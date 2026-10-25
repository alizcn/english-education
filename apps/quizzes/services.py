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


def template_count(user, kind, topic=None, *, target_language) -> int:
    return QuizTemplate.objects.filter(
        user=user, kind=kind, topic=topic, target_language=target_language,
    ).count()


def next_template_name(user, kind, topic=None, *, target_language) -> str:
    n = template_count(user, kind, topic=topic, target_language=target_language)
    return f'Quiz #{n + 1}'


def word_pool(user, target_language) -> list:
    """Kişisel kelime havuzu. Anahtarlar AI sözleşmesiyle birebir: term/meaning."""
    return list(
        Word.objects
        .filter(user=user, target_language=target_language)
        .values('term', 'meaning')
    )


def topic_context(topic, *, pair) -> dict:
    """Konu üretimi için gereken her şeyi TEK SEFERDE okur.

    `claude_client.parallel_map`in sözleşmesi iş parçacıklarının veritabanına
    dokunmamasını şart koşuyor: Django thread başına ayrı bağlantı açıyor ve
    SQLite'ta beş paralel parça `database table is locked` ile düşüyor.
    `word_pool` zaten bu yüzden havuzu önceden okuyor; konu tarafı da aynı
    deseni izliyor.
    """
    explanation, _code = topic.explanation_for(pair.native_code)
    return {
        'name': topic.name,
        'explanation': explanation,
        'examples': list(topic.examples.values_list('sentence', flat=True)),
    }


def topic_items(context: dict, n: int, focus: str = '', *, pair) -> list:
    """`context` önceden okunmuş konu verisi (bkz. `topic_context`)."""
    return normalize_items(
        claude.generate_topic_quiz(
            context['name'], context['explanation'], context['examples'],
            n=n, focus=focus, pair=pair,
        )
    )


def word_items(pool: list, n: int, focus: str = '', *, pair) -> list:
    return normalize_items(
        claude.generate_word_quiz_extras(pool, n=n, focus=focus, pair=pair)
    )
