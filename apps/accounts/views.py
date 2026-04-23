import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

from .forms import ProfileForm, SignupForm
from .models import UserConsent

logger = logging.getLogger(__name__)


def _client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


@ratelimit(key='ip', rate='10/h', method='POST', block=False)
def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if getattr(request, 'limited', False):
        messages.error(request, _('Çok fazla kayıt denemesi. Biraz sonra tekrar dene.'))
        return redirect('accounts:signup')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserConsent.objects.create(
                user=user,
                kind=UserConsent.KVKK,
                ip_address=_client_ip(request) or None,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:400],
            )
            login(request, user)
            logger.info('account_created: user_id=%s username=%s', user.pk, user.username)
            return redirect('dashboard:home')
    else:
        form = SignupForm()
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Profilin güncellendi.'))
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def delete_account(request):
    if request.method == 'POST':
        confirm = (request.POST.get('confirm') or '').strip().lower()
        if confirm != (request.user.username or '').lower():
            messages.error(request, _('Onay için kullanıcı adını doğru yaz.'))
            return redirect('accounts:delete_account')
        user_id = request.user.pk
        username = request.user.username
        user = request.user
        logout(request)
        user.delete()
        logger.info('account_deleted: user_id=%s username=%s', user_id, username)
        messages.success(request, _('Hesabın silindi.'))
        return redirect('accounts:login')
    return render(request, 'accounts/delete_account.html')
