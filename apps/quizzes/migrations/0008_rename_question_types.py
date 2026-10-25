"""Soru tiplerini dil çiftinden yöne çevirir.

`translate_en_tr` → `translate_to_native`, `translate_tr_en` → `translate_to_target`.

Dil çifti bazlı isimlendirme 4 hedef × 3 ana dil = 12 çiftte 24 enum değerine
patlıyordu. Yön + oturumun `target_language`/`native_language` alanları
birlikte anlamı tam belirlediği için sabit 4 değer yetiyor.

`questions_data` JSON alanları da dönüştürülüyor: hem şablonlarda hem seed
verisinde soru tipi orada da yazılı.
"""

from django.db import migrations

FORWARD = {
    'translate_en_tr': 'translate_to_native',
    'translate_tr_en': 'translate_to_target',
}
BACKWARD = {new: old for old, new in FORWARD.items()}
BATCH = 500


def _remap_json(model, mapping):
    """`questions_data` içindeki question_type değerlerini eşler."""
    updates = []
    for row in model.objects.exclude(questions_data=[]).iterator(chunk_size=BATCH):
        items = row.questions_data
        if not isinstance(items, list):
            continue
        changed = False
        for item in items:
            if not isinstance(item, dict):
                continue
            current = item.get('question_type')
            if current in mapping:
                item['question_type'] = mapping[current]
                changed = True
        if changed:
            row.questions_data = items
            updates.append(row)
        if len(updates) >= BATCH:
            model.objects.bulk_update(updates, ['questions_data'])
            updates = []
    if updates:
        model.objects.bulk_update(updates, ['questions_data'])


def forwards(apps, schema_editor):
    Question = apps.get_model('quizzes', 'QuizQuestion')
    Template = apps.get_model('quizzes', 'QuizTemplate')

    for old, new in FORWARD.items():
        Question.objects.filter(question_type=old).update(question_type=new)
    _remap_json(Template, FORWARD)


def backwards(apps, schema_editor):
    """Yalnızca TÜM içerik İngilizce iken güvenli.

    Ters eşleme `translate_to_native` → `translate_en_tr` diyor; bu, hedef
    dilin İngilizce ve ana dilin Türkçe olduğunu varsayıyor. Faz 5'ten sonra
    Almanca ya da Fransızca sorular varsa bu eşleme onlara yanlış tip yazar ve
    hata sessiz kalır — bu yüzden açıkça reddediyoruz.
    """
    BankWord = apps.get_model('wordbank', 'BankWord')
    Session = apps.get_model('quizzes', 'QuizSession')

    non_english = (
        BankWord.objects.exclude(language='en').exists()
        or Session.objects.exclude(target_language='en').exists()
    )
    if non_english:
        raise RuntimeError(
            'Geri alma reddedildi: İngilizce dışında içerik var. Ters eşleme '
            '(translate_to_native -> translate_en_tr) hedefin İngilizce, ana '
            'dilin Türkçe olduğunu varsayıyor; başka dillerde yanlış tip '
            'yazardı. Geri almak gerekiyorsa önce diğer dillerin içeriğini '
            'kaldırın.'
        )

    Question = apps.get_model('quizzes', 'QuizQuestion')
    Template = apps.get_model('quizzes', 'QuizTemplate')
    for old, new in BACKWARD.items():
        Question.objects.filter(question_type=old).update(question_type=new)
    _remap_json(Template, BACKWARD)


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0007_template_session_languages'),
        # Ters yön `BankWord.language`a bakıyor; o alan wordbank/0006'da doğuyor.
        ('wordbank', '0006_bankword_language_extra'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
