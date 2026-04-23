import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.subscriptions.models import Subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Süresi dolmuş abonelikleri STATUS_EXPIRED olarak işaretler.'

    def handle(self, *args, **options):
        now = timezone.now()
        qs = Subscription.objects.filter(
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_CANCELLED],
            expires_at__lte=now,
        )
        count = qs.update(status=Subscription.STATUS_EXPIRED, updated_at=now)
        logger.info('expire_subscriptions: %s rows updated', count)
        self.stdout.write(self.style.SUCCESS(
            f'{count} abonelik STATUS_EXPIRED olarak işaretlendi.'
        ))
