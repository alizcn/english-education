"""Konu anlatımlarını ve örneklerini Claude ile üretir — DEVAM EDEBİLİR.

Girdi: ``apps/topics/data/<hedef>/topics.json`` (slug + ad + sıra; elle yazılır,
çünkü Almanca'nın gramer konuları İngilizce'den çeviri değil).

Çıktı: `GenerationBatch` satırları; `export_content --kind topics` onları
repo dosyalarına döküyor:

* anlatım  -> ``apps/topics/data/<hedef>/explanations/<ana>/<slug>.md``
* örnekler -> ``apps/topics/data/<hedef>/topics.json`` içindeki ``examples``

İki tür parça var:

* **topic_explanation** — her (hedef, slug, ana dil) için bir anlatım.
  Metin ana dilde, örnekler hedef dilde.
* **topic_examples** — her (hedef, slug) için BİR örnek kümesi
  (``native_language=''``). Cümle hedef dilde bir kez üretilip çağrı içinde
  tüm ana dillere çevriliyor; ana dil başına yeniden üretmek aynı cümleyi
  üç kez yazdırmak demekti.

Kullanım (oturum limitine dayanıklı)::

    until manage.py generate_topic_content --target de --workers 3; do
      [ $? -eq 75 ] && sleep 1800 || break
    done
"""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.content.models import GenerationBatch
from apps.content.runner import (
    EXIT_TEMPFAIL, BatchValidationError, run_batches,
)
from services import claude_client as claude
from services import languages

DATA_DIR = Path(__file__).resolve().parents[3] / 'topics' / 'data'

#: Anlatım gövdesi alt sınırı. Bunun altındaki metin konu anlatımı değil,
#: modelin yarım bıraktığı bir cevap; sessizce yayına girmesin.
MIN_BODY_CHARS = 400

#: Örnek türü başına beklenen cümle sayısı.
PER_KIND = 6
EXAMPLE_KINDS = ('positive', 'negative', 'question')


def read_topics(target, data_dir=None):
    """`topics.json`'dan `(slug, name, order)` listesi — deterministik sırada."""
    path = (data_dir or DATA_DIR) / target / 'topics.json'
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for item in items:
        slug = (item.get('slug') or '').strip()
        name = (item.get('name') or '').strip()
        if slug and name and isinstance(item.get('order'), int):
            out.append({'slug': slug, 'name': name, 'order': item['order']})
    return sorted(out, key=lambda x: x['order'])


def _explanation_path(target, native, slug, data_dir=None):
    return ((data_dir or DATA_DIR) / target / 'explanations' / native
            / f'{slug}.md')


