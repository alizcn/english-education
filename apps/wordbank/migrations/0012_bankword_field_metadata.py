"""Alan etiketleri ve yardım metinleri (yalnızca durum, şema etkisi yok)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0011_drop_turkish_columns'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bankword',
            name='term',
            field=models.CharField(max_length=120, verbose_name='Terim'),
        ),
        migrations.AlterField(
            model_name='bankword',
            name='example',
            field=models.CharField(blank=True, max_length=500,
                                   verbose_name='Örnek cümle (hedef dilde)'),
        ),
        migrations.AlterField(
            model_name='bankword',
            name='rank',
            field=models.PositiveIntegerField(
                help_text='Kaynak listedeki sıra. Quiz ilerleyişini bu belirler.'),
        ),
    ]
