import os

from django.conf import settings
from django.db import migrations


DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "93.aliozcan@gmail.com"
DEFAULT_PASSWORD = "Admin2026!"


def create_superuser(apps, schema_editor):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME)
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", DEFAULT_EMAIL)
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", DEFAULT_PASSWORD)

    if User.objects.filter(username=username).exists():
        return

    User.objects.create_superuser(username=username, email=email, password=password)


def remove_superuser(apps, schema_editor):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME)
    User.objects.filter(username=username, is_superuser=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_superuser, remove_superuser),
    ]
