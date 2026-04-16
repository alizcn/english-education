from services import ai
from apps.vocabulary.models import Word
from .models import QuizTemplate, QuizSession
from .normalization import normalize_items


POOL_TARGET = 5
MIN_WORDS = 10


def _template_count(user, kind, topic=None):
    return QuizTemplate.objects.filter(user=user, kind=kind, topic=topic).count()


def _generate_topic_template(user, topic):
    examples = list(topic.examples.values_list('sentence_en', flat=True))
    items = ai.generate_topic_quiz(topic.name, topic.explanation, examples, n=50)
    items = normalize_items(items)
    if not items:
        return None
    count = _template_count(user, QuizTemplate.TOPIC, topic=topic)
    return QuizTemplate.objects.create(
        user=user,
        kind=QuizTemplate.TOPIC,
        topic=topic,
        name=f'Quiz #{count + 1}',
        questions_data=items,
    )


def _generate_word_template(user):
    pool = list(Word.objects.filter(user=user).values('english', 'turkish'))
    if len(pool) < MIN_WORDS:
        return None
    items = ai.generate_word_quiz_extras(pool, n=50)
    items = normalize_items(items)
    if not items:
        return None
    count = _template_count(user, QuizTemplate.WORD)
    return QuizTemplate.objects.create(
        user=user,
        kind=QuizTemplate.WORD,
        name=f'Quiz #{count + 1}',
        questions_data=items,
    )


def generate_one(user, kind, topic=None):
    if kind == QuizTemplate.TOPIC:
        return _generate_topic_template(user, topic)
    return _generate_word_template(user)


def ensure_at_least_one(user, kind, topic=None):
    """İlk ziyarette en az bir şablon garanti et."""
    if _template_count(user, kind, topic=topic) == 0:
        return generate_one(user, kind, topic=topic)
    return None


def uncompleted_count(user, kind, topic=None):
    templates = QuizTemplate.objects.filter(user=user, kind=kind, topic=topic)
    finished_ids = set(
        QuizSession.objects.filter(
            user=user, template__in=templates, finished_at__isnull=False,
        ).values_list('template_id', flat=True)
    )
    return templates.exclude(id__in=finished_ids).count()


def replenish_if_needed(user, kind, topic=None, threshold=1, target=POOL_TARGET):
    """Çözülmemiş sayısı threshold'a inince, havuz target'a ulaşmadıysa yeni üret."""
    total = _template_count(user, kind, topic=topic)
    if total >= target:
        return None
    remaining = uncompleted_count(user, kind, topic=topic)
    if remaining <= threshold:
        return generate_one(user, kind, topic=topic)
    return None
