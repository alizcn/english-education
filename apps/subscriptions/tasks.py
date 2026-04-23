import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def expire_subscriptions_task():
    """Celery beat üzerinden günlük çalıştırılır."""
    logger.info('expire_subscriptions_task: starting')
    call_command('expire_subscriptions')