class Command(BaseCommand):
    help = 'Konu anlatımı ve örnekleri üretir (devam edebilir).'

    def add_arguments(self, parser):
        parser.add_argument('--target', required=True, help='Hedef dil kodu.')
        parser.add_argument('--native', default=None,
                            help='Yalnızca bu ana dil için anlatım üret. '
                                 'Verilmezse yayındaki tüm arayüz dilleri.')
        parser.add_argument('--slug', default=None, help='Yalnızca bu konu.')
        parser.add_argument('--kind', default='all',
                            choices=['all', 'explanation', 'examples'],
                            help='Yalnızca bu tür parçalar.')
        parser.add_argument('--data-dir', default=None,
                            help=f'Konu kökü (varsayılan: {DATA_DIR}).')
        parser.add_argument('--workers', type=int, default=None)
        parser.add_argument('--model', default=None)
        parser.add_argument('--effort', default=None)
        parser.add_argument('--limit', type=int, default=None,
                            help='En çok bu kadar parça işle (deneme için).')
        parser.add_argument('--max-runtime', type=int, default=None)
        parser.add_argument('--status', action='store_true',
                            help='Hiçbir şey üretmeden ilerlemeyi raporla.')

    def handle(self, *args, **opts):
        target = opts['target']
        try:
            spec = languages.get(target)
        except languages.UnknownLanguage as e:
            raise CommandError(str(e))
        if not spec.is_learnable:
            raise CommandError(f'{target} öğrenilebilir dil değil.')

        self.data_dir = Path(opts['data_dir']) if opts.get('data_dir') else DATA_DIR
        self.topics = read_topics(target, self.data_dir)
        if not self.topics:
            raise CommandError(
                f'{self.data_dir / target / "topics.json"} yok ya da boş. '
                'Konu listesi elle yazılır.'
            )
        if opts['slug']:
            self.topics = [t for t in self.topics if t['slug'] == opts['slug']]
            if not self.topics:
                raise CommandError(f'{opts["slug"]}: topics.json içinde yok.')

        # Anlatım, kursun ana dilinde okunuyor; ana dil arayüz diline bağlı
        # olmadığı için sicildeki tüm diller için üretiliyor.
        natives = ([opts['native']] if opts['native']
                   else [code for code in languages.ALL_CODES])
        for code in natives:
            try:
                languages.get(code)
            except languages.UnknownLanguage as e:
                raise CommandError(str(e))

        kinds = ({'explanation', 'examples'} if opts['kind'] == 'all'
                 else {opts['kind']})

        if opts['status']:
            return self._report(target, kinds)

        self._plan(target, natives, kinds, opts)

        wanted_kinds = []
        if 'explanation' in kinds:
            wanted_kinds.append(GenerationBatch.TOPIC_EXPLANATION)
        if 'examples' in kinds:
            wanted_kinds.append(GenerationBatch.TOPIC_EXAMPLES)

        queryset = GenerationBatch.objects.filter(
            kind__in=wanted_kinds, target_language=target,
            topic_slug__in=[t['slug'] for t in self.topics],
        )
        if opts['native']:
            queryset = queryset.filter(
                native_language__in=[opts['native'], '']
            )

        overrides = {}
        if opts['model']:
            overrides['CLAUDE_MODEL'] = opts['model']
        if opts['effort']:
            overrides['CLAUDE_REASONING_EFFORT'] = opts['effort']

        with claude.options(**overrides):
            done, failed, left, stopped = run_batches(
                queryset, self._produce,
                validate=self._validate,
                workers=opts['workers'],
                max_runtime=opts['max_runtime'],
                stdout=self.stdout,
            )

        self.stdout.write(self.style.SUCCESS(
            f'{target} konu içeriği: {done} parça bitti, {failed} başarısız, '
            f'{left} kaldı.'
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

    def _plan(self, target, natives, kinds, opts):
        """Parçaları kurar; mevcutlara dokunmaz."""
        rows = []
        planned = 0
        for topic in self.topics:
            if opts['limit'] is not None and planned >= opts['limit']:
                break
            if 'explanation' in kinds:
                for native in natives:
                    rows.append(GenerationBatch(
                        kind=GenerationBatch.TOPIC_EXPLANATION,
                        target_language=target, native_language=native,
                        topic_slug=topic['slug'], chunk_index=0, batch_size=1,
                        input_payload={'slug': topic['slug'],
                                       'name': topic['name']},
                    ))
            if 'examples' in kinds:
                # native_language='' — cümle hedef dilde bir kez üretilir,
                # çeviriler aynı çağrıda tüm ana dillere yapılır.
                rows.append(GenerationBatch(
                    kind=GenerationBatch.TOPIC_EXAMPLES,
                    target_language=target, native_language='',
                    topic_slug=topic['slug'], chunk_index=0, batch_size=1,
                    input_payload={'slug': topic['slug'],
                                   'name': topic['name'],
                                   'natives': [c for c in languages.ALL_CODES
                                               if c != target]},
                ))
            planned += 1
        if rows:
            created = GenerationBatch.objects.bulk_create(
                rows, ignore_conflicts=True,
            )
            # SQLite'ta `ignore_conflicts` eklenmeyeni de döndürüyor; gerçek
            # sayıyı saymak için yeniden sorgulamak gerekir, rapor o işi yapıyor.
            self.stdout.write(f'{len(created)} parça planlandı (mevcutlar atlandı).')

    # -------------------------------------------------------------- üretici

    def _produce(self, batch):
        """İş parçacığında koşar — YALNIZCA Claude çağırır, DB'ye dokunmaz."""
        payload = batch.input_payload
        name = payload['name']
        target_spec = languages.get(batch.target_language)

        if batch.kind == GenerationBatch.TOPIC_EXPLANATION:
            # `languages.pair()` aynı dili reddediyor ama `Pair` onu tutabilir
            # (`is_mono`). Hedef dilin kendi dilindeki anlatımı meşru bir
            # gramer referansı — `apps/topics/data/en/explanations/en/` zaten
            # bunu barındırıyor.
            native_spec = languages.get(batch.native_language)
            pair = languages.Pair(target_spec, native_spec)
            body = claude.generate_topic_explanation(name, pair=pair)
            return {'body': body}

        natives = {
            code: languages.get(code).english_name
            for code in (payload.get('natives')
                         or [c for c in languages.ALL_CODES
                             if c != batch.target_language])
        }
        items = claude.generate_topic_examples(
            name, '', target=batch.target_language,
            target_name=target_spec.english_name,
            natives=natives, per_kind=PER_KIND,
        )
        return {'items': items}

    # ------------------------------------------------------------ doğrulama

    @staticmethod
    def _validate(batch, output):
        output = output or {}
        if batch.kind == GenerationBatch.TOPIC_EXPLANATION:
            body = (output.get('body') or '').strip()
            if len(body) < MIN_BODY_CHARS:
                raise BatchValidationError(
                    f'anlatım {len(body)} karakter, en az {MIN_BODY_CHARS} '
                    'bekleniyor'
                )
            # Ayrıştırıcı yalnızca `##` başlığını tanıyor; başlıksız metin tek
            # bloğa düşer ve sayfa okunamaz hâle gelir.
            if '\n##' not in body and not body.startswith('##'):
                raise BatchValidationError('hiç "##" başlığı yok')
            if '```' in body:
                raise BatchValidationError('kod bloğu içeriyor')
            return

        items = output.get('items') or []
        if not items:
            raise BatchValidationError('boş çıktı')
        wanted_natives = set(
            batch.input_payload.get('natives')
            or [c for c in languages.ALL_CODES if c != batch.target_language]
        )
        by_kind = {}
        seen = set()
        for item in items:
            kind = item.get('kind')
            sentence = (item.get('sentence') or '').strip()
            if kind not in EXAMPLE_KINDS:
                raise BatchValidationError(f'geçersiz tür: {kind!r}')
            if not sentence:
                raise BatchValidationError('cümlesiz kayıt')
            key = sentence.lower()
            if key in seen:
                raise BatchValidationError(f'yinelenen cümle: {sentence[:40]}')
            seen.add(key)
            missing = wanted_natives - set(item.get('translations') or {})
            if missing:
                raise BatchValidationError(
                    f'{sentence[:30]!r}: çeviri eksik {sorted(missing)}'
                )
            by_kind[kind] = by_kind.get(kind, 0) + 1

        for kind in EXAMPLE_KINDS:
            if by_kind.get(kind, 0) < PER_KIND:
                raise BatchValidationError(
                    f'{kind}: {by_kind.get(kind, 0)} cümle, {PER_KIND} isteniyor'
                )

    # --------------------------------------------------------------- rapor

    def _report(self, target, kinds):
        wanted = []
        if 'explanation' in kinds:
            wanted.append(GenerationBatch.TOPIC_EXPLANATION)
        if 'examples' in kinds:
            wanted.append(GenerationBatch.TOPIC_EXAMPLES)
        rows = GenerationBatch.objects.filter(
            kind__in=wanted, target_language=target,
        )
        if not rows.exists():
            self.stdout.write('Hiç parça planlanmamış.')
            return
        for kind in wanted:
            sub = rows.filter(kind=kind)
            total = sub.count()
            if not total:
                continue
            done = sub.filter(status=GenerationBatch.DONE).count()
            self.stdout.write(f'{target} {kind}: {done}/{total}')
            for status, _label in GenerationBatch.STATUS_CHOICES:
                if status == GenerationBatch.DONE:
                    continue
                count = sub.filter(status=status).count()
                if count:
                    self.stdout.write(f'  {status:8s} {count}')
        stuck = rows.filter(
            status=GenerationBatch.FAILED,
            attempts__gte=GenerationBatch.MAX_ATTEMPTS,
        )
        if stuck.exists():
            self.stdout.write(self.style.WARNING(
                f'{stuck.count()} parça deneme hakkını tüketti:'
            ))
            for batch in stuck[:5]:
                self.stdout.write(f'  {batch}: {batch.last_error[:100]}')
