"""Centralised helpers for deciding what a user can currently do."""
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import Subscription, TrialUsage


@dataclass
class AccessState:
    is_subscribed: bool
    is_trial: bool
    trial_ends_at: Optional[object]
    trial_days_left: int
    subscription: Optional[Subscription]
    trial_usage: Optional[TrialUsage]

    @property
    def needs_upgrade(self) -> bool:
        return not self.is_subscribed

    @property
    def is_gated(self) -> bool:
        """True when the user must pay before accessing the rest of the site."""
        return not self.is_subscribed and not self.is_trial


def _ensure_trial(user) -> TrialUsage:
    trial, _ = TrialUsage.objects.get_or_create(
        user=user,
        defaults={'trial_ends_at': timezone.now() + timedelta(days=settings.TRIAL_DAYS)},
    )
    return trial


def get_state(user) -> AccessState:
    # Cancelled subscriptions keep access until expires_at, because the user
    # already paid for that period — cancellation stops future renewal only.
    sub = (
        Subscription.objects
        .filter(
            user=user,
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_CANCELLED],
            expires_at__gt=timezone.now(),
        )
        .select_related('plan')
        .first()
    )
    if sub:
        return AccessState(
            is_subscribed=True, is_trial=False,
            trial_ends_at=None, trial_days_left=0,
            subscription=sub, trial_usage=None,
        )
    trial = _ensure_trial(user)
    trial_active = trial.is_trial_active()
    return AccessState(
        is_subscribed=False,
        is_trial=trial_active,
        trial_ends_at=trial.trial_ends_at,
        trial_days_left=trial.days_left() if trial_active else 0,
        subscription=None,
        trial_usage=trial,
    )


def can_use_interview(state: AccessState) -> bool:
    if state.is_subscribed:
        return True
    if state.is_trial and state.trial_usage:
        return state.trial_usage.interview_count < settings.TRIAL_INTERVIEW_LIMIT
    return False


def can_use_chat(state: AccessState) -> bool:
    if state.is_subscribed:
        return True
    if state.is_trial and state.trial_usage:
        return state.trial_usage.chat_count < settings.TRIAL_CHAT_LIMIT
    return False


def can_use_bulk_translate(state: AccessState) -> bool:
    if state.is_subscribed:
        return True
    if state.is_trial and state.trial_usage:
        return state.trial_usage.bulk_translate_count < settings.TRIAL_BULK_TRANSLATE_LIMIT
    return False


def record_interview_use(state: AccessState) -> None:
    if state.is_subscribed or not state.trial_usage:
        return
    TrialUsage.objects.filter(pk=state.trial_usage.pk).update(
        interview_count=F('interview_count') + 1
    )


def record_chat_use(state: AccessState) -> None:
    if state.is_subscribed or not state.trial_usage:
        return
    TrialUsage.objects.filter(pk=state.trial_usage.pk).update(
        chat_count=F('chat_count') + 1
    )


def record_bulk_translate_use(state: AccessState) -> None:
    if state.is_subscribed or not state.trial_usage:
        return
    TrialUsage.objects.filter(pk=state.trial_usage.pk).update(
        bulk_translate_count=F('bulk_translate_count') + 1
    )
