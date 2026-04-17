import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.quizzes.models import QuizTemplate
from apps.quizzes.normalization import normalize_items
from apps.topics.models import Topic


class Command(BaseCommand):
    help = 'Her konu için varsayılan (user=None) seed quiz şablonunu apps/quizzes/seeds/<slug>.json üzerinden yükler.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Önce mevcut seed şablonları sil.')

    def handle(self, *args, **opts):
        seeds_dir = Path(__file__).resolve().parent.parent.parent / 'seeds'
        if not seeds_dir.exists():
            self.stdout.write(self.style.ERROR(f'{seeds_dir} yok.'))
            return

        if opts.get('reset'):
            deleted = QuizTemplate.objects.filter(user__isnull=True, kind=QuizTemplate.TOPIC).delete()
            self.stdout.write(self.style.WARNING(f'Silinen seed: {deleted}'))

        topics = {t.slug: t for t in Topic.objects.all()}
        created = 0
        updated = 0
        skipped = 0
        for path in sorted(seeds_dir.glob('*.json')):
            slug = path.stem
            topic = topics.get(slug)
            if not topic:
                self.stdout.write(self.style.WARNING(f'{slug}: topic yok, atlandı.'))
                skipped += 1
                continue
            items = json.loads(path.read_text(encoding='utf-8'))
            items = normalize_items(items)
            if not items:
                self.stdout.write(self.style.WARNING(f'{slug}: boş, atlandı.'))
                skipped += 1
                continue
            obj, was_created = QuizTemplate.objects.update_or_create(
                user=None,
                kind=QuizTemplate.TOPIC,
                topic=topic,
                defaults={
                    'name': 'Varsayılan',
                    'questions_data': items,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f'{slug}: oluşturuldu ({len(items)} soru)')
            else:
                updated += 1
                self.stdout.write(f'{slug}: güncellendi ({len(items)} soru)')
        self.stdout.write(self.style.SUCCESS(
            f'Bitti. Oluşturulan: {created}, güncellenen: {updated}, atlanan: {skipped}.'
        ))
