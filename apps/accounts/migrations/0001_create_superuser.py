"""Süper kullanıcı oluşturma buradan 0004'e taşındı — no-op.

Buradaki RunPython, accounts_userlevel tablosunu kuran 0002_initial'dan önce
kullanıcı yaratıyordu; post_save sinyali o tabloya yazmaya çalışınca sıfırdan
kurulan her veritabanı migrate sırasında `no such table` ile düşüyordu.
Gerçek oluşturma artık 0004_create_superuser_after_tables içinde.

Migration adı geçmişte kayıtlı olduğu için dosya duruyor; içeriği boşaltıldı.
"""

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = []
