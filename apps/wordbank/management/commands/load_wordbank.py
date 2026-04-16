import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.wordbank.models import BankWord


class Command(BaseCommand):
    help = 'JSON fixture\'larından BankWord\'leri yükler (apps/wordbank/data/{a1,a2,b1}.json).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Önce tüm BankWord kayıtlarını sil.')

    def handle(self, *args, **opts):
        data_dir = Path(__file__).resolve().parent.parent.parent / 'data'

        if opts.get('reset'):
            count = BankWord.objects.count()
            BankWord.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'{count} mevcut kelime silindi.'))

        total_new = 0
        total_existing = 0
        for code in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            path = data_dir / f'{code.lower()}.json'
            if not path.exists():
                self.stdout.write(self.style.WARNING(f'{path} bulunamadı — atlandı.'))
                continue
            with open(path, encoding='utf-8') as f:
                items = json.load(f)
            new_count = 0
            existing_count = 0
            with transaction.atomic():
                for it in items:
                    _, created = BankWord.objects.get_or_create(
                        level=code,
                        english=it['english'],
                        part_of_speech=it.get('part_of_speech', ''),
                        defaults={
                            'rank': it['rank'],
                            'turkish': it['turkish'],
                            'example_en': it.get('example_en', ''),
                            'example_tr': it.get('example_tr', ''),
                        },
                    )
                    if created:
                        new_count += 1
                    else:
                        existing_count += 1
            total_new += new_count
            total_existing += existing_count
            self.stdout.write(f'{code}: {new_count} yeni, {existing_count} mevcut.')

        self.stdout.write(self.style.SUCCESS(
            f'Bitti. Toplam yeni: {total_new}, mevcut: {total_existing}.'
        ))
