from django.shortcuts import redirect
from django.urls import reverse

from . import access


ALLOWED_PREFIXES = (
    '/admin/',
    '/static/',
    '/i18n/',
    '/accounts/',
    '/abonelik/',
    '/favicon',
)


class SubscriptionGateMiddleware:
    """
    After trial expires and no active subscription, authenticated users are
    redirected to the plans page. Landing, auth, admin, static, language
    switch and the subscription flow itself remain accessible.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_staff:
            path = request.path
            if not any(path.startswith(p) for p in ALLOWED_PREFIXES):
                state = access.get_state(user)
                if state.is_gated:
                    return redirect(reverse('subscriptions:plans'))
        return self.get_response(request)
