"""Abonelik/ödeme sisteminin veritabanı artıklarını temizler.

`apps.subscriptions` uygulaması tamamen kaldırıldı (platform ücretsiz). Django
artık bu tabloları tanımadığı için:

  * `subscriptions_*` tabloları auth_user'a FK tutmaya devam eder ve SQLite'ın
    FK zorlaması yüzünden kullanıcı silme işlemini kırar,
  * celery beat, artık var olmayan `expire_subscriptions_task` görevini
    çalıştırmayı dener.

Bu migration ikisini de temizler. Tümü idempotent — temiz kurulumda hiçbir şey
bulamaz ve sessizce geçer. Kaldırılan verinin JSON yedeği:
data/backups/subscriptions-data-2026-08-02.json
"""
from django.db import migrations


PERIODIC_TASK_NAME = 'expire-subscriptions-daily'
TABLES = (
    # Önce FK ile bağımlı olanlar.
    'subscriptions_payment',
    'subscriptions_subscription',
    'subscriptions_trialusage',
    'subscriptions_plan',
)


def cleanup(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        pass
    else:
        PeriodicTask.objects.filter(name=PERIODIC_TASK_NAME).delete()

    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    ct_ids = list(
        ContentType.objects.filter(app_label='subscriptions').values_list('id', flat=True)
    )
    if ct_ids:
        Permission.objects.filter(content_type_id__in=ct_ids).delete()
        ContentType.objects.filter(id__in=ct_ids).delete()

    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f'DROP TABLE IF EXISTS {table}')
        cursor.execute("DELETE FROM django_migrations WHERE app = 'subscriptions'")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        # Geri alınamaz: tablolar ve kayıtlar kalıcı olarak düşürülür.
        migrations.RunPython(cleanup, migrations.RunPython.noop),
    ]
