import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.quizzes.models import QuizSession
from .models import UserLevel

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_level(sender, instance, created, **kwargs):
    if created:
        UserLevel.objects.get_or_create(user=instance)


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
    level, _ = UserLevel.objects.get_or_create(user_id=instance.user_id)
    level.advance(score)
    setattr(instance, cache_attr, True)
    logger.info(
        'userlevel advance user=%s +%s score=%s level=%s',
        instance.user_id, score, level.score, level.current_level,
    )
