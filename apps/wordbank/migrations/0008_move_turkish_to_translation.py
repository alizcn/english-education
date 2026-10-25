"""Mevcut Türkçe anlamları `BankWordTranslation`a taşır.

Yalnızca VERİ taşır; eski sütunlar 0011'e kadar yerinde kalıyor. Aradaki
pencere bilinçli: o aralıkta kod yeni tablodan okuyor ama eski sütunlar hâlâ
durduğu için geri alma kod revert'iyle yapılabiliyor.

Tersine alınabilir: geri yönde çeviriler eski sütunlara yazılıyor.
"""

from django.db import migrations

BATCH = 500


def forwards(apps, schema_editor):
    BankWord = apps.get_model('wordbank', 'BankWord')
    Translation = apps.get_model('wordbank', 'BankWordTranslation')

    rows = []
    qs = BankWord.objects.exclude(turkish='').only('id', 'turkish', 'example_tr')
    for word in qs.iterator(chunk_size=BATCH):
        rows.append(Translation(
            word_id=word.id,
            language='tr',
            meaning=(word.turkish or '').strip()[:400],
            example_translation=(word.example_tr or '').strip()[:500],
        ))
        if len(rows) >= BATCH:
            Translation.objects.bulk_create(rows, ignore_conflicts=True)
            rows = []
    if rows:
        Translation.objects.bulk_create(rows, ignore_conflicts=True)


def backwards(apps, schema_editor):
    BankWord = apps.get_model('wordbank', 'BankWord')
    Translation = apps.get_model('wordbank', 'BankWordTranslation')

    updates = []
    for tr in Translation.objects.filter(language='tr').select_related('word').iterator(
        chunk_size=BATCH
    ):
        word = tr.word
        word.turkish = tr.meaning
        word.example_tr = tr.example_translation
        updates.append(word)
        if len(updates) >= BATCH:
            BankWord.objects.bulk_update(updates, ['turkish', 'example_tr'])
            updates = []
    if updates:
        BankWord.objects.bulk_update(updates, ['turkish', 'example_tr'])
    Translation.objects.filter(language='tr').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0007_create_bankwordtranslation'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
