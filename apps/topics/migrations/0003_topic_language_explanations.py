"""Konulara hedef dil ekseni, anlatımlara ayrı tablo, örneklere sıra+çeviri.

`slug` tek başına UNIQUE olmaktan çıkıyor: konu listesi hedef dile özgü,
Almanca'nın konuları İngilizce'den çeviri değil. Sıra önemli — önce
`AlterField(unique=False)`, sonra `(language, slug)` kısıtı.
"""

import django.db.models.deletion
from django.db import migrations, models

LANG_CHOICES = [('tr', 'Türkçe'), ('en', 'English'),
                ('fr', 'Français'), ('de', 'Deutsch')]


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0002_topic_explanation_en_topic_updated_at_and_more'),
    ]

    operations = [
        # --- Topic ---
        migrations.AddField(
            model_name='topic',
            name='language',
            field=models.CharField(choices=LANG_CHOICES, db_index=True,
                                   default='en', max_length=5,
                                   verbose_name='Hedef dil'),
        ),
        migrations.AlterField(
            model_name='topic',
            name='slug',
            field=models.SlugField(),
        ),
        migrations.AlterModelOptions(
            name='topic',
            options={'ordering': ['language', 'order', 'name']},
        ),
        migrations.AddConstraint(
            model_name='topic',
            constraint=models.UniqueConstraint(
                fields=('language', 'slug'), name='unique_topic_language_slug'),
        ),
        # --- TopicExplanation ---
        migrations.CreateModel(
            name='TopicExplanation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=LANG_CHOICES, max_length=5,
                                              verbose_name='Anlatım dili')),
                ('body', models.TextField(verbose_name='Anlatım (markdown)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('topic', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='explanations', to='topics.topic')),
            ],
            options={'ordering': ['topic', 'language']},
        ),
        migrations.AddConstraint(
            model_name='topicexplanation',
            constraint=models.UniqueConstraint(
                fields=('topic', 'language'), name='unique_topic_explanation'),
        ),
        # --- TopicExample ---
        migrations.RenameField(
            model_name='topicexample', old_name='sentence_en', new_name='sentence',
        ),
        migrations.AlterField(
            model_name='topicexample',
            name='sentence',
            field=models.CharField(max_length=300,
                                   verbose_name='Cümle (hedef dilde)'),
        ),
        migrations.AddField(
            model_name='topicexample',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='topicexample',
            name='translations',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='{"tr": "...", "en": "..."} — ana dil kodundan çeviriye.'),
        ),
    ]
