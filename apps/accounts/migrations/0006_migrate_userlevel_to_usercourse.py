"""Mevcut seviyeleri İngilizce kursuna taşır.

Bugün tek kurs var: Türk kullanıcıya İngilizce. Dolayısıyla her `UserLevel`
satırı `(target='en', native='tr')` kursuna, aktif olarak dönüşüyor.

Tersine alınabilir: geri yönde İngilizce kursu `UserLevel`a yazılır.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    UserLevel = apps.get_model('accounts', 'UserLevel')
    UserCourse = apps.get_model('accounts', 'UserCourse')

    rows = [
        UserCourse(
            user_id=level.user_id,
            target_language='en',
            native_language='tr',
            current_level=level.current_level,
            score=level.score,
            is_active=True,
        )
        for level in UserLevel.objects.all().iterator()
    ]
    # ignore_conflicts: migration yeniden koşarsa (ör. kısmi başarısızlık
    # sonrası) mevcut kursları ezmesin.
    UserCourse.objects.bulk_create(rows, ignore_conflicts=True)


def backwards(apps, schema_editor):
    UserLevel = apps.get_model('accounts', 'UserLevel')
    UserCourse = apps.get_model('accounts', 'UserCourse')

    for course in UserCourse.objects.filter(target_language='en').iterator():
        UserLevel.objects.update_or_create(
            user_id=course.user_id,
            defaults={'current_level': course.current_level, 'score': course.score},
        )
    UserCourse.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_create_usercourse'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
