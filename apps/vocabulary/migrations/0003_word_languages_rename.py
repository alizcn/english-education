"""Kişisel kelimelere dil ekseni; alan adlarından dil çıkıyor.

`english`→`term`, `turkish`→`meaning`, `example_en`→`example`,
`example_tr`→`example_translation`. Benzersizlik `(user, english)`ten
`(user, target_language, term)`a geçiyor: aynı terim iki kursta ayrı satır
olabilmeli (Almanca "Buch" ve İngilizce "book" ayrı, ama "die" kelimesi hem
İngilizce hem Almanca listede bulunabilir).
"""

from django.db import migrations, models

LANG_CHOICES = [('tr', 'Türkçe'), ('en', 'English'),
                ('fr', 'Français'), ('de', 'Deutsch')]


class Migration(migrations.Migration):

    dependencies = [
        ('vocabulary', '0002_word_mastered'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='word', name='unique_user_english',
        ),
        migrations.RenameField(model_name='word', old_name='english', new_name='term'),
        migrations.RenameField(model_name='word', old_name='turkish', new_name='meaning'),
        migrations.RenameField(model_name='word', old_name='example_en', new_name='example'),
        migrations.RenameField(
            model_name='word', old_name='example_tr', new_name='example_translation',
        ),
        migrations.AddField(
            model_name='word',
            name='target_language',
            field=models.CharField(choices=LANG_CHOICES, db_index=True,
                                   default='en', max_length=5,
                                   verbose_name='Öğrenilen dil'),
        ),
        migrations.AddField(
            model_name='word',
            name='native_language',
            field=models.CharField(choices=LANG_CHOICES, default='tr',
                                   max_length=5, verbose_name='Anlatım dili'),
        ),
        migrations.AlterField(
            model_name='word', name='term',
            field=models.CharField(max_length=120, verbose_name='Terim'),
        ),
        migrations.AlterField(
            model_name='word', name='meaning',
            field=models.CharField(max_length=200, verbose_name='Anlam'),
        ),
        migrations.AddConstraint(
            model_name='word',
            constraint=models.UniqueConstraint(
                fields=('user', 'target_language', 'term'),
                name='unique_user_target_term'),
        ),
    ]
