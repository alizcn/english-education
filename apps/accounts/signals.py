import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.quizzes.models import QuizSession

from .models import UserCourse

logger = logging.getLogger(__name__)


# NOT: `post_save(AUTH_USER_MODEL)` ile otomatik kurs AÇMIYORUZ.
#
# Sinyalin `request`e erişimi yok, dolayısıyla kullanıcının ana dilini
# bilemiyor. İngilizce konuşan bir kullanıcıya `native_language='tr'` kurs
# açmak sessiz bir veri hatası olurdu — kullanıcı anlamadığı bir dilde
# anlatım görürdü ve bunu düzeltmek için kursu silmesi gerekirdi.
#
# Kurs artık dili bilen yerlerde açılıyor:
#   * `apps/accounts/views.py` signup — aktif arayüz dilinden
#   * `apps/accounts/services.ensure_active_course` — eski kullanıcılar için
#     ilk istekte, aktif arayüz diline göre
# Bkz. `apps/accounts/services.py` modül docstring'i.


@receiver(post_save, sender=QuizSession)
def award_score_on_quiz_finish(sender, instance: QuizSession, created, update_fields=None, **kwargs):
    if created or not instance.finished_at:
        return
    # Sadece bitmiş oturumlar puan verir. Çifte puan önleme: session cache key.
    cache_attr = '_level_awarded'
    if getattr(instance, cache_attr, False):
        return
    score = instance.correct_count - (instance.wrong_count // 2)
    if score <= 0:
        return

    # Puan, oturumun AİT OLDUĞU kursa yazılır. Kullanıcının birden çok kursu
    # olabildiği için `filter(user=...)` tek başına yetmiyor; Almanca quizinin
    # puanı İngilizce seviyesini yükseltemez.
    course = UserCourse.objects.filter(
        user_id=instance.user_id,
        target_language=instance.target_language,
    ).first()
    if course is None:
        logger.warning(
            'quiz bitti ama kurs yok, puan yazılmadı (user=%s, target=%s)',
            instance.user_id, instance.target_language,
        )
        return

    course.advance(score)
    setattr(instance, cache_attr, True)
    logger.info(
        'kurs ilerledi user=%s target=%s +%s score=%s level=%s',
        instance.user_id, instance.target_language, score,
        course.score, course.current_level,
    )
