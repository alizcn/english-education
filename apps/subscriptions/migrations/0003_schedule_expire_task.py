from django.db import migrations


TASK_NAME = 'expire-subscriptions-daily'
TASK_PATH = 'apps.subscriptions.tasks.expire_subscriptions_task'


def create_schedule(apps, schema_editor):
    try:
        CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        return

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute='0',
        hour='3',
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
        defaults={'timezone': 'Europe/Istanbul'},
    )
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            'task': TASK_PATH,
            'crontab': schedule,
            'enabled': True,
            'description': 'Süresi dolmuş abonelikleri günde 1 STATUS_EXPIRED yap.',
        },
    )


def remove_schedule(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        return
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0002_backfill_trials'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
