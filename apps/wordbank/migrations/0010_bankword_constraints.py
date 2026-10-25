"""Yeni benzersizlik kısıtı ve okuma yollarının indeksleri."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0009_check_rank_uniqueness'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bankword',
            options={'ordering': ['language', 'level', 'rank']},
        ),
        migrations.AddConstraint(
            model_name='bankword',
            constraint=models.UniqueConstraint(
                fields=('language', 'level', 'rank'), name='unique_bank_word_rank'),
        ),
        migrations.AddIndex(
            model_name='bankword',
            index=models.Index(fields=['language', 'level', 'term'],
                               name='bankword_lang_level_term'),
        ),
        migrations.AddIndex(
            model_name='bankword',
            index=models.Index(fields=['language', 'level', 'rank'],
                               name='bankword_lang_level_rank'),
        ),
    ]
