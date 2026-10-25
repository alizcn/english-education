"""Kelime hazinesini Claude ile zenginleştirir — DEVAM EDEBİLİR.

Girdi: ``apps/wordbank/data/<hedef>/<seviye>.raw.json`` (ham liste —
``build_wordlist`` üretiyor) ya da mevcut ``<seviye>.json``.
Çıktı: `GenerationBatch` satırları; `export_content` onları repo JSON'una döküyor.

İki aşama var:

* **Hedef taraf** (``--native`` verilmez): örnek cümle ve dile özgü morfoloji.
  Kelime başına BİR KEZ üretiliyor.
* **Ana dil tarafı** (``--native tr``): anlam ve örnek cümlenin çevirisi.
  Her ana dil için ayrı.

Ayrımın nedeni ölçüldü: örnek cümleyi ana dil başına yeniden üretmek 45.436
gereksiz üretim demekti.

Kullanım (oturum limitine dayanıklı)::

    until manage.py enrich_wordbank --target de --native tr --workers 3; do
      [ $? -eq 75 ] && sleep 1800 || break
    done
"""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.content.models import GenerationBatch
from apps.content.runner import (
    EXIT_TEMPFAIL, BatchValidationError, plan_chunks, run_batches,
)
from apps.content import terms as terms_index
from apps.wordbank.models import BankWord
from services import claude_client as claude
from services import languages

DATA_DIR = Path(__file__).resolve().parents[3] / 'wordbank' / 'data'
DEFAULT_BATCH = 25

# Model alan sınırları. Taşan metin arayüzü bozuyor ve MySQL'e geçişte
# sessiz kesilme yerine hata veriyor; kapı burada.
LIMITS = {'term': 120, 'part_of_speech': 40, 'example': 500,
          'meaning': 400, 'example_translation': 500}

#: `--repair` parçalarının indeks tabanı. Normal plan 0'dan sayıyor; onarım
#: parçaları buradan başlıyor ki `(kind, target, native, level, chunk_index)`
#: tekilliğinde çakışmasınlar ve `--batch` tutarlılık kontrolü bozulmasın.
REPAIR_OFFSET = 10_000


def _read_terms(target, level, data_dir=None):
    """Ham ya da zenginleştirilmiş dosyadan `(rank, term)` listesi."""
    lang_dir = (data_dir or DATA_DIR) / target
    for name in (f'{level.lower()}.raw.json', f'{level.lower()}.json'):
        path = lang_dir / name
        if path.exists():
            items = json.loads(path.read_text(encoding='utf-8'))
            out = []
            for item in items:
                term = (item.get('term') or item.get('english') or '').strip()
                if term and isinstance(item.get('rank'), int):
                    out.append({'rank': item['rank'], 'term': term})
            # Deterministik sıra: parça indeksleri buna bağlı.
            return sorted(out, key=lambda x: x['rank'])
    return []


