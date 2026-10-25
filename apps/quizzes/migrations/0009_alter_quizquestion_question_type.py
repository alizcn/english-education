"""Soru tipi etiketleri artık dil çifti yazmıyor (yalnızca durum).

Eski etiketler "Çeviri EN→TR" / "Çeviri TR→EN" idi; yöne dayalı isimlendirmeyle
birlikte "Hedef dilden çeviri" / "Hedef dile çeviri" oldu.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0008_rename_question_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quizquestion',
            name='question_type',
            field=models.CharField(
                choices=[('translate_to_native', 'Hedef dilden çeviri'),
                         ('translate_to_target', 'Hedef dile çeviri'),
                         ('fill_blank', 'Boşluk doldurma'),
                         ('multiple_choice', 'Çoktan seçmeli')],
                max_length=20),
        ),
    ]
