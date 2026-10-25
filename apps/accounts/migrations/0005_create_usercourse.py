"""Kullanıcı başına çok kurs: `UserLevel` yerine `UserCourse`.

`UserLevel` OneToOne olduğu için bir kullanıcı tek dil öğrenebiliyordu. Veri
0006'da taşınıyor, eski model 0007'de siliniyor.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_create_superuser_after_tables'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserCourse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('target_language', models.CharField(
                    choices=[('tr', 'Türkçe'), ('en', 'English'),
                             ('fr', 'Français'), ('de', 'Deutsch')],
                    max_length=5, verbose_name='Öğrenilen dil')),
                ('native_language', models.CharField(
                    choices=[('tr', 'Türkçe'), ('en', 'English'),
                             ('fr', 'Français'), ('de', 'Deutsch')],
                    max_length=5, verbose_name='Anlatım dili')),
                ('current_level', models.CharField(
                    choices=[('A1', 'A1'), ('A2', 'A2'), ('B1', 'B1'),
                             ('B2', 'B2'), ('C1', 'C1'), ('C2', 'C2')],
                    default='A1', max_length=2)),
                ('score', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(
                    default=False,
                    help_text='Kullanıcının üzerinde çalıştığı kurs.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='courses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Kurs',
                'verbose_name_plural': 'Kurslar',
                'ordering': ['-is_active', 'target_language'],
            },
        ),
        migrations.AddConstraint(
            model_name='usercourse',
            constraint=models.UniqueConstraint(
                fields=('user', 'target_language'), name='unique_user_course'),
        ),
        migrations.AddConstraint(
            model_name='usercourse',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)), fields=('user',),
                name='one_active_course'),
        ),
        migrations.AlterModelOptions(
            name='userlevel',
            options={'verbose_name': 'Seviye (eski)',
                     'verbose_name_plural': 'Seviyeler (eski)'},
        ),
    ]
