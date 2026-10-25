"""Seed quiz dosyalarını yazmadan denetler — KALİTE KAPISI.

Niçin gerekli: seed soruların büyük bölümü AI üretimi. Bozuk bir soru sessizce
yayına girip kullanıcıya yanlış cevabı doğru saydırıyor, ve bu veri
`QuizTemplate.questions_data` içinde JSON olarak yaşadığı için şema
doğrulaması yapmıyor. Ölçülmüş invariantlar burada zorunlu kılınıyor.

Denetimler:

* `multiple_choice` tam 4 şık, şıklar boş değil, `correct_answer` şıklardan
  BİRİNİN birebir metni (model bazen "A" yazıyor), şıklar yinelenmiyor.
* `multiple_choice` dışındaki tiplerde `choices` null.
* `fill_blank` prompt'unda `___` var — yoksa boşluk doldurulacak yer belli
  değil ve soru cevaplanamıyor.
* Soru tipi geçerli enum değeri. Eski `translate_en_tr`/`translate_tr_en`
  isimleri AYRICA raporlanıyor: dönüşüm atlanmış demek.
* Konu başına soru sayısı bandı ve tip dengesi.
* Aynı prompt konu içinde yinelenmiyor.
* Dosya adı ↔ `Topic.slug` eşleşmesi (`seed_quizzes` eşleşmeyeni sessizce
  atlıyor).

Kullanım::

    manage.py validate_quiz_seeds --target de
    manage.py validate_quiz_seeds            # sicildeki tüm diller
"""

import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.quizzes.models import QuizQuestion
from apps.topics.models import Topic
from services import languages

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / 'seeds'

#: Konu başına beklenen soru sayısı. Alt sınır: daha azı quiz hissi vermiyor.
#: Üst sınır: fazlası tek oturumda bitirilemiyor ve `questions_data` şişiyor.
MIN_PER_TOPIC = 30
MAX_PER_TOPIC = 60

#: Tip dengesi toleransı. Tek tipe yığılmış quiz tek beceriyi ölçüyor.
MAX_TYPE_SHARE = 0.70

MC = 'multiple_choice'
FILL = 'fill_blank'

#: Dönüşümü atlanmış dosyaların işareti.
LEGACY_TYPES = {'translate_en_tr', 'translate_tr_en'}


