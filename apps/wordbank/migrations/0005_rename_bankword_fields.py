"""Dil adlarını alan adlarından çıkarır: english→term, example_en→example.

`RenameField` veriyi KORUR (SQLite'ta tabloyu yeniden kurar ama içeriği taşır).
`turkish` ve `example_tr` burada adlandırılmıyor; onlar 0008'de ayrı tabloya
kopyalanıp 0011'de silinecek.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wordbank', '0004_remove_unique_bank_word'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bankword', old_name='english', new_name='term',
        ),
        migrations.RenameField(
            model_name='bankword', old_name='example_en', new_name='example',
        ),
    ]
