"""Hedef dil ekseni ve dile özgü morfoloji alanı.

`language` için `default='en'` + `preserve_default=False`: mevcut 6.163 satırın
tamamı İngilizce, ama yeni satırlar dili açıkça vermek zorunda — sessizce
İngilizce'ye düşen bir Almanca kelime en kötü hata türü.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0005_rename_bankword_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankword',
            name='language',
            field=models.CharField(
                choices=[('tr', 'Türkçe'), ('en', 'English'),
                         ('fr', 'Français'), ('de', 'Deutsch')],
                db_index=True, default='en', max_length=5,
                verbose_name='Hedef dil',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='bankword',
            name='extra',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
