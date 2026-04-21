from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.subscriptions.models import Plan


PLANS = [
    {
        'slug': 'monthly',
        'name': 'Aylık',
        'description': '30 gün sınırsız erişim',
        'price_try': Decimal('199.00'),
        'duration_days': 30,
        'is_popular': False,
        'sort_order': 10,
    },
    {
        'slug': 'quarterly',
        'name': '3 Aylık',
        'description': '90 gün sınırsız erişim · %17 indirim',
        'price_try': Decimal('499.00'),
        'duration_days': 90,
        'is_popular': True,
        'sort_order': 20,
    },
    {
        'slug': 'yearly',
        'name': 'Yıllık',
        'description': '365 gün sınırsız erişim · %37 indirim',
        'price_try': Decimal('1499.00'),
        'duration_days': 365,
        'is_popular': False,
        'sort_order': 30,
    },
]


class Command(BaseCommand):
    help = 'Levelenai abonelik paketlerini seed eder.'

    def handle(self, *args, **options):
        for data in PLANS:
            plan, created = Plan.objects.update_or_create(
                slug=data['slug'],
                defaults=data,
            )
            tag = 'oluşturuldu' if created else 'güncellendi'
            self.stdout.write(self.style.SUCCESS(f'{plan.name}: {tag}'))
        self.stdout.write(self.style.SUCCESS(f'Toplam {Plan.objects.count()} paket aktif.'))
