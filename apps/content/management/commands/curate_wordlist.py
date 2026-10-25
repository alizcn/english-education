"""Frekans adaylarından gerçek sözlük maddelerini ayıklar — DEVAM EDEBİLİR.

`build_wordlist` deterministik: `wordfreq` ne veriyorsa onu yazıyor. Ama
frekans listesi YÜZEY BİÇİMLERİ veriyor ve kuyruğu sözlük maddesi değil.
Ölçülmüş örnekler (C2 bandı):

* Türkçe — `gruplarına`, `göstergesidir` (çekimli), `hamilton`, `rebecca`
  (özel ad), `phone`, `price` (İngilizce sızıntısı)
* Almanca — `early`, `earth` (İngilizce), `betty`, `bologna` (özel ad),
  `blonden` (çekimli sıfat)
* İngilizce — `mis`, `mma`, `comin` (kelime değil)

Bunları kelime hazinesine koymak öğrenciye çöp ezberletmek olurdu; daha önce
Türkçe listesinde tam olarak bu yüzden 43 kayıt budandı. Planın §1'i bu adımı
zaten öngörüyordu: "filtre → lemmatizasyon + seviye Claude ile".

Akış::

    build_wordlist --target tr --source wordfreq --levels C2 --exclude-existing
    curate_wordlist --target tr --level C2 --keep 1000      # BU KOMUT
    enrich_wordbank --target tr --native en ...

Girdi ve çıktı aynı dosya: ``<seviye>.raw.json``. Komut önce ham adayları
yedekliyor (``<seviye>.candidates.json``) ki ayıklama yeniden koşturulabilsin.
"""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.content.models import GenerationBatch
from apps.content.runner import (
    EXIT_TEMPFAIL, BatchValidationError, plan_chunks, run_batches,
)
from services import claude_client as claude
from services import languages

DATA_DIR = Path(__file__).resolve().parents[3] / 'wordbank' / 'data'

#: Çağrı başına aday. Büyük parça modelin listeyi savsaklamasına yol açıyor.
DEFAULT_BATCH = 60

#: Parça başına kaç madde tutulacağı — adayların yaklaşık üçte biri.
#: Frekans kuyruğunda eleme oranı yüksek, bunu zorlamak çöpü içeri alır.
KEEP_RATIO = 0.35


