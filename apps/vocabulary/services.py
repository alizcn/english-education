import random
from .models import Word


MIN_WORDS_FOR_QUIZ = 4


def personal_stats(user):
    words = Word.objects.filter(user=user)
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


def pick_next(user):
    unseen_qs = Word.objects.filter(user=user, mastered=False, times_asked=0).order_by('id')
    retry_qs = Word.objects.filter(user=user, mastered=False, times_asked__gt=0)

    has_unseen = unseen_qs.exists()
    retry_list = list(retry_qs)

    if not has_unseen and not retry_list:
        return None, False

    if retry_list and (not has_unseen or random.random() < 0.25):
        return random.choice(retry_list), True
    return unseen_qs.first(), False


def build_question(word, user):
    candidate_ids = list(
        Word.objects.filter(user=user)
        .exclude(id=word.id)
        .exclude(turkish=word.turkish)
        .exclude(turkish='')
        .values_list('id', flat=True)
    )
    chosen_ids = random.sample(candidate_ids, k=min(3, len(candidate_ids)))
    distractors = list(Word.objects.filter(id__in=chosen_ids))
    correct = (word.turkish or '').strip()
    options = [correct] + [(d.turkish or '').strip() for d in distractors]
    options = [o for o in options if o]
    random.shuffle(options)
    return options


def record_answer(word, is_correct):
    word.times_asked += 1
    if is_correct:
        word.times_correct += 1
        word.mastered = True
    word.save(update_fields=['times_asked', 'times_correct', 'mastered'])
