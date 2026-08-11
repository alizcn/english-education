"""Mülakat sorusu üretimi — arka plan görevleri.

Her soru dört uzun alan içeriyor (TR/EN soru + TR/EN detaylı cevap), yani üretim
saniyeler değil dakikalar sürebiliyor. Bu süre HTTP request path'inde tutulamaz:
gunicorn worker'ı bloke eder ve birkaç eşzamanlı istek tüm worker'ları doldurur.
View'ler bu yüzden PENDING bir oturum açıp işi buraya devrediyor, kullanıcı
detay sayfasında sonucu bekliyor.

Üretim tek çağrı değil, paralel parçalar hâlinde yapılıyor. Çıktı tokeni seri
üretildiği için tek büyük çağrının süresi ürettiği metinle doğru orantılı; işi
bölmek hem toplam süreyi düşürüyor hem de ilk soruları çok daha erken veriyor.
CLI transport'unda ölçüm (Haiku 4.5, 10 soru):

    tek çağrı   : 80.6s, kullanıcı 80s boyunca boş ekran görüyor
    5x2 paralel : 41.8s toplam, ilk parça 21.8s'de ekranda

Parçalar bittikçe oturuma yazılıyor (status PENDING kalır), böylece detay sayfası
soruları damla damla gösterebiliyor.
"""

import logging

from celery import shared_task
from django.utils.translation import gettext as _

from services import claude_client as claude
from .models import InterviewSession

logger = logging.getLogger(__name__)

QUESTION_COUNT = 10
# Parça başına soru. Küçük parça = ilk sonuç daha erken, ama paralel çağrılar
# birbirini yavaşlattığı için 5 parçadan sonrası toplam süreyi düşürmüyor.
CHUNK_SIZE = 2

# Her parçaya ayrı konu veriliyor; yoksa parçalar birbirinin sorusunu üretiyor.
FOCUS_TOPICS = [
    'core language, framework and tooling fundamentals',
    'system design and architecture decisions',
    'data modeling, performance and scalability',
    'testing, debugging and code quality',
    'behavioral, teamwork and situational scenarios',
]


def _chunk_plan(total: int) -> list[tuple[int, str]]:
    """(soru_sayısı, odak) parçalarına böler; odaklar sırayla dağıtılır."""
    plan = []
    remaining = total
    while remaining > 0:
        size = min(CHUNK_SIZE, remaining)
        plan.append((size, FOCUS_TOPICS[len(plan) % len(FOCUS_TOPICS)]))
        remaining -= size
    return plan


def _dedupe(items: list[dict], seen: set) -> list[dict]:
    """Parçalar farklı odaklara rağmen aynı soruyu üretebiliyor; ingilizce soruya göre teker."""
    fresh = []
    for it in items:
        key = (it.get('question_en') or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        fresh.append(it)
    return fresh


def _fail(session: InterviewSession, message: str) -> None:
    session.status = InterviewSession.FAILED
    session.error_message = message[:300]
    session.save(update_fields=['status', 'error_message'])


def _run(session_id: int, produce) -> None:
    """Ortak akış: parçaları paralel üret, bitenleri hemen yaz, hatayı kullanıcıya taşı.

    `produce(n, focus)` tek bir parçayı üretir.
    """
    try:
        session = InterviewSession.objects.get(pk=session_id)
    except InterviewSession.DoesNotExist:
        # Kullanıcı beklerken silmiş olabilir; yeniden denemenin anlamı yok.
        logger.warning('mülakat oturumu bulunamadı, üretim atlandı: %s', session_id)
        return

    if session.status == InterviewSession.READY:
        # acks_late yeniden teslim ettiyse: iş zaten bitmiş, tekrar üretme.
        logger.info('mülakat zaten hazır, yeniden üretim atlandı: %s', session_id)
        return

    # Yeniden teslimde yarım kalmış parçaların üstüne eklemeyelim.
    if session.questions_data:
        session.questions_data = []
        session.save(update_fields=['questions_data'])

    plan = _chunk_plan(QUESTION_COUNT)
    collected: list[dict] = []
    seen: set = set()
    first_error: Exception | None = None

    for _index, items, error in claude.parallel_map(lambda p: produce(*p), plan):
        if error is not None:
            first_error = first_error or error
            continue
        fresh = _dedupe(items or [], seen)
        if not fresh:
            continue
        collected.extend(fresh)
        # Kısmi sonucu hemen görünür kıl: kullanıcı hepsini beklemesin.
        session.questions_data = collected
        session.save(update_fields=['questions_data'])

    if not collected:
        if isinstance(first_error, claude.ClaudeClientError):
            logger.warning('mülakat üretimi başarısız (session=%s): %s', session_id, first_error)
            _fail(session, str(first_error))
        elif first_error is not None:
            logger.exception(
                'mülakat üretiminde beklenmedik hata (session=%s)', session_id, exc_info=first_error,
            )
            _fail(session, _('Sorular üretilirken beklenmedik bir hata oluştu.'))
        else:
            _fail(session, _('Sorular üretilemedi. Tekrar deneyin.'))
        return

    # Parçaların bir kısmı düşse bile eldekini teslim ediyoruz; hiç yoktan iyi.
    if first_error is not None:
        logger.warning(
            'mülakat kısmi üretildi (session=%s, soru=%d): %s', session_id, len(collected), first_error,
        )

    session.questions_data = collected
    session.status = InterviewSession.READY
    session.error_message = ''
    session.save(update_fields=['questions_data', 'status', 'error_message'])
    logger.info('mülakat hazır (session=%s, soru=%d)', session_id, len(collected))


# Süre limitleri iç içe geçmiş bir merdiven; bozarsan ya görev boşuna ölür ya da
# aynı iş iki kez çalışır:
#   CLAUDE_CLI_TIMEOUT (600) < soft_time_limit (660) < time_limit (720)
#   < broker visibility_timeout (900, config/settings.py)
# Parçalar paralel koştuğu için toplam süre en yavaş parçaya bağlı, toplamlarına değil;
# merdiven bu yüzden parça sayısından bağımsız geçerli kalıyor.
SOFT_TIME_LIMIT = 660
HARD_TIME_LIMIT = 720

# acks_late + reject_on_worker_lost: worker deploy/restart sırasında ölürse görev
# broker'a geri döner ve yeniden teslim edilir. Aksi halde mesaj alındığı anda
# ack'lendiği için oturum sonsuza kadar "Hazırlanıyor"da kalırdı.
_TASK = dict(
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=SOFT_TIME_LIMIT,
    time_limit=HARD_TIME_LIMIT,
)


@shared_task(**_TASK)
def generate_from_title(session_id: int, job_title: str) -> None:
    _run(session_id, lambda n, focus: claude.generate_interview_questions(job_title, n=n, focus=focus))


@shared_task(**_TASK)
def generate_from_cv(session_id: int, cv_text: str) -> None:
    _run(session_id, lambda n, focus: claude.generate_interview_from_cv(cv_text, n=n, focus=focus))
