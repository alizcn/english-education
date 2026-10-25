"""Kişisel kelime listesinin quiz parçaları.

Her sorgu bir hedef dile bağlı: kullanıcının Almanca listesi İngilizce quizine
karışmamalı.
"""

import random

from .models import Word


MIN_WORDS_FOR_QUIZ = 4


def user_words(user, target_language):
    return Word.objects.filter(user=user, target_language=target_language)


def personal_stats(user, target_language):
    words = user_words(user, target_language)
    total = words.count()
    mastered = words.filter(mastered=True).count()
    retry = words.filter(mastered=False, times_asked__gt=0).count()
    unseen = words.filter(mastered=False, times_asked=0).count()
    percent = round(100 * mastered / total) if total else 0
    return {
        'total': total,
        'mastered': mastered,
        'retry': retry,
        'unseen': unseen,
        'percent': percent,
    }


def pick_next(user, target_language):
    base = user_words(user, target_language)
    unseen_qs = base.filter(mastered=False, times_asked=0).order_by('id')
    retry_qs = base.filter(mastered=False, times_asked__gt=0)

    has_unseen = unseen_qs.exists()
    retry_list = list(retry_qs)

    if not has_unseen and not retry_list:
        return None, False

    if retry_list and (not has_unseen or random.random() < 0.25):
        return random.choice(retry_list), True
    return unseen_qs.first(), False


def build_question(word, user):
    candidate_ids = list(
        user_words(user, word.target_language)
        .exclude(id=word.id)
        .exclude(meaning=word.meaning)
        .exclude(meaning='')
        .values_list('id', flat=True)
    )
    chosen_ids = random.sample(candidate_ids, k=min(3, len(candidate_ids)))
    distractors = list(Word.objects.filter(id__in=chosen_ids))
    correct = (word.meaning or '').strip()
    options = [correct] + [(d.meaning or '').strip() for d in distractors]
    options = [o for o in options if o]
    random.shuffle(options)
    return options


def record_answer(word, is_correct):
    word.times_asked += 1
    if is_correct:
        word.times_correct += 1
        word.mastered = True
    word.save(update_fields=['times_asked', 'times_correct', 'mastered'])
