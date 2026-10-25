"""Mülakat oturumlarına dil çifti.

Sorular hedef + ana dil çifti olarak üretiliyor; hangi çift olduğunu oturumun
kendisi taşımak zorunda, yoksa eski kayıtlar yeniden yorumlanamaz.
"""

from django.db import migrations, models

LANG_CHOICES = [('tr', 'Türkçe'), ('en', 'English'),
                ('fr', 'Français'), ('de', 'Deutsch')]


class Migration(migrations.Migration):

    dependencies = [
        ('interviews', '0004_interviewsession_error_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewsession', name='target_language',
            field=models.CharField(choices=LANG_CHOICES, db_index=True,
                                   default='en', max_length=5,
                                   verbose_name='Öğrenilen dil'),
        ),
        migrations.AddField(
            model_name='interviewsession', name='native_language',
            field=models.CharField(choices=LANG_CHOICES, default='tr',
                                   max_length=5, verbose_name='Anlatım dili'),
        ),
    ]
