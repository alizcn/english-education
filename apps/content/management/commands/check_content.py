"""İçerik kalite kapısı — yayın öncesi zorunlu adım.

Dört hedef dil × altı seviye × üç ana dil ölçeğinde içerik gözle denetlenemez.
Bu komut ölçülebilir invariantları zorluyor:

* **Üç seed hattının slug kümesi birebir aynı.** `topics.json`, anlatım
  dosyaları ve `seeds/*.json` ayrışırsa `seed_quizzes` dosyayı SESSİZCE
  atlıyordu — artık burada görünüyor.
* **Alan uzunlukları modele sığıyor.** Taşan metin arayüzü bozuyor.
* **Çeviri eksikliği raporlanıyor** — hangi (hedef, ana dil) çiftinde kaç
  kelime anlamsız.
* **Terim biçimi tutarlı.** Mevcut C2 verisi büyük harfle başlıyor
  (`Abiding`) ve Türkçe karşılıkları karşılık değil İngilizce tanımın
  çevirisi — yeni diller aynı hattan geçeceği için bu kapı şart.
* **Anlatımlarda en az bir `##` başlık** var: markdown konvansiyonunun
  karşılığı (bkz. `apps/topics/markup.py`).
"""

import json
import re
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.topics.models import Topic
from apps.wordbank.models import BankWord
from services import languages

WORDBANK_DIR = Path(__file__).resolve().parents[3] / 'wordbank' / 'data'
QUIZ_SEEDS_DIR = Path(__file__).resolve().parents[3] / 'quizzes' / 'seeds'

LIMITS = {'term': 120, 'part_of_speech': 40, 'example': 500,
          'meaning': 400, 'example_translation': 500}

#: Karşılık yerine TANIM yazılmış kayıtlar. Yakalanmak istenen gerçek hata
#: eski C2 verisiydi: `abiding → "Devam ediyor; uzun süre devam ediyor."` —
#: İngilizce tanımın makine çevirisi, karşılık değil.
#:
#: `^to\s` kalıbı buradan ÇIKARILDI: İngilizce'de fiilin karşılığı zaten
#: mastarla yazılıyor (`enfoncer → "to drive in; to push down"` DOĞRU bir
#: karşılık) ve kural Fransızca B2'de 1033 sağlam kaydı yanlışlıkla
#: işaretliyordu. Kalan iki sinyal ayırt edici:
#:
#: * açıkça tanımsal açılış ("the act of", "a person who"),
#: * karşılığın CÜMLE olması — büyük harfle başlayıp nokta ile bitmesi.
#:   Karşılık listesi böyle yazılmaz; tanım çevirisi böyle yazılır.
_DEFINITION_LIKE = re.compile(
    r'^(the\s(act|state|quality|fact)\s|a\s(person|thing|place)\s(who|that)\b)',
    re.IGNORECASE,
)
_SENTENCE_LIKE = re.compile(r'^[^\Wa-z\d_]\S*(\s+\S+){2,}\s*\.$')


def looks_like_definition(meaning: str) -> bool:
    """Karşılık yerine tanım yazılmış mı?"""
    meaning = (meaning or '').strip()
    if not meaning:
        return False
    return bool(_DEFINITION_LIKE.match(meaning)
                or _SENTENCE_LIKE.match(meaning))


