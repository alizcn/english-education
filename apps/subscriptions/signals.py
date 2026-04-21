from datetime import timedelta

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import TrialUsage


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_trial_on_signup(sender, instance, created, **kwargs):
    if not created:
        return
    TrialUsage.objects.get_or_create(
        user=instance,
        defaults={
            'trial_ends_at': timezone.now() + timedelta(days=settings.TRIAL_DAYS),
        },
    )
