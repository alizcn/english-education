"""Eski benzersizlik kısıtını kaldırır.

`(level, english, part_of_speech)` anahtarı, `part_of_speech` kaynak veride %90
boş olduğu için çok anlamlı kelimeleri tek satıra çöküyordu: JSON'daki 6.218
kaydın 55'i veritabanına hiç girmiyordu. Yeni anahtar `(language, level, rank)`
ve 0010'da ekleniyor.

Alan yeniden adlandırmadan ÖNCE kaldırılıyor: kısıt eski alan adlarına atıfta
bulunuyor, önce rename yapılırsa Django kısıtı yeniden kurmaya çalışıp düşüyor.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0003_purge_empty_turkish'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='bankword',
            name='unique_bank_word',
        ),
    ]