class Command(BaseCommand):
    help = 'İçerik invariantlarını denetler (slug senkronu, uzunluklar, eksikler).'

    def add_arguments(self, parser):
        parser.add_argument('--target', default=None,
                            help='Yalnızca bu hedef dil. Verilmezse hepsi.')
        parser.add_argument('--strict', action='store_true',
                            help='Uyarıları da hata say (eksik çeviri, biçim).')

    def handle(self, *args, **opts):
        targets = ([opts['target']] if opts['target']
                   else list(languages.LEARNABLE_CODES))
        errors, warnings = [], []

        for target in targets:
            try:
                spec = languages.get(target)
            except languages.UnknownLanguage:
                raise CommandError(f'sicilde olmayan dil: {target}')
            e, w = self._check_language(spec)
            errors += e
            warnings += w

        for line in warnings:
            self.stdout.write(self.style.WARNING(f'  UYARI  {line}'))
        for line in errors:
            self.stdout.write(self.style.ERROR(f'  HATA   {line}'))

        if errors or (opts['strict'] and warnings):
            raise CommandError(
                f'{len(errors)} hata, {len(warnings)} uyarı bulundu.'
            )
        self.stdout.write(self.style.SUCCESS(
            f'İçerik temiz ({len(warnings)} uyarı).'
        ))

    # ------------------------------------------------------------------ dil

    def _check_language(self, spec):
        errors, warnings = [], []
        errors += self._check_slug_sync(spec)
        e, w = self._check_wordbank_files(spec)
        errors += e
        warnings += w
        warnings += self._check_translation_coverage(spec)
        warnings += self._check_explanations(spec)
        return errors, warnings

    def _check_slug_sync(self, spec):
        """Üç seed hattının slug kümesi birebir aynı olmak zorunda."""
        db_slugs = set(
            Topic.objects.filter(language=spec.code).values_list('slug', flat=True)
        )
        if not db_slugs:
            return []

        seed_dir = QUIZ_SEEDS_DIR / spec.code
        if not seed_dir.exists():
            seed_dir = QUIZ_SEEDS_DIR if spec.code == 'en' else None
        seed_slugs = (
            {p.stem for p in seed_dir.glob('*.json')} if seed_dir else set()
        )
        if not seed_slugs:
            return []

        only_db = db_slugs - seed_slugs
        only_seed = seed_slugs - db_slugs
        problems = []
        if only_seed:
            problems.append(
                f'{spec.code}: {len(only_seed)} seed dosyasının konusu yok '
                f'({sorted(only_seed)[:5]}) — seed_quizzes bunları SESSİZCE atlar.'
            )
        if only_db:
            self.stdout.write(
                f'{spec.code}: {len(only_db)} konunun seed quizi yok '
                f'({sorted(only_db)[:5]}).'
            )
        return problems

    def _check_wordbank_files(self, spec):
        errors, warnings = [], []
        lang_dir = WORDBANK_DIR / spec.code
        if not lang_dir.exists():
            return errors, warnings

        for level in spec.cefr_levels:
            path = lang_dir / f'{level.lower()}.json'
            if not path.exists():
                continue
            try:
                items = json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                errors.append(f'{spec.code}/{level}: bozuk JSON ({e})')
                continue

            ranks = Counter()
            capitalised = definition_like = no_pos = 0
            for item in items:
                rank = item.get('rank')
                if not isinstance(rank, int):
                    errors.append(f'{spec.code}/{level}: rank tamsayı değil: {item}')
                    continue
                ranks[rank] += 1

                term = (item.get('term') or '').strip()
                if not term:
                    errors.append(f'{spec.code}/{level}: rank {rank} terimsiz')
                    continue

                # Uzunluk kapısı
                for field, limit in LIMITS.items():
                    value = item.get(field)
                    if isinstance(value, str) and len(value) > limit:
                        errors.append(
                            f'{spec.code}/{level} {term}: {field} '
                            f'{len(value)} karakter, sınır {limit}'
                        )

                # Biçim: diğer seviyeler küçük harf, C2 büyük harfle başlıyor
                if term[:1].isupper() and term.lower() != term and ' ' not in term:
                    capitalised += 1

                if not (item.get('part_of_speech') or '').strip():
                    no_pos += 1

                for code, entry in (item.get('translations') or {}).items():
                    meaning = (entry or {}).get('meaning', '') if isinstance(entry, dict) else str(entry)
                    if looks_like_definition(meaning):
                        definition_like += 1

            duplicates = [r for r, n in ranks.items() if n > 1]
            if duplicates:
                errors.append(
                    f'{spec.code}/{level}: yinelenen rank {duplicates[:5]} — '
                    '(language, level, rank) tekil olmak zorunda.'
                )

            total = max(len(items), 1)
            if capitalised > total * 0.5:
                warnings.append(
                    f'{spec.code}/{level}: {capitalised}/{total} terim büyük '
                    'harfle başlıyor — diğer seviyelerle tutarsız '
                    '(mevcut C2 verisinin bilinen sorunu).'
                )
            if definition_like > total * 0.2:
                warnings.append(
                    f'{spec.code}/{level}: {definition_like}/{total} karşılık '
                    'tanım gibi görünüyor (karşılık değil İngilizce tanımın '
                    'çevirisi) — mevcut C2 verisinin bilinen sorunu.'
                )
            if no_pos > total * 0.5:
                warnings.append(
                    f'{spec.code}/{level}: {no_pos}/{total} kayıtta '
                    'part_of_speech boş.'
                )
        return errors, warnings

    def _check_translation_coverage(self, spec):
        """Hangi (hedef, ana dil) çiftinde kaç kelime anlamsız?"""
        total = BankWord.objects.filter(language=spec.code).count()
        if not total:
            return []
        warnings = []
        for native in languages.UI_CODES:
            if native == spec.code:
                continue
            covered = BankWord.objects.filter(
                language=spec.code, translations__language=native,
            ).exclude(translations__meaning='').distinct().count()
            if covered < total:
                warnings.append(
                    f'{spec.code}<-{native}: {total - covered}/{total} kelimenin '
                    'anlamı eksik.'
                )
        return warnings

    def _check_explanations(self, spec):
        """Anlatımlar markdown konvansiyonuna uyuyor mu?"""
        warnings = []
        topics = Topic.objects.filter(language=spec.code).prefetch_related(
            'explanations',
        )
        for topic in topics:
            languages_present = set()
            for explanation in topic.explanations.all():
                languages_present.add(explanation.language)
                if '##' not in explanation.body:
                    warnings.append(
                        f'{spec.code}/{topic.slug} [{explanation.language}]: '
                        'hiç `##` başlık yok — tüm metin başlıksız blok olarak '
                        'render edilir.'
                    )
            for native in languages.UI_CODES:
                if native != spec.code and native not in languages_present:
                    warnings.append(
                        f'{spec.code}/{topic.slug}: {native} anlatımı yok.'
                    )
        return warnings
