"""Her konu için varsayılan (user=None) seed quiz şablonunu yükler.

Kaynak: ``apps/quizzes/seeds/<slug>.json``

ESKİ SÜRÜMDEN ÜÇ FARK:

1. **`transaction.atomic()` var.** Eskiden yoktu: komut yarıda kesilirse
   kısmi yükleme kalıyordu.
2. **Konu bulunamazsa sessizce atlanmıyor**, sayılıp sonda uyarı veriliyor.
   Dosya adı ↔ `Topic.slug` eşleşmesi tutmazsa (üç seed hattının slug kümesi
   birebir aynı olmak zorunda) eskiden hiç fark edilmiyordu.
3. **Dil çifti yazılıyor** ve benzersizlik `(kind, topic, native_language)`
   üzerinden, yani aynı konunun Türkçe ve İngilizce anlatımlı seed quizleri
   yan yana yaşayabiliyor.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext as _

from apps.quizzes.models import QuizTemplate
from apps.quizzes.normalization import normalize_items
from apps.topics.models import Topic

DEFAULT_SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / 'seeds'


class Command(BaseCommand):
    help = 'Konu başına varsayılan seed quiz şablonlarını yükler.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Önce mevcut seed şablonları sil.')
        parser.add_argument('--target', default='en', help='Hedef dil kodu.')
        parser.add_argument('--native', default='tr', help='Anlatım dili kodu.')
        parser.add_argument('--seeds-dir', default=None,
                            help=f'Seed dizini (varsayılan: {DEFAULT_SEEDS_DIR}).')

    def handle(self, *args, **opts):
        seeds_dir = Path(opts['seeds_dir']) if opts['seeds_dir'] else DEFAULT_SEEDS_DIR
        target, native = opts['target'], opts['native']

        # Yeni düzen: seeds/<hedef>/<ana>/<slug>.json. Yoksa eski düz düzene
        # düşülüyor (dosyalar taşınırken geçiş kolaylığı).
        nested = seeds_dir / target / native
        source_dir = nested if nested.exists() else seeds_dir

        # `mono/` tamamen hedef dildeki sorular (fill_blank, multiple_choice):
        # ana dilden bağımsız oldukları için hedef dil başına BİR KEZ üretilip
        # her ana dile aynı dosyadan ekleniyor. Üretimi %33 azaltıyor.
        mono_dir = seeds_dir / target / 'mono'

        if not source_dir.exists() and not mono_dir.exists():
            self.stdout.write(self.style.ERROR(f'{source_dir} yok.'))
            return

        if opts['reset']:
            deleted = QuizTemplate.objects.filter(
                user__isnull=True, kind=QuizTemplate.TOPIC,
                target_language=target, native_language=native,
            ).delete()[0]
            self.stdout.write(self.style.WARNING(f'Silinen seed: {deleted}'))

        topics = {t.slug: t for t in Topic.objects.filter(language=target)}
        created = updated = empty = 0
        missing_topics = []

        # Slug kümesi iki kaynağın birleşimi: bir konu yalnızca mono sorulara
        # sahip olabilir (çeviri soruları henüz üretilmemişse).
        slugs = sorted(
            {p.stem for p in source_dir.glob('*.json')}
            | {p.stem for p in mono_dir.glob('*.json')}
        ) if source_dir.exists() or mono_dir.exists() else []

        with transaction.atomic():
            for slug in slugs:
                topic = topics.get(slug)
                if not topic:
                    missing_topics.append(slug)
                    continue

                raw = []
                for directory in (mono_dir, source_dir):
                    path = directory / f'{slug}.json'
                    if path.exists():
                        raw.extend(json.loads(path.read_text(encoding='utf-8')))

                items = normalize_items(raw)
                if not items:
                    self.stdout.write(self.style.WARNING(f'{slug}: boş, atlandı.'))
                    empty += 1
                    continue

                _obj, was_created = QuizTemplate.objects.update_or_create(
                    user=None,
                    kind=QuizTemplate.TOPIC,
                    topic=topic,
                    target_language=target,
                    native_language=native,
                    defaults={
                        'name': _('Varsayılan'),
                        'questions_data': items,
                        'status': QuizTemplate.READY,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Bitti ({target}<-{native}). Oluşturulan: {created}, '
            f'güncellenen: {updated}, boş: {empty}.'
        ))

        if missing_topics:
            # Sessiz atlama yok: slug kümeleri ayrışmışsa bunu bilmek gerekiyor.
            self.stdout.write(self.style.WARNING(
                f'{len(missing_topics)} seed dosyasının konusu yok '
                f'({target} dilinde): {", ".join(missing_topics[:10])}'
                f'{"..." if len(missing_topics) > 10 else ""}. '
                "Önce `seed_topics` koşun."
            ))
