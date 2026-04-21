from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def backfill_trials(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    TrialUsage = apps.get_model('subscriptions', 'TrialUsage')
    days = getattr(settings, 'TRIAL_DAYS', 3)
    now = timezone.now()
    created = 0
    for user in User.objects.all():
        _, was_created = TrialUsage.objects.get_or_create(
            user=user,
            defaults={'trial_ends_at': now + timedelta(days=days)},
        )
        if was_created:
            created += 1
    print(f'  · {created} mevcut kullanıcıya {days} gün deneme tanımlandı.')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_trials, noop),
    ]
