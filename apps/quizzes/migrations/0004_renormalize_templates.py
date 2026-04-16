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
            if any((not isinstance(c, str) or not c.strip()) for c in ch):
                continue
            if n['correct_answer'] not in ch:
                continue
        out.append(n)
    return out


def forwards(apps, schema_editor):
    QuizTemplate = apps.get_model('quizzes', 'QuizTemplate')
    fixed = 0
    for t in QuizTemplate.objects.all():
        cleaned = _clean(t.questions_data)
        if cleaned != t.questions_data:
            t.questions_data = cleaned
            t.save(update_fields=['questions_data'])
            fixed += 1
    if fixed:
        print(f'  quizzes: normalized {fixed} template(s)')


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('quizzes', '0003_normalize_existing_items'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
