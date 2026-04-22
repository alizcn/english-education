from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Plan(models.Model):
    slug = models.SlugField(unique=True, max_length=40)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    price_try = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'duration_days']

    def __str__(self):
        return f'{self.name} ({self.price_try}₺)'

    @property
    def price_str(self):
        return f'{self.price_try:.2f}'


class Subscription(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Beklemede')),
        (STATUS_ACTIVE, _('Aktif')),
        (STATUS_EXPIRED, _('Süresi doldu')),
        (STATUS_CANCELLED, _('İptal edildi')),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} · {self.plan.name} · {self.status}'

    def activate(self):
        now = timezone.now()
        self.starts_at = now
        self.expires_at = now + timedelta(days=self.plan.duration_days)
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=['status', 'starts_at', 'expires_at', 'updated_at'])

    def is_currently_active(self):
        if self.status != self.STATUS_ACTIVE:
            return False
        return self.expires_at is not None and self.expires_at > timezone.now()


class Payment(models.Model):
    STATUS_INITIALIZED = 'initialized'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_INITIALIZED, _('Başlatıldı')),
        (STATUS_SUCCESS, _('Başarılı')),
        (STATUS_FAILED, _('Başarısız')),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='payments')
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIALIZED)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='TRY')
    conversation_id = models.CharField(max_length=64, unique=True)
    iyzico_token = models.CharField(max_length=128, blank=True, db_index=True)
    iyzico_payment_id = models.CharField(max_length=64, blank=True)
    error_message = models.CharField(max_length=400, blank=True)
    raw_init_response = models.JSONField(default=dict, blank=True)
    raw_verify_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} · {self.plan.name} · {self.status}'


class TrialUsage(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trial_usage')
    trial_started_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField()
    interview_count = models.PositiveIntegerField(default=0)
    chat_count = models.PositiveIntegerField(default=0)
    bulk_translate_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.user} trial → {self.trial_ends_at:%Y-%m-%d}'

    def is_trial_active(self):
        return timezone.now() < self.trial_ends_at

    def days_left(self):
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days + (1 if delta.seconds else 0))
