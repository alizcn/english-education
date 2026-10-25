"""Eski anlatım ve çeviri sütunlarını siler.

Veri 0004'te taşındı. Üretime alırken 0004..0005 ile burası arasına en az bir
deploy bırakın: o pencerede iki temsil yan yana durduğu için geri alma yalnızca
kodu revert etmekle yapılabiliyor.

GERİ ALINABİLİR — silmeden önce alanlara varsayılan veriliyor, çünkü
`RemoveField`in tersi `AddField` ve varsayılanı olmayan bir NOT NULL sütun
geri eklenemiyor. Sütunlar boş gelir, içeriği 0004'ün ters fonksiyonu doldurur.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0005_topicexample_order_constraint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='topic',
            name='explanation',
            field=models.TextField(blank=True, default='',
                                   verbose_name='Konu anlatımı (TR)'),
        ),
        migrations.AlterField(
            model_name='topic',
            name='explanation_en',
            field=models.TextField(blank=True, default='',
                                   verbose_name='Konu anlatımı (EN)'),
        ),
        migrations.AlterField(
            model_name='topicexample',
            name='sentence_tr',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.RemoveField(model_name='topic', name='explanation'),
        migrations.RemoveField(model_name='topic', name='explanation_en'),
        migrations.RemoveField(model_name='topicexample', name='sentence_tr'),
    ]