class Command(BaseCommand):
    help = 'Seed quiz dosyalarını denetler (yazmaz).'

    def add_arguments(self, parser):
        parser.add_argument('--target', default=None,
                            help='Yalnızca bu hedef dil.')
        parser.add_argument('--seeds-dir', default=None)
        parser.add_argument('--strict', action='store_true',
                            help='Uyarıları da hata say.')

    def handle(self, *args, **opts):
        seeds_dir = (Path(opts['seeds_dir']) if opts['seeds_dir']
                     else SEEDS_DIR)
        valid_types = {value for value, _label in QuizQuestion.TYPE_CHOICES}

        targets = ([opts['target']] if opts['target']
                   else list(languages.LEARNABLE_CODES))
        for code in targets:
            try:
                languages.get(code)
            except languages.UnknownLanguage:
                raise CommandError(f'sicilde olmayan dil: {code}')

        errors, warnings = [], []
        checked_files = checked_items = 0

        for code in targets:
            lang_dir = seeds_dir / code
            buckets = []
            if lang_dir.exists():
                buckets = [d for d in sorted(lang_dir.iterdir()) if d.is_dir()]
            elif code == 'en':
                # Eski düz düzen: seeds/<slug>.json
                buckets = [seeds_dir]
            if not buckets:
                self.stdout.write(f'{code}: seed dizini yok — atlandı.')
                continue

            db_slugs = set(
                Topic.objects.filter(language=code)
                .values_list('slug', flat=True)
            )

            # Mono + ana dil kovaları BİRLEŞTİRİLEREK sayılıyor: kullanıcıya
            # giden quiz ikisinin toplamı, bant kontrolü de o toplam üzerinde
            # anlamlı.
            per_slug = {}
            for bucket in buckets:
                for path in sorted(bucket.glob('*.json')):
                    checked_files += 1
                    try:
                        items = json.loads(path.read_text(encoding='utf-8'))
                    except json.JSONDecodeError as exc:
                        errors.append(f'{path}: bozuk JSON ({exc})')
                        continue
                    if not isinstance(items, list):
                        errors.append(f'{path}: kök öğe liste değil')
                        continue
                    checked_items += len(items)
                    file_errors = self._check_items(path, items, valid_types)
                    errors.extend(file_errors)
                    key = (code, bucket.name, path.stem)
                    per_slug.setdefault(key, []).extend(items)

            # Bant ve denge: mono kovası tek başına bandı tutmaz, ana dil
            # kovasıyla toplanıyor.
            merged = {}
            for (lang, bucket_name, slug), items in per_slug.items():
                if bucket_name == 'mono':
                    continue
                mono = per_slug.get((lang, 'mono', slug), [])
                merged[(lang, bucket_name, slug)] = items + mono
            if not merged:
                merged = {k: v for k, v in per_slug.items()}

            for (lang, bucket_name, slug), items in sorted(merged.items()):
                label = f'{lang}/{bucket_name}/{slug}'
                count = len(items)
                if count < MIN_PER_TOPIC:
                    warnings.append(
                        f'{label}: {count} soru, en az {MIN_PER_TOPIC} bekleniyor'
                    )
                elif count > MAX_PER_TOPIC:
                    warnings.append(
                        f'{label}: {count} soru, üst sınır {MAX_PER_TOPIC}'
                    )
                if count:
                    share = Counter(
                        i.get('question_type') for i in items
                    ).most_common(1)[0]
                    if share[1] / count > MAX_TYPE_SHARE:
                        warnings.append(
                            f'{label}: soruların %{share[1] * 100 // count}\'i '
                            f'{share[0]} — tek beceri ölçülüyor'
                        )
                prompts = Counter(
                    (i.get('prompt') or '').strip().lower() for i in items
                )
                dupes = [p for p, n in prompts.items() if n > 1 and p]
                if dupes:
                    errors.append(
                        f'{label}: {len(dupes)} yinelenen prompt '
                        f'({dupes[0][:40]!r})'
                    )
                if db_slugs and slug not in db_slugs:
                    warnings.append(
                        f'{label}: bu slug {lang} konularında yok — '
                        'seed_quizzes SESSİZCE atlar'
                    )

        for line in warnings:
            self.stdout.write(self.style.WARNING(f'UYARI {line}'))
        for line in errors:
            self.stdout.write(self.style.ERROR(f'HATA  {line}'))

        if errors or (opts['strict'] and warnings):
            raise CommandError(
                f'{len(errors)} hata, {len(warnings)} uyarı '
                f'({checked_files} dosya, {checked_items} soru).'
            )
        self.stdout.write(self.style.SUCCESS(
            f'Seed quizler temiz ({checked_files} dosya, {checked_items} soru, '
            f'{len(warnings)} uyarı).'
        ))

    # ------------------------------------------------------------ öğe kontrolü

    @staticmethod
    def _check_items(path, items, valid_types):
        problems = []
        for index, item in enumerate(items):
            where = f'{path.parent.name}/{path.stem}[{index}]'
            if not isinstance(item, dict):
                problems.append(f'{where}: öğe sözlük değil')
                continue

            qtype = item.get('question_type')
            prompt = (item.get('prompt') or '').strip()
            answer = (item.get('correct_answer') or '').strip()
            choices = item.get('choices')

            if qtype in LEGACY_TYPES:
                problems.append(
                    f'{where}: eski tip {qtype!r} — soru tipi dönüşümü '
                    'bu dosyada koşmamış'
                )
                continue
            if qtype not in valid_types:
                problems.append(f'{where}: geçersiz tip {qtype!r}')
                continue
            if not prompt:
                problems.append(f'{where}: prompt boş')
            if not answer:
                problems.append(f'{where}: correct_answer boş')

            if qtype == MC:
                if not isinstance(choices, list):
                    problems.append(f'{where}: choices liste değil')
                    continue
                if len(choices) != 4:
                    problems.append(
                        f'{where}: {len(choices)} şık, tam 4 olmalı'
                    )
                texts = [str(c).strip() for c in choices]
                if any(not t for t in texts):
                    problems.append(f'{where}: boş şık')
                if len(set(texts)) != len(texts):
                    problems.append(f'{where}: yinelenen şık')
                if answer and answer not in texts:
                    problems.append(
                        f'{where}: correct_answer şıklar arasında yok '
                        f'({answer[:30]!r})'
                    )
            elif choices is not None:
                problems.append(
                    f'{where}: {qtype} için choices null olmalı'
                )

            if qtype == FILL and '___' not in prompt:
                problems.append(f'{where}: fill_blank prompt\'unda "___" yok')

        return problems
