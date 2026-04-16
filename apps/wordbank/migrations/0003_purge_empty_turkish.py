from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    BankWord = apps.get_model('wordbank', 'BankWord')
    empty = BankWord.objects.filter(Q(turkish='') | Q(turkish__isnull=True))
    count = empty.count()
    empty.delete()
    if count:
        print(f'  wordbank: removed {count} BankWord rows with empty turkish')


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('wordbank', '0002_alter_bankword_level'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
