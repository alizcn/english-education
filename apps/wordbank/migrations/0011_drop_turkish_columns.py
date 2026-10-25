"""Eski Türkçe sütunlarını siler.

Veri 0008'de `BankWordTranslation`a kopyalandı. Bu migration bilinçli olarak
zincirin en sonunda: 0008 ile burası arasında kalan pencerede iki temsil yan
yana duruyor, dolayısıyla üretimde geri alma yalnızca kodu revert etmekle
yapılabiliyor.

Üretime alırken 0008..0010 ile 0011 arasına en az bir deploy bırakın.

GERİ ALINABİLİR — ama iki adımda: silmeden önce alanlara `default=''`
veriliyor, çünkü `RemoveField`in tersi `AddField` ve varsayılanı olmayan bir
NOT NULL sütun geri eklenemiyor ("NOT NULL constraint failed"). Sütunlar boş
olarak geri gelir, içeriği 0008'in ters fonksiyonu doldurur.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0010_bankword_constraints'),
    ]

    operations = [
        # Ters yönün sütunu geri ekleyebilmesi için varsayılan şart.
        migrations.AlterField(
            model_name='bankword',
            name='turkish',
            field=models.CharField(blank=True, default='', max_length=400),
        ),
        migrations.AlterField(
            model_name='bankword',
            name='example_tr',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.RemoveField(model_name='bankword', name='turkish'),
        migrations.RemoveField(model_name='bankword', name='example_tr'),
    ]
