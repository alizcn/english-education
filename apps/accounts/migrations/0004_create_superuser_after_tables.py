"""Süper kullanıcıyı UserLevel tablosu oluştuktan sonra yaratır.

0001_create_superuser bunu 0002_initial'dan önce yapıyordu: kullanıcı kaydı
post_save sinyalini tetikliyor, sinyal de henüz var olmayan accounts_userlevel
tablosuna yazmaya çalışıp `no such table` ile patlıyordu. Sıfırdan kurulan her
veritabanı (test DB'si ve yeni deploy dahil) migrate aşamasında düşüyordu.

Zaten migrate edilmiş veritabanlarında 0001 uygulanmış sayıldığı için bir şey
değişmez; bu migration çalışır, kullanıcı mevcut olduğu için erken döner.
"""

import os

from django.conf import settings
from django.db import migrations

DEFAULT_USERNAME = 'admin'
DEFAULT_EMAIL = '93.aliozcan@gmail.com'
DEFAULT_PASSWORD = 'Admin2026!'


def create_superuser(apps, schema_editor):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', DEFAULT_USERNAME)
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', DEFAULT_EMAIL)
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', DEFAULT_PASSWORD)

    if User.objects.filter(username=username).exists():
        return

    User.objects.create_superuser(username=username, email=email, password=password)


def remove_superuser(apps, schema_editor):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', DEFAULT_USERNAME)
    User.objects.filter(username=username, is_superuser=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_drop_subscriptions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_superuser, remove_superuser),
    ]
