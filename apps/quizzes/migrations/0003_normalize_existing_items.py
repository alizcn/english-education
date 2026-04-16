from django.db import migrations

from apps.quizzes.normalization import normalize_item


def _clean(items):
    if not isinstance(items, list):
        return items
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        n = normalize_item(it)
        if not (n.get('prompt') or '').strip():
            continue
        if not (n.get('correct_answer') or '').strip():
            continue
        if n.get('question_type') == 'multiple_choice':
            ch = n.get('choices') or []
            if len(ch) < 2:
                continue
        out.append(n)
    return out


def forwards(apps, schema_editor):
    QuizTemplate = apps.get_model('quizzes', 'QuizTemplate')
    for t in QuizTemplate.objects.all():
        cleaned = _clean(t.questions_data)
        if cleaned != t.questions_data:
            t.questions_data = cleaned
            t.save(update_fields=['questions_data'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('quizzes', '0002_quiztemplate_quizsession_template'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
