"""Kelime hazinesini JSON dosyalarından yükler.

Dosya düzeni: ``apps/wordbank/data/<hedef_dil>/<seviye>.json``

Her kayıt::

    {
      "rank": 1,
      "term": "book",
      "part_of_speech": "noun",
      "example": "I read a book every night.",
      "extra": {},
      "translations": {
        "tr": {"meaning": "kitap", "example_translation": "Her gece kitap okurum."},
        "fr": {"meaning": "livre", "example_translation": "Je lis un livre chaque soir."}
      }
    }

Eski düzen (``data/<seviye>.json`` + ``english``/``turkish``/``example_en``/
``example_tr`` anahtarları) da okunuyor; `_normalise_record` onu yeni şekle
çeviriyor. Böylece dosyalar dönüştürülürken yükleyici iki biçimi birden
destekliyor.

ESKİ YÜKLEYİCİDEN ÜÇ FARK:

1. **Anahtar `(language, level, rank)`**, `(level, english, part_of_speech)`
   değil. `part_of_speech` kaynak veride %90 boş olduğu için çok anlamlı
   kelimeler tek satıra çöküyordu: JSON'daki 6.218 kaydın 55'i veritabanına
   HİÇ girmiyordu (A1'deki `about` "yaklaşık" ve "hakkında" olarak iki kez
   var; biri kayboluyordu).
2. **`update_or_create`**, `get_or_create(defaults=...)` değil. Eskisi
   yalnızca satır yokken `defaults` uyguluyordu, yani bir çeviriyi düzeltip
   yeniden yüklemek sessizce hiçbir şey yapmıyordu.
3. **Sonda eşitlik doğrulaması.** Dosyadaki kayıt sayısı ile veritabanındaki
   satır sayısı tutmuyorsa komut hata veriyor. Bu kontrol olmadığı için 55
   kayıtlık kayıp aylarca sessiz kaldı.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.wordbank.models import BankWord, BankWordTranslation
from services import languages

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / 'data'
BATCH = 500


def _normalise_record(raw):
    """Eski ve yeni kayıt biçimini tek şekle indirir.

    Dönen: ``(rank, alanlar, {dil: {meaning, example_translation}})`` ya da
    zorunlu alan eksikse ``None``.
    """
    if not isinstance(raw, dict):
        return None

    rank = raw.get('rank')
    if not isinstance(rank, int):
        return None

    term = (raw.get('term') or raw.get('english') or '').strip()
    if not term:
        return None

    translations = {}
    raw_translations = raw.get('translations')
    if isinstance(raw_translations, dict):
        for code, entry in raw_translations.items():
            if isinstance(entry, dict):
                meaning = (entry.get('meaning') or '').strip()
                example_translation = (entry.get('example_translation') or '').strip()
            else:
                # Kısa biçim: {"tr": "kitap"}
                meaning, example_translation = str(entry or '').strip(), ''
            if meaning:
                translations[code] = {
                    'meaning': meaning[:400],
                    'example_translation': example_translation[:500],
                }
    else:
        # Eski düz biçim: turkish + example_tr
        meaning = (raw.get('turkish') or '').strip()
        if meaning:
            translations['tr'] = {
                'meaning': meaning[:400],
                'example_translation': (raw.get('example_tr') or '').strip()[:500],
            }

    # Hiçbir dilde karşılığı olmayan kayıt YÜKLENMİYOR: kullanıcıya boş
    # anlamla soru çıkarır, `export_content` de zaten "yüklenirken atlanacak"
    # diye uyarıyor. Tek bir dilde eksik olması ayrı mesele — o filtre
    # `pick_next` tarafında, ana dil başına.
    if not translations:
        return None

    extra = raw.get('extra')
    fields = {
        'term': term[:120],
        'part_of_speech': (raw.get('part_of_speech') or '').strip()[:40],
        'example': (raw.get('example') or raw.get('example_en') or '').strip()[:500],
        'extra': extra if isinstance(extra, dict) else {},
    }
    return rank, fields, translations


class Command(BaseCommand):
    help = 'Kelime hazinesini apps/wordbank/data/<dil>/<seviye>.json dosyalarından yükler.'

    def add_arguments(self, parser):
        parser.add_argument('--target', default=None,
                            help='Yalnızca bu hedef dili yükle (örn. de). '
                                 'Verilmezse sicildeki tüm diller.')
        parser.add_argument('--level', default=None,
                            help='Yalnızca bu seviyeyi yükle (örn. A1).')
        parser.add_argument('--data-dir', default=None,
                            help='Veri kökü (varsayılan: apps/wordbank/data).')
        parser.add_argument('--reset', action='store_true',
                            help='Yüklenen dilin mevcut kayıtlarını önce sil.')
        parser.add_argument('--prune', action='store_true',
                            help='Dosyada olmayan rank değerlerini sil.')
        parser.add_argument('--check', action='store_true',
                            help='Hiçbir şey yazmadan dosya↔DB farkını raporla.')
        parser.add_argument('--force-level', action='store_true',
                            help='Dil siciline kayıtlı olmayan seviyeleri de yükle '
                                 '(--level ile birlikte kullanılmalı). İçerik önce '
                                 'yüklenip kayıt sonra açılır.')

    def handle(self, *args, **opts):
        data_dir = Path(opts['data_dir']) if opts['data_dir'] else DEFAULT_DATA_DIR
        if not data_dir.exists():
            raise CommandError(f'veri dizini yok: {data_dir}')

        targets = [opts['target']] if opts['target'] else list(languages.LEARNABLE_CODES)
        only_level = (opts['level'] or '').upper() or None

        problems = []
        for target in targets:
            try:
                spec = languages.get(target)
            except languages.UnknownLanguage:
                raise CommandError(f'sicilde olmayan dil: {target}')
            problems += self._load_language(spec, data_dir, only_level, opts)

        if problems:
            for line in problems:
                self.stderr.write(self.style.ERROR(f'  {line}'))
            raise CommandError(f'{len(problems)} tutarsızlık bulundu.')

    # ---------------------------------------------------------------- dil

    def _load_language(self, spec, data_dir, only_level, opts):
        # Yeni düzen: data/<dil>/<seviye>.json. Eski düz düzene yalnızca
        # varsayılan dil için düşülüyor (dosyalar dönüştürülürken geçiş kolaylığı).
        nested = data_dir / spec.code
        flat_fallback = not nested.exists() and spec.code == 'en'
        source_dir = data_dir if flat_fallback else nested

        if not source_dir.exists():
            self.stdout.write(self.style.WARNING(
                f'{spec.code}: {source_dir} yok — atlandı.'
            ))
            return []

        if opts['reset'] and not opts['check']:
            deleted = BankWord.objects.filter(language=spec.code).delete()[0]
            self.stdout.write(self.style.WARNING(
                f'{spec.code}: {deleted} mevcut kayıt silindi.'
            ))

        problems = []
        levels_to_load = (
            [only_level] if (only_level and opts.get('force_level'))
            else spec.cefr_levels
        )
        for level in levels_to_load:
            if only_level and level != only_level:
                continue
            path = source_dir / f'{level.lower()}.json'
            if not path.exists():
                self.stdout.write(f'{spec.code}/{level}: dosya yok — atlandı.')
                continue
            problems += self._load_level(spec, level, path, opts)
        return problems

    # ------------------------------------------------------------- seviye

    def _load_level(self, spec, level, path, opts):
        try:
            raw_items = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            return [f'{spec.code}/{level}: bozuk JSON ({e})']
        if not isinstance(raw_items, list):
            return [f'{spec.code}/{level}: kök bir liste olmalı']

        records, skipped, seen_ranks, duplicates = [], 0, set(), []
        for raw in raw_items:
            parsed = _normalise_record(raw)
            if parsed is None:
                skipped += 1
                continue
            rank = parsed[0]
            if rank in seen_ranks:
                duplicates.append(rank)
                continue
            seen_ranks.add(rank)
            records.append(parsed)

        problems = []
        if duplicates:
            problems.append(
                f'{spec.code}/{level}: {len(duplicates)} yinelenen rank '
                f'(ilk örnekler: {duplicates[:5]}) — (language, level, rank) '
                'tekil olmak zorunda.'
            )

        if opts['check']:
            in_db = BankWord.objects.filter(language=spec.code, level=level).count()
            status = 'OK' if in_db == len(records) else 'FARK'
            self.stdout.write(
                f'{spec.code}/{level}: dosya {len(records)}, DB {in_db} — {status}'
            )
            if in_db != len(records):
                problems.append(
                    f'{spec.code}/{level}: dosyada {len(records)}, DB\'de {in_db} satır.'
                )
            return problems

        created, updated, pruned = self._write(spec, level, records, opts)

        in_db = BankWord.objects.filter(language=spec.code, level=level).count()
        self.stdout.write(
            f'{spec.code}/{level}: {created} yeni, {updated} güncel, '
            f'{skipped} atlandı, {pruned} silindi (DB: {in_db})'
        )

        # Eşitlik doğrulaması — eski yükleyicide olmadığı için 55 kayıtlık
        # kayıp aylarca fark edilmedi.
        if opts['prune'] and in_db != len(records):
            problems.append(
                f'{spec.code}/{level}: yükleme sonrası dosya {len(records)} != '
                f'DB {in_db}. Beklenmedik — veri kaybı olabilir.'
            )
        return problems

    @transaction.atomic
    def _write(self, spec, level, records, opts):
        created = updated = 0
        translation_rows = []

        for rank, fields, translations in records:
            word, was_created = BankWord.objects.update_or_create(
                language=spec.code, level=level, rank=rank, defaults=fields,
            )
            created += was_created
            updated += not was_created
            for code, entry in translations.items():
                translation_rows.append(BankWordTranslation(
                    word=word, language=code, **entry,
                ))

        # Çeviriler toplu upsert: 6k satırda satır bazlı yazım dakikalar sürüyor.
        for i in range(0, len(translation_rows), BATCH):
            BankWordTranslation.objects.bulk_create(
                translation_rows[i:i + BATCH],
                update_conflicts=True,
                unique_fields=['word', 'language'],
                update_fields=['meaning', 'example_translation'],
            )

        pruned = 0
        if opts['prune']:
            file_ranks = {rank for rank, _f, _t in records}
            stale = BankWord.objects.filter(
                language=spec.code, level=level,
            ).exclude(rank__in=file_ranks)
            pruned = stale.count()
            if pruned:
                self.stdout.write(self.style.WARNING(
                    f'{spec.code}/{level}: {pruned} satır dosyada yok, siliniyor.'
                ))
                stale.delete()

        return created, updated, pruned