class Command(BaseCommand):
    help = 'Frekans adaylarını Claude ile ayıklayıp lemmalaştırır.'

    def add_arguments(self, parser):
        parser.add_argument('--target', required=True)
        parser.add_argument('--level', required=True)
        parser.add_argument('--batch', type=int, default=DEFAULT_BATCH)
        parser.add_argument('--keep', type=int, default=None,
                            help='Toplam tutulacak madde (varsayılan: sınırsız).')
        parser.add_argument('--workers', type=int, default=None)
        parser.add_argument('--max-runtime', type=int, default=None)
        parser.add_argument('--write', action='store_true',
                            help='Tamamlanan parçaları raw.json dosyasına yaz.')
        parser.add_argument('--status', action='store_true')

    def handle(self, *args, **opts):
        target, level = opts['target'], opts['level'].upper()
        try:
            spec = languages.get(target)
        except languages.UnknownLanguage as e:
            raise CommandError(str(e))

        lang_dir = DATA_DIR / target
        raw_path = lang_dir / f'{level.lower()}.raw.json'
        cand_path = lang_dir / f'{level.lower()}.candidates.json'

        queryset = GenerationBatch.objects.filter(
            kind=GenerationBatch.WORDLIST_CURATION,
            target_language=target, level=level,
        )

        if opts['status']:
            total = queryset.count()
            done = queryset.filter(status=GenerationBatch.DONE).count()
            kept = sum(len((b.output or {}).get('terms', []))
                       for b in queryset.filter(status=GenerationBatch.DONE))
            self.stdout.write(f'{target}/{level}: {done}/{total} parça, '
                              f'{kept} madde ayıklandı.')
            return

        if opts['write']:
            return self._write(target, level, raw_path, queryset, opts)

        # Adaylar: ilk koşuda ham dosyadan alınıp ayrıca saklanıyor, çünkü
        # ayıklama sonucu aynı dosyanın üstüne yazılıyor.
        if not cand_path.exists():
            if not raw_path.exists():
                raise CommandError(
                    f'{raw_path} yok. Önce: manage.py build_wordlist '
                    f'--target {target} --source wordfreq --levels {level} '
                    '--exclude-existing'
                )
            cand_path.write_text(raw_path.read_text(encoding='utf-8'),
                                 encoding='utf-8')
            self.stdout.write(f'Adaylar saklandı -> {cand_path}')

        candidates = json.loads(cand_path.read_text(encoding='utf-8'))
        terms = [c['term'] for c in candidates if c.get('term')]
        if not terms:
            raise CommandError(f'{cand_path} içinde terim yok.')

        self._plan(target, level, terms, opts)

        def produce(batch):
            payload = batch.input_payload
            return {'terms': claude.curate_wordlist_terms(
                payload['terms'],
                language_name=spec.english_name,
                level=level,
                keep=payload['keep'],
            )}

        done, failed, left, stopped = run_batches(
            queryset, produce,
            validate=self._validate,
            workers=opts['workers'],
            max_runtime=opts['max_runtime'],
            stdout=self.stdout,
        )
        self.stdout.write(self.style.SUCCESS(
            f'{target}/{level}: {done} parça bitti, {failed} başarısız, '
            f'{left} kaldı.\n'
            f'Şimdi: manage.py curate_wordlist --target {target} '
            f'--level {level} --write'
        ))
        if stopped == 'session_limit' or left:
            sys.exit(EXIT_TEMPFAIL)

    def _plan(self, target, level, terms, opts):
        existing = set(
            GenerationBatch.objects.filter(
                kind=GenerationBatch.WORDLIST_CURATION,
                target_language=target, level=level,
            ).values_list('chunk_index', flat=True)
        )
        rows = []
        for index, chunk in plan_chunks(
            [{'term': t} for t in terms], opts['batch'],
        ):
            if index in existing:
                continue
            chunk_terms = [c['term'] for c in chunk]
            rows.append(GenerationBatch(
                kind=GenerationBatch.WORDLIST_CURATION,
                target_language=target, native_language='', level=level,
                chunk_index=index, batch_size=opts['batch'],
                input_payload={
                    'terms': chunk_terms,
                    'keep': max(int(len(chunk_terms) * KEEP_RATIO), 1),
                },
            ))
        if rows:
            GenerationBatch.objects.bulk_create(rows, ignore_conflicts=True)
            self.stdout.write(f'{len(rows)} yeni parça planlandı.')

    @staticmethod
    def _validate(batch, output):
        terms = (output or {}).get('terms') or []
        if not terms:
            raise BatchValidationError('boş çıktı')
        wanted = {t.lower() for t in batch.input_payload['terms']}
        for item in terms:
            term = (item.get('term') or '').strip()
            if not term:
                raise BatchValidationError('terimsiz kayıt')
            if len(term) > 120:
                raise BatchValidationError(f'{term[:30]}: terim çok uzun')
        # Lemmalaştırma adaylardan SAPMAYA izin veriyor (`gruplarına` ->
        # `grup`), o yüzden birebir eşleşme aranmıyor. Ama modelin listeden
        # tamamen kopup kendi kelimelerini uydurması da kabul değil: en az
        # bir madde adaylarla aynı kökten gelmeli.
        if not any(
            any(t.startswith(item['term'][:4].lower()) for t in wanted)
            for item in terms if len(item.get('term') or '') >= 4
        ):
            raise BatchValidationError(
                'çıktı adaylarla ilişkisiz görünüyor'
            )

    def _write(self, target, level, raw_path, queryset, opts):
        """Tamamlanan parçaları `raw.json`a yazar — ENRİCH BUNU OKUYOR."""
        batches = queryset.filter(
            status=GenerationBatch.DONE,
        ).order_by('chunk_index')
        if not batches:
            raise CommandError('Tamamlanmış parça yok.')

        # Rank'ler MEVCUT en büyük rank'ten sonra başlıyor. `load_wordbank`
        # (dil, seviye, rank) anahtarıyla upsert ettiği için 1'den başlamak
        # o seviyedeki mevcut kayıtların ÜZERİNE yazardı — İngilizce C2'de
        # zaten 250 kayıt var ve hepsi kaybolurdu.
        from apps.wordbank.models import BankWord
        offset = (
            BankWord.objects.filter(language=target, level=level)
            .order_by('-rank').values_list('rank', flat=True).first() or 0
        )
        mevcut_terimler = set(
            BankWord.objects.filter(language=target, level=level)
            .values_list('term', flat=True)
        )
        seen = {t.lower() for t in mevcut_terimler}
        rows = []
        for batch in batches:
            for item in (batch.output or {}).get('terms', []):
                term = (item.get('term') or '').strip()
                key = term.lower()
                if not term or key in seen:
                    continue
                seen.add(key)
                rows.append({
                    'rank': offset + len(rows) + 1,
                    'term': term,
                    'part_of_speech': item.get('part_of_speech') or '',
                    'extra': {},
                })
        if opts['keep']:
            rows = rows[:opts['keep']]
            for index, row in enumerate(rows, 1):
                row['rank'] = offset + index

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        self.stdout.write(self.style.SUCCESS(
            f'{target}/{level}: {len(rows)} madde -> {raw_path}\n'
            f'Şimdi: manage.py enrich_wordbank --target {target} '
            f'--level {level} --native <dil>'
        ))
