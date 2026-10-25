"""Örnek sıralaması kısıtı — seeder'ın keyed upsert yapabilmesi için.

Eski seeder her çalıştığında `topic.examples.all().delete()` yapıp yeniden
yaratıyordu: her container açılışında 324 satırın PK'sı değişiyor, SQLite
dosyası şişiyor ve örneklere FK vermek imkânsız hâle geliyordu.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0004_move_explanations_and_examples'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='topicexample',
            options={'ordering': ['topic', 'kind', 'order', 'id']},
        ),
        migrations.AddConstraint(
            model_name='topicexample',
            constraint=models.UniqueConstraint(
                fields=('topic', 'kind', 'order'),
                name='unique_topic_example_order'),
        ),
    ]
