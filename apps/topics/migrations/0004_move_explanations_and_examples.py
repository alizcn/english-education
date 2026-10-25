"""Anlatımları ve örnek çevirilerini yeni yapıya taşır.

* `Topic.explanation` (Türkçe) → `TopicExplanation(language='tr')`
* `Topic.explanation_en`       → `TopicExplanation(language='en')`
* `TopicExample.sentence_tr`   → `translations['tr']`

Örneklere ayrıca `order` veriliyor: yeni `(topic, kind, order)` kısıtının ön
koşulu. Sıra mevcut `id` düzenine göre, yani ekrandaki sıralama korunuyor.

Tersine alınabilir.
"""

from django.db import migrations

BATCH = 500


def forwards(apps, schema_editor):
    Topic = apps.get_model('topics', 'Topic')
    Explanation = apps.get_model('topics', 'TopicExplanation')
    Example = apps.get_model('topics', 'TopicExample')

    rows = []
    for topic in Topic.objects.all().iterator():
        for code, body in (('tr', topic.explanation), ('en', topic.explanation_en)):
            body = (body or '').strip()
            if body:
                rows.append(Explanation(topic_id=topic.id, language=code, body=body))
    Explanation.objects.bulk_create(rows, ignore_conflicts=True)

    # Örnek çevirileri + sıra. `kind` grubu içinde id sırası korunuyor.
    for topic_id in Topic.objects.values_list('id', flat=True):
        for kind in ('positive', 'negative', 'question'):
            examples = list(
                Example.objects.filter(topic_id=topic_id, kind=kind).order_by('id')
            )
            for index, example in enumerate(examples):
                example.order = index
                translation = (example.sentence_tr or '').strip()
                example.translations = {'tr': translation} if translation else {}
            if examples:
                Example.objects.bulk_update(examples, ['order', 'translations'])


def backwards(apps, schema_editor):
    Topic = apps.get_model('topics', 'Topic')
    Explanation = apps.get_model('topics', 'TopicExplanation')
    Example = apps.get_model('topics', 'TopicExample')

    for topic in Topic.objects.all().iterator():
        bodies = {
            e.language: e.body
            for e in Explanation.objects.filter(topic_id=topic.id)
        }
        topic.explanation = bodies.get('tr', '')
        topic.explanation_en = bodies.get('en', '')
        topic.save(update_fields=['explanation', 'explanation_en'])
    Explanation.objects.all().delete()

    updates = []
    for example in Example.objects.all().iterator(chunk_size=BATCH):
        example.sentence_tr = (example.translations or {}).get('tr', '')
        updates.append(example)
        if len(updates) >= BATCH:
            Example.objects.bulk_update(updates, ['sentence_tr'])
            updates = []
    if updates:
        Example.objects.bulk_update(updates, ['sentence_tr'])


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0003_topic_language_explanations'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