class Command(BaseCommand):
    help = 'Kelime hazinesi için anlam/örnek üretir (devam edebilir).'

    def add_arguments(self, parser):
        parser.add_argument('--target', required=True, help='Hedef dil kodu.')
        parser.add_argument('--data-dir', default=None,
                            help=f'Kaynak liste kökü (varsayılan: {DATA_DIR}).')
        parser.add_argument('--native', default=None,
                            help='Ana dil kodu. Verilmezse hedef taraf '
                                 '(örnek cümle + morfoloji) üretilir.')
        parser.add_argument('--level', default=None, help='Yalnızca bu seviye.')
        parser.add_argument('--batch', type=int, default=DEFAULT_BATCH,
                            help=f'Parça başına kelime (varsayılan {DEFAULT_BATCH}).')
        parser.add_argument('--workers', type=int, default=None,
                            help='Paralel parça sayısı (varsayılan CLAUDE_MAX_PARALLEL).')
        parser.add_argument('--model', default=None, help='CLAUDE_MODEL ezmesi.')
        parser.add_argument('--effort', default=None,
                            help='CLAUDE_REASONING_EFFORT ezmesi.')
        parser.add_argument('--limit', type=int, default=None,
                            help='En çok bu kadar parça işle (deneme için).')
        parser.add_argument('--max-runtime', type=int, default=None,
                            help='Saniye cinsinden duvar saati sınırı.')
        parser.add_argument('--replan', action='store_true',
                            help='--batch değiştiyse planı yeniden kur '
                                 '(tamamlanmamış parçalar silinir).')
        parser.add_argument('--status', action='store_true',
                            help='Hiçbir şey üretmeden ilerlemeyi raporla.')
        parser.add_argument('--repair', action='store_true',
                            help='Yalnızca DB\'de karşılığı EKSİK kalan '
                                 'kayıtlar için parça kurar (--native şart).')

    def handle(self, *args, **opts):
        target = opts['target']
        native = opts['native'] or ''
        try:
            spec = languages.get(target)
            pair = languages.pair(target, native) if native else None
        except (languages.UnknownLanguage, ValueError) as e:
            raise CommandError(str(e))

        levels = [opts['level'].upper()] if opts['level'] else list(spec.cefr_levels)
        self.data_dir = Path(opts['data_dir']) if opts.get('data_dir') else DATA_DIR

        if opts['status']:
            return self._report(target, native, levels)

        if opts['repair']:
            self._plan_repair(target, native, levels, opts)
        else:
            self._plan(target, native, levels, opts)

        queryset = GenerationBatch.objects.filter(
            kind=GenerationBatch.WORDBANK,
            target_language=target, native_language=native,
            level__in=levels,
        )

        overrides = {}
        if opts['model']:
            overrides['CLAUDE_MODEL'] = opts['model']
        if opts['effort']:
            overrides['CLAUDE_REASONING_EFFORT'] = opts['effort']

        produce = self._make_producer(pair, spec, native)
        with claude.options(**overrides):
            done, failed, left, stopped = run_batches(
                queryset, produce,
                validate=self._validate,
                workers=opts['workers'],
                max_runtime=opts['max_runtime'],
                stdout=self.stdout,
            )

        self.stdout.write(self.style.SUCCESS(
            f'{target}<-{native or "(mono)"}: {done} parça bitti, '
            f'{failed} başarısız, {left} kaldı.'
        ))

        if stopped == 'session_limit':
            self.stdout.write(self.style.WARNING(
                'Oturum limiti. Parçalar kayıtlı; komutu sonra tekrar koşun. '
                f'(çıkış {EXIT_TEMPFAIL})'
            ))
            sys.exit(EXIT_TEMPFAIL)
        if left:
            sys.exit(EXIT_TEMPFAIL)

    # ------------------------------------------------------------------ plan

    def _plan_repair(self, target, native, levels, opts):
        """Karşılığı eksik kalan kayıtlar için parça kurar.

        Niçin gerekli: DOĞRULAMA düzeltmelerinde payload'dan çıkarılan
        terimler (modelin karıştırdığı ya da reddettiği kelimeler) DB'de
        karşılıksız kalıyor ve `load_wordbank` onları atlıyor — yani satır
        var ama kullanıcıya hiç çıkmıyor. Normal plan onları geri getirmiyor
        çünkü o parçalar `done`.

        Parça indeksleri `REPAIR_OFFSET`ten başlıyor ki normal planın
        anahtarlarıyla çakışmasın ve `--batch` tutarlılık kontrolü bozulmasın.
        """
        if not native:
            raise CommandError('--repair için --native şart: onarılan şey '
                               'eksik karşılık.')
        created = 0
        for level in levels:
            missing = []
            words = (
                BankWord.objects
                .filter(language=target, level=level)
                .prefetch_related('translations')
                .order_by('rank')
            )
            for word in words:
                meaning = ''
                for row in word.translations.all():
                    if row.language == native:
                        meaning = (row.meaning or '').strip()
                        break
                if not meaning:
                    missing.append({'rank': word.rank, 'term': word.term})
            if not missing:
                self.stdout.write(f'{target}/{level}: eksik karşılık yok.')
                continue

            existing = set(
                GenerationBatch.objects.filter(
                    kind=GenerationBatch.WORDBANK, target_language=target,
                    native_language=native, level=level,
                    chunk_index__gte=REPAIR_OFFSET,
                ).values_list('chunk_index', flat=True)
            )
            rows = []
            for index, chunk in plan_chunks(missing, opts['batch']):
                key = REPAIR_OFFSET + index
                if key in existing:
                    continue
                rows.append(GenerationBatch(
                    kind=GenerationBatch.WORDBANK,
                    target_language=target, native_language=native,
                    level=level, chunk_index=key, batch_size=opts['batch'],
                    input_payload={'terms': chunk},
                ))
            if rows:
                GenerationBatch.objects.bulk_create(rows, ignore_conflicts=True)
                created += len(rows)
            self.stdout.write(
                f'{target}/{level}: {len(missing)} eksik karşılık, '
                f'{len(rows)} onarım parçası.'
            )
        if created:
            self.stdout.write(f'{created} onarım parçası planlandı.')

    def _plan(self, target, native, levels, opts):
        """Parçaları deterministik olarak kurar; mevcutlara dokunmaz."""
        created = 0
        for level in levels:
            terms = _read_terms(target, level, self.data_dir)
            if not terms:
                self.stdout.write(f'{target}/{level}: kaynak liste yok — atlandı.')
                continue

            existing = {
                b.chunk_index: b
                for b in GenerationBatch.objects.filter(
                    kind=GenerationBatch.WORDBANK, target_language=target,
                    native_language=native, level=level,
                )
            }
            # `--batch` değişimi tüm parça anahtarlarını kaydırır ve yarı
            # tamamlanmış işi çöpe atar; bu yüzden açıkça reddediyoruz.
            stale = [b for b in existing.values() if b.batch_size != opts['batch']]
            if stale and not opts['replan']:
                raise CommandError(
                    f'{target}/{level}: kayıtlı parçalar batch_size='
                    f'{stale[0].batch_size} ile kurulmuş, şimdi {opts["batch"]} '
                    'istendi. Parça anahtarları kayar ve tamamlanmış iş '
                    'kullanılamaz hâle gelir. Aynı değerle devam edin ya da '
                    '--replan verin.'
                )
            if stale and opts['replan']:
                with transaction.atomic():
                    GenerationBatch.objects.filter(
                        kind=GenerationBatch.WORDBANK, target_language=target,
                        native_language=native, level=level,
                    ).exclude(status=GenerationBatch.DONE).delete()
                existing = {
                    b.chunk_index: b
                    for b in GenerationBatch.objects.filter(
                        kind=GenerationBatch.WORDBANK, target_language=target,
                        native_language=native, level=level,
                    )
                }

            rows = []
            for index, chunk in plan_chunks(terms, opts['batch']):
                if opts['limit'] is not None and index >= opts['limit']:
                    break
                if index in existing:
                    continue
                rows.append(GenerationBatch(
                    kind=GenerationBatch.WORDBANK,
                    target_language=target, native_language=native,
                    level=level, chunk_index=index, batch_size=opts['batch'],
                    input_payload={'terms': chunk},
                ))
            if rows:
                GenerationBatch.objects.bulk_create(rows, ignore_conflicts=True)
                created += len(rows)
        if created:
            self.stdout.write(f'{created} yeni parça planlandı.')

    # -------------------------------------------------------------- üretici

    def _make_producer(self, pair, spec, native):
        """İş parçacığında koşacak fonksiyon — YALNIZCA Claude çağırır.

        `parallel_map`in sözleşmesi: burada veritabanına dokunulmaz.
        """
        if native:
            def produce(batch):
                # Aynı terim farklı anlamlarla birden çok kez gelebilir (EN'de
                # çok anlamlı kelimeler). Claude'a her terimi yalnızca bir kez
                # gönderiyoruz; doğrulama da set kullandığı için tutarlı.
                seen_keys: set = set()
                unique_terms: list = []
                for t in batch.input_payload['terms']:
                    key = t['term'].lower()
                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_terms.append(t['term'])
                items = claude.generate_lexicon_entries(unique_terms, pair=pair)
                return {'items': items}
        else:
            # Mono taraf: ana dil yok, yine de `pair` gerekiyor çünkü prompt
            # öğrenen profilini kuruyor. Varsayılan arayüz dilini ana dil
            # sayıyoruz; üretilen alanlardan yalnızca hedef taraf kullanılacak.
            fallback_native = next(
                code for code in languages.UI_CODES if code != spec.code
            )
            mono_pair = languages.pair(spec.code, fallback_native)

            def produce(batch):
                terms = [t['term'] for t in batch.input_payload['terms']]
                items = claude.generate_lexicon_entries(terms, pair=mono_pair)
                # Ana dil tarafını atıyoruz: bu aşama yalnızca hedef dildeki
                # örnek cümleyi ve morfolojiyi üretiyor.
                for item in items:
                    item.pop('meaning', None)
                    item.pop('example_translation', None)
                return {'items': items}

        return produce

    # ------------------------------------------------------------ doğrulama

    @staticmethod
    def _validate(batch, output):
        items = (output or {}).get('items') or []
        if not items:
            raise BatchValidationError('boş çıktı')

        payload = batch.input_payload['terms']
        wanted = {
            (t['term'] if isinstance(t, dict) else t).strip() for t in payload
        }
        # Eşleme aksan/büyük-küçük harf sapmasına toleranslı ve dışa aktarma
        # ile AYNI dizinden okuyor (`apps/content/terms.py`): doğrulayıcı
        # gevşek, dışa aktarma katı olursa parça `done` olur ama kayıt
        # dosyaya yazılmaz.
        index = terms_index.build_index(payload)
        seen = set()
        for item in items:
            term = (item.get('term') or '').strip()
            if not term:
                raise BatchValidationError('terimsiz kayıt')
            # Model bazen terimi yeniden yazıyor; eşleşmeyen kayıt sessizce
            # yanlış kelimeye anlam yazmak demek.
            canonical = terms_index.resolve(term, index)
            if canonical is None:
                raise BatchValidationError(
                    f'istenmeyen terim döndü: {term!r} (istenen: {len(wanted)} terim)'
                )
            if canonical in seen:
                raise BatchValidationError(
                    f'parça içinde yinelenen terim: {canonical}'
                )
            seen.add(canonical)
            if batch.native_language and not (item.get('meaning') or '').strip():
                raise BatchValidationError(f'{canonical}: anlam boş')
            for field, limit in LIMITS.items():
                value = item.get(field)
                if value and len(value) > limit:
                    raise BatchValidationError(
                        f'{canonical}: {field} {len(value)} karakter, '
                        f'sınır {limit}'
                    )

        missing = wanted - seen
        if not missing:
            return
        # Onarım parçasında KISMİ kapsama kabul ediliyor. Gerekçe: onarım
        # zaten artakalanları topluyor ve listede modelin meşru olarak
        # karşılık üretemediği terimler var (`kaori` bir Japon özel adı,
        # Fransızca kelime değil). Hepsi-ya-hiç kuralı tek bir çöp terimin
        # yanındaki 20 gerçek kelimeyi de süresiz bloke ediyordu. Kapsanmayan
        # terim gizlenmiyor: bir sonraki `--repair` planında yine çıkıyor,
        # yani sorun kelime listesine geri gösteriliyor.
        #
        # Normal parçada kural katı kalıyor: orada tam kapsama GERÇEK
        # değişmez, eksik terim sessizce kaybolan kelime demek.
        if batch.chunk_index >= REPAIR_OFFSET and seen:
            return
        raise BatchValidationError(
            f'{len(missing)} terim eksik: {sorted(missing)[:5]}'
        )

    # --------------------------------------------------------------- rapor

    def _report(self, target, native, levels):
        rows = GenerationBatch.objects.filter(
            kind=GenerationBatch.WORDBANK,
            target_language=target, native_language=native,
            level__in=levels,
        )
        total = rows.count()
        if not total:
            self.stdout.write('Hiç parça planlanmamış.')
            return
        by_status = {}
        for status, _label in GenerationBatch.STATUS_CHOICES:
            by_status[status] = rows.filter(status=status).count()
        self.stdout.write(f'{target}<-{native or "(mono)"}: {total} parça')
        for status, count in by_status.items():
            if count:
                self.stdout.write(f'  {status:8s} {count}')
        stuck = rows.filter(
            status=GenerationBatch.FAILED,
            attempts__gte=GenerationBatch.MAX_ATTEMPTS,
        )
        if stuck.exists():
            self.stdout.write(self.style.WARNING(
                f'  {stuck.count()} parça deneme hakkını tüketti:'
            ))
            for batch in stuck[:5]:
                self.stdout.write(f'    {batch}: {batch.last_error[:100]}')
