"""Quiz üretimi — arka plan görevleri.

Bu üretim eskiden HTTP isteğinin içinde çalışıyordu: tek çağrıda 50 soru, ~100 saniye.
O süre boyunca bir gunicorn worker'ı bloke oluyordu ve `--workers 3` ile üç eşzamanlı
quiz üretimi siteyi herkes için durduruyordu. Artık mülakat tarafındaki desenin aynısı:
PENDING şablon açılır, iş buraya devredilir, sorular parça parça birikir.

Üretim paralel parçalara bölünüyor çünkü çıktı tokeni seri üretiliyor — tek büyük
çağrının süresi ürettiği metinle doğru orantılı (bkz. apps/interviews/tasks.py).
"""

import logging

from celery import shared_task
from django.utils.translation import gettext as _

from services import claude_client as claude

from . import services as quiz_services
from .models import QuizTemplate

logger = logging.getLogger(__name__)

QUESTION_TARGET = 50
CHUNK_SIZE = 10

# Her parçaya ayrı odak; yoksa parçalar birbirinin sorusunu üretir.
TOPIC_FOCUS = [
    'positive statements covering the basic usage',
    'negative forms',
    'question forms, including short answers',
    'multiple_choice items with plausible but clearly wrong distractors',
    'translation in both directions using slightly longer everyday sentences',
]
WORD_FOCUS = [
    'translate_en_tr items',
    'translate_tr_en items',
    'multiple_choice items with close, easily-confused distractors',
    'words from the second half of the pool',
    'the least common words in the pool',
]


def _chunk_plan(total: int, focuses: list[str]) -> list[tuple[int, str]]:
    plan = []
    remaining = total
    while remaining > 0:
        size = min(CHUNK_SIZE, remaining)
        plan.append((size, focuses[len(plan) % len(focuses)]))
        remaining -= size
    return plan


def _dedupe(items: list[dict], seen: set) -> list[dict]:
    fresh = []
    for it in items:
        key = (it.get('prompt') or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        fresh.append(it)
    return fresh


def _fail(template: QuizTemplate, message: str) -> None:
    template.status = QuizTemplate.FAILED
    template.error_message = message[:300]
    template.save(update_fields=['status', 'error_message'])


def _run(template_id: int, produce, focuses: list[str]) -> None:
    """Parçaları paralel üret, bitenleri hemen yaz. `produce(n, focus)` bir parça üretir."""
    try:
        template = QuizTemplate.objects.get(pk=template_id)
    except QuizTemplate.DoesNotExist:
        logger.warning('quiz şablonu bulunamadı, üretim atlandı: %s', template_id)
        return

    if template.status == QuizTemplate.READY:
        # acks_late yeniden teslim ettiyse iş zaten bitmiş.
        logger.info('quiz zaten hazır, yeniden üretim atlandı: %s', template_id)
        return

    if template.questions_data:
        template.questions_data = []
        template.save(update_fields=['questions_data'])

    collected: list[dict] = []
    seen: set = set()
    first_error: Exception | None = None

    plan = _chunk_plan(QUESTION_TARGET, focuses)
    for _index, items, error in claude.parallel_map(lambda p: produce(*p), plan):
        if error is not None:
            first_error = first_error or error
            continue
        fresh = _dedupe(items or [], seen)
        if not fresh:
            continue
        collected.extend(fresh)
        template.questions_data = collected
        template.save(update_fields=['questions_data'])

    if not collected:
        if isinstance(first_error, claude.ClaudeClientError):
            logger.warning('quiz üretimi başarısız (template=%s): %s', template_id, first_error)
            _fail(template, str(first_error))
        elif first_error is not None:
            logger.exception(
                'quiz üretiminde beklenmedik hata (template=%s)', template_id, exc_info=first_error,
            )
            _fail(template, _('Quiz üretilirken beklenmedik bir hata oluştu.'))
        else:
            _fail(template, _('Quiz üretilemedi. Tekrar dene.'))
        return

    if first_error is not None:
        logger.warning(
            'quiz kısmi üretildi (template=%s, soru=%d): %s', template_id, len(collected), first_error,
        )

    template.questions_data = collected
    template.status = QuizTemplate.READY
    template.error_message = ''
    template.save(update_fields=['questions_data', 'status', 'error_message'])
    logger.info('quiz hazır (template=%s, soru=%d)', template_id, len(collected))


# Süre merdiveni mülakat tarafıyla aynı gerekçeye dayanıyor; oradaki yorumu da oku.
SOFT_TIME_LIMIT = 660
HARD_TIME_LIMIT = 720

_TASK = dict(
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=SOFT_TIME_LIMIT,
    time_limit=HARD_TIME_LIMIT,
)


@shared_task(**_TASK)
def generate_topic_template(template_id: int, topic_id: int) -> None:
    from apps.topics.models import Topic

    try:
        topic = Topic.objects.get(pk=topic_id)
    except Topic.DoesNotExist:
        logger.warning('quiz konusu bulunamadı, üretim atlandı: %s', topic_id)
        return
    _run(
        template_id,
        lambda n, focus: quiz_services.topic_items(topic, n, focus),
        TOPIC_FOCUS,
    )


@shared_task(**_TASK)
def generate_word_template(template_id: int, user_id: int) -> None:
    from django.contrib.auth import get_user_model

    try:
        user = get_user_model().objects.get(pk=user_id)
    except get_user_model().DoesNotExist:
        logger.warning('quiz kullanıcısı bulunamadı, üretim atlandı: %s', user_id)
        return
    # Havuz bir kez okunuyor: her parça aynı havuzu görmeli, ayrıca iş
    # parçacıklarından DB'ye dokunmuyoruz (Django orada ayrı bağlantı açar).
    pool = quiz_services.word_pool(user)
    _run(
        template_id,
        lambda n, focus: quiz_services.word_items(pool, n, focus),
        WORD_FOCUS,
    )
