"""Ana dil tarafını ayrı tabloya alır.

Örnek cümle hedef dilde bir kez üretiliyor; yalnızca anlamı ve cümlenin
çevirisi ana dile göre değişiyor. Aynı satırda tutmak (meaning_tr/en/fr/de)
cümleyi her ana dil için yeniden üretmek demekti.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0006_bankword_language_extra'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankWordTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('language', models.CharField(
                    choices=[('tr', 'Türkçe'), ('en', 'English'),
                             ('fr', 'Français'), ('de', 'Deutsch')],
                    max_length=5, verbose_name='Ana dil')),
                ('meaning', models.CharField(max_length=400, verbose_name='Anlam')),
                ('example_translation', models.CharField(blank=True, max_length=500)),
                ('word', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='translations', to='wordbank.bankword')),
            ],
            options={'ordering': ['word', 'language']},
        ),
        migrations.AddConstraint(
            model_name='bankwordtranslation',
            constraint=models.UniqueConstraint(
                fields=('word', 'language'), name='unique_word_translation'),
        ),
        migrations.AddIndex(
            model_name='bankwordtranslation',
            index=models.Index(fields=['language'], name='wordtranslation_lang'),
        ),
    ]
