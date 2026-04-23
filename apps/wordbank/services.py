import random
from django.db.models import Count, Q

from .models import BankWord, BankProgress


def level_stats(user, level):
    total = BankWord.objects.filter(level=level).exclude(turkish='').count()
    if total == 0:
        return {
            'level': level, 'total': 0, 'answered': 0,
            'mastered': 0, 'retry': 0, 'unseen': 0,
            'percent': 0,
        }
    progress_qs = BankProgress.objects.filter(user=user, word__level=level)
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


def pick_next(user, level):
    """Return (word, is_retry) or (None, False) if level complete."""
    seen_ids = set(
        BankProgress.objects.filter(user=user, word__level=level)
        .values_list('word_id', flat=True)
    )
    unseen_qs = (
        BankWord.objects.filter(level=level)
        .exclude(id__in=seen_ids)
        .exclude(turkish='')
        .order_by('rank')
    )
    retry_qs = BankProgress.objects.filter(
        user=user, word__level=level, mastered=False,
    ).exclude(word__turkish='').select_related('word')

    has_unseen = unseen_qs.exists()
    retry_list = list(retry_qs)

    if not has_unseen and not retry_list:
        return None, False

    if retry_list and (not has_unseen or random.random() < 0.25):
        return random.choice(retry_list).word, True
    return unseen_qs.first(), False


def build_question(word):
    """Return list of up to 4 shuffled Turkish options (1 correct + 3 distractors)."""
    candidate_ids = list(
        BankWord.objects.filter(level=word.level)
        .exclude(id=word.id)
        .exclude(turkish=word.turkish)
        .exclude(turkish='')
        .values_list('id', flat=True)
    )
    chosen_ids = random.sample(candidate_ids, k=min(3, len(candidate_ids)))
    distractors = list(BankWord.objects.filter(id__in=chosen_ids))
    correct = (word.turkish or '').strip()
    options = [correct] + [(d.turkish or '').strip() for d in distractors]
    options = [o for o in options if o]
    random.shuffle(options)
    return options


def record_answer(user, word, is_correct):
    progress, _ = BankProgress.objects.get_or_create(user=user, word=word)
    if is_correct:
        progress.mastered = True
        progress.correct_count += 1
    else:
        progress.wrong_count += 1
    progress.save()
    return progress
