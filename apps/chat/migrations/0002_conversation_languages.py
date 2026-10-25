"""Sohbetlere dil çifti.

Öğretmen rolü hedef dile, düzeltme açıklamaları ana dile göre kuruluyor.
"""

from django.db import migrations, models

LANG_CHOICES = [('tr', 'Türkçe'), ('en', 'English'),
                ('fr', 'Français'), ('de', 'Deutsch')]


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation', name='target_language',
            field=models.CharField(choices=LANG_CHOICES, db_index=True,
                                   default='en', max_length=5,
                                   verbose_name='Öğrenilen dil'),
        ),
        migrations.AddField(
            model_name='chatconversation', name='native_language',
            field=models.CharField(choices=LANG_CHOICES, default='tr',
                                   max_length=5, verbose_name='Anlatım dili'),
        ),
    ]
