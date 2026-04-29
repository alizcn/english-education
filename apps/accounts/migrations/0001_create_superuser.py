import os

from django.conf import settings
from django.db import migrations


DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "93.aliozcan@gmail.com"
DEFAULT_PASSWORD = "Admin2026!"


def create_superuser(apps, schema_editor):
    from django.contrib.auth import get_user_model
    from django.db.models.signals import post_save

    User = get_user_model()
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME)
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", DEFAULT_EMAIL)
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", DEFAULT_PASSWORD)

    if User.objects.filter(username=username).exists():
        return

    # Temporarily disconnect post_save signals to avoid accessing
    # tables that haven't been created yet (e.g. accounts_userlevel).
    receivers_backup = post_save.receivers[:]
    post_save.receivers = []
    post_save.sender_receivers_cache.clear()
    try:
        User.objects.create_superuser(username=username, email=email, password=password)
    finally:
        post_save.receivers = receivers_backup
        post_save.sender_receivers_cache.clear()


def remove_superuser(apps, schema_editor):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME)
    User.objects.filter(username=username, is_superuser=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '__latest__'),
    ]

    operations = [
        migrations.RunPython(create_superuser, remove_superuser),
    ]
