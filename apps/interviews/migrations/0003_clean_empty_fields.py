from django.db import migrations


REQUIRED = ('question_tr', 'question_en', 'answer_tr', 'answer_en')


def _clean(items):
    if not isinstance(items, list):
        return items
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cleaned = {k: str(it.get(k) or '').strip() for k in REQUIRED}
        if all(cleaned.values()):
            out.append(cleaned)
    return out


def forwards(apps, schema_editor):
    InterviewSession = apps.get_model('interviews', 'InterviewSession')
    removed_sessions = 0
    fixed_sessions = 0
    for s in InterviewSession.objects.all():
        cleaned = _clean(s.questions_data)
        if not cleaned:
            s.delete()
            removed_sessions += 1
            continue
        if cleaned != s.questions_data:
            s.questions_data = cleaned
            s.save(update_fields=['questions_data'])
            fixed_sessions += 1
    if fixed_sessions or removed_sessions:
        print(f'  interviews: fixed {fixed_sessions}, removed {removed_sessions} empty sessions')


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('interviews', '0002_interviewsession_cv_filename_interviewsession_source_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
