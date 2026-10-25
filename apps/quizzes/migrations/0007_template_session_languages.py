"""Quiz şablon ve oturumlarına dil çifti.

FK değil CharField: seed şablonları `user=None` olduğu için `UserCourse`a FK
verilemiyor, ayrıca dil çifti şablonun kendi özelliği.

`QuizSession.target_language` puanın hangi kursa yazılacağını belirliyor
(bkz. apps/accounts/signals.py) — Almanca quizinin puanı İngilizce seviyesini
yükseltmemeli.
"""

from django.db import migrations, models

LANG_CHOICES = [('tr', 'Türkçe'), ('en', 'English'),
                ('fr', 'Français'), ('de', 'Deutsch')]


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0006_quiztemplate_error_message_quiztemplate_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quiztemplate', name='target_language',
            field=models.CharField(choices=LANG_CHOICES, db_index=True,
                                   default='en', max_length=5,
                                   verbose_name='Öğrenilen dil'),
        ),
        migrations.AddField(
            model_name='quiztemplate', name='native_language',
            field=models.CharField(choices=LANG_CHOICES, default='tr',
                                   max_length=5, verbose_name='Anlatım dili'),
        ),
        migrations.AddField(
            model_name='quizsession', name='target_language',
            field=models.CharField(choices=LANG_CHOICES, db_index=True,
                                   default='en', max_length=5,
                                   verbose_name='Öğrenilen dil'),
        ),
        migrations.AddField(
            model_name='quizsession', name='native_language',
            field=models.CharField(choices=LANG_CHOICES, default='tr',
                                   max_length=5, verbose_name='Anlatım dili'),
        ),
    ]
