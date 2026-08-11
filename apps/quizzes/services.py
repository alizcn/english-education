"""Quiz üretiminin saf parçaları.

Buradaki fonksiyonlar Claude'u çağırıp normalize edilmiş soru listesi döndürür;
şablonu yaratmak ve durumunu yönetmek `tasks.py`nin işi. Ayrım kasıtlı: üretim
dakikalar sürüyor ve HTTP isteği içinde çalıştırılamaz.
"""

from apps.vocabulary.models import Word
from services import claude_client as claude

from .models import QuizTemplate
from .normalization import normalize_items

MIN_WORDS = 10


def template_count(user, kind, topic=None) -> int:
    return QuizTemplate.objects.filter(user=user, kind=kind, topic=topic).count()


def next_template_name(user, kind, topic=None) -> str:
    return f'Quiz #{template_count(user, kind, topic=topic) + 1}'


def word_pool(user) -> list[dict]:
    return list(Word.objects.filter(user=user).values('english', 'turkish'))


def topic_items(topic, n: int, focus: str = '') -> list[dict]:
    examples = list(topic.examples.values_list('sentence_en', flat=True))
    return normalize_items(
        claude.generate_topic_quiz(topic.name, topic.explanation, examples, n=n, focus=focus)
    )


def word_items(pool: list[dict], n: int, focus: str = '') -> list[dict]:
    return normalize_items(claude.generate_word_quiz_extras(pool, n=n, focus=focus))
