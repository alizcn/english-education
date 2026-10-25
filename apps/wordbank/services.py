"""Kelime hazinesi quizinin saf parçaları.

Her fonksiyon artık bir (hedef dil, ana dil) çifti içinde çalışıyor. Eskiden
"anlamı olan kelime" `.exclude(turkish='')` ile süzülüyordu; şimdi anlam ayrı
tabloda olduğu için ölçüt "istenen ana dilde çevirisi var" oldu.
"""

import random

from .models import BankProgress, BankWord, BankWordTranslation


def translated_words(target_language, native_language, level=None):
    """İstenen ana dilde çevirisi OLAN kelimeler.

    Çeviri ayrı tabloda, bu yüzden `exclude(meaning='')` yerine ilişki üzerinden
    süzülüyor. Aynı kelimenin iki çevirisi olamaz (`unique_word_translation`),
    dolayısıyla join satır çoğaltmıyor.
    """
    qs = BankWord.objects.filter(
        language=target_language,
        translations__language=native_language,
    ).exclude(translations__meaning='')
    if level:
        qs = qs.filter(level=level)
    return qs


def level_stats(user, level, *, target_language, native_language):
    total = translated_words(target_language, native_language, level).count()
    if total == 0:
        return {
            'level': level, 'total': 0, 'answered': 0,
            'mastered': 0, 'retry': 0, 'unseen': 0,
            'percent': 0,
        }
    progress_qs = BankProgress.objects.filter(
        user=user, word__language=target_language, word__level=level,
    )
    answered = progress_qs.count()
    mastered = progress_qs.filter(mastered=True).count()
    retry = progress_qs.filter(mastered=False).count()
    unseen = total - answered
    percent = round(100 * mastered / total) if total else 0
    return {
        'level': level, 'total': total, 'answered': answered,
        'mastered': mastered, 'retry': retry, 'unseen': unseen,
        'percent': percent,
    }


def pick_next(user, level, *, target_language, native_language):
    """(kelime, tekrar_mı) döndürür; seviye bittiyse (None, False)."""
    seen_ids = set(
        BankProgress.objects
        .filter(user=user, word__language=target_language, word__level=level)
        .values_list('word_id', flat=True)
    )
    unseen_qs = (
        translated_words(target_language, native_language, level)
        .exclude(id__in=seen_ids)
        .order_by('rank')
    )
    retry_qs = (
        BankProgress.objects
        .filter(
            user=user,
            word__language=target_language,
            word__level=level,
            mastered=False,
            word__translations__language=native_language,
        )
        .exclude(word__translations__meaning='')
        .select_related('word')
    )

    has_unseen = unseen_qs.exists()
    retry_list = list(retry_qs)

    if not has_unseen and not retry_list:
        return None, False

    if retry_list and (not has_unseen or random.random() < 0.25):
        return random.choice(retry_list).word, True
    return unseen_qs.first(), False


def build_question(word, *, native_language):
    """(doğru_çeviri, seçenekler) — seçenekler karıştırılmış çeviri nesneleri.

    Çeviri nesnesi döndürüyoruz, düz metin değil: cevap kontrolü artık metin
    karşılaştırmak yerine kimlik karşılaştırıyor. Aynı anlama gelen iki farklı
    çeviri metni ("kitap" / "kitap") eskiden şıkları sessizce teke indiriyordu.
    """
    correct = word.translation_for(native_language)
    if correct is None:
        return None, []

    candidate_ids = list(
        BankWordTranslation.objects
        .filter(language=native_language, word__language=word.language,
                word__level=word.level)
        .exclude(word_id=word.id)
        .exclude(meaning='')
        .exclude(meaning=correct.meaning)
        .values_list('id', flat=True)
    )
    chosen_ids = random.sample(candidate_ids, k=min(3, len(candidate_ids)))
    distractors = list(BankWordTranslation.objects.filter(id__in=chosen_ids))

    options = [correct] + distractors
    random.shuffle(options)
    return correct, options


def record_answer(user, word, is_correct):
    progress, _ = BankProgress.objects.get_or_create(user=user, word=word)
    if is_correct:
        progress.mastered = True
        progress.correct_count += 1
    else:
        progress.wrong_count += 1
    progress.save()
    return progress
