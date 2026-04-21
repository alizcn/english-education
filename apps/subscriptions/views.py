import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import access, services
from .models import Payment, Plan, Subscription

logger = logging.getLogger(__name__)


@login_required
def plans(request):
    state = access.get_state(request.user)
    plan_list = Plan.objects.filter(is_active=True)
    return render(request, 'subscriptions/plans.html', {
        'plans': plan_list,
        'state': state,
    })


@login_required
@require_POST
def checkout(request, slug):
    plan = get_object_or_404(Plan, slug=slug, is_active=True)

    payment = Payment.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price_try,
        conversation_id=services.new_conversation_id(),
    )
    callback_url = request.build_absolute_uri(reverse('subscriptions:callback'))
    # iyzico requires a publicly reachable URL. In local dev, SITE_URL env
    # overrides the host so tunnels (ngrok) can be plugged in.
    if settings.SITE_URL:
        callback_url = settings.SITE_URL.rstrip('/') + reverse('subscriptions:callback')

    try:
        result = services.initialize_checkout(
            user=request.user, plan=plan, payment=payment, callback_url=callback_url,
        )
    except Exception as exc:
        logger.exception('iyzico init failed')
        payment.status = Payment.STATUS_FAILED
        payment.error_message = str(exc)[:400]
        payment.save(update_fields=['status', 'error_message', 'updated_at'])
        messages.error(request, _('Ödeme başlatılamadı: %(error)s') % {'error': exc})
        return redirect('subscriptions:plans')

    payment.raw_init_response = result
    if result.get('status') != 'success':
        payment.status = Payment.STATUS_FAILED
        payment.error_message = result.get('errorMessage', '')[:400]
        payment.save()
        messages.error(request, _('iyzico: %(error)s') % {'error': result.get('errorMessage')})
        return redirect('subscriptions:plans')

    payment.iyzico_token = result.get('token', '')
    payment.save()

    return render(request, 'subscriptions/checkout.html', {
        'plan': plan,
        'payment': payment,
        'iyzico_form_content': result.get('checkoutFormContent', ''),
        'payment_page_url': result.get('paymentPageUrl', ''),
    })


@require_POST
def callback(request):
    """iyzico posts here after the user finishes the checkout form."""
    token = request.POST.get('token', '')
    if not token:
        return HttpResponse('missing token', status=400)

    payment = Payment.objects.filter(iyzico_token=token).first()
    if not payment:
        return HttpResponse('unknown token', status=404)

    try:
        result = services.retrieve_checkout(
            conversation_id=payment.conversation_id, token=token,
        )
    except Exception as exc:
        logger.exception('iyzico retrieve failed')
        payment.status = Payment.STATUS_FAILED
        payment.error_message = str(exc)[:400]
        payment.save(update_fields=['status', 'error_message', 'updated_at'])
        return redirect('subscriptions:failed', payment_id=payment.pk)

    payment.raw_verify_response = result

    is_successful = (
        result.get('status') == 'success'
        and result.get('paymentStatus') == 'SUCCESS'
    )

    if not is_successful:
        payment.status = Payment.STATUS_FAILED
        payment.error_message = (result.get('errorMessage') or 'payment failed')[:400]
        payment.save()
        return redirect('subscriptions:failed', payment_id=payment.pk)

    payment.status = Payment.STATUS_SUCCESS
    payment.iyzico_payment_id = str(result.get('paymentId', ''))

    subscription = Subscription.objects.create(
        user=payment.user,
        plan=payment.plan,
        status=Subscription.STATUS_PENDING,
    )
    subscription.activate()
    payment.subscription = subscription
    payment.save()

    return redirect('subscriptions:success', payment_id=payment.pk)


@login_required
def success(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
    return render(request, 'subscriptions/success.html', {'payment': payment})


@login_required
def failed(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
    return render(request, 'subscriptions/failed.html', {'payment': payment})


@login_required
def my_subscriptions(request):
    subs = (
        Subscription.objects
        .filter(user=request.user)
        .select_related('plan')
        .order_by('-created_at')
    )
    payments = (
        Payment.objects
        .filter(user=request.user)
        .select_related('plan')
        .order_by('-created_at')[:10]
    )
    return render(request, 'subscriptions/my_subscriptions.html', {
        'subscriptions': subs,
        'payments': payments,
    })


@login_required
@require_POST
def cancel_subscription(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    if sub.status != Subscription.STATUS_ACTIVE:
        messages.error(request, _('Bu abonelik zaten iptal ya da süresi dolmuş.'))
        return redirect('subscriptions:my')

    sub.status = Subscription.STATUS_CANCELLED
    sub.save(update_fields=['status', 'updated_at'])
    messages.success(
        request,
        _('Aboneliğin iptal edildi. Erişimin %(date)s tarihine kadar açık kalacak.')
        % {'date': sub.expires_at.strftime('%d %b %Y') if sub.expires_at else '-'}
    )
    return redirect('subscriptions:my')


@login_required
@require_POST
def resume_subscription(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    if sub.status != Subscription.STATUS_CANCELLED:
        messages.error(request, _('Sadece iptal edilmiş abonelikler devam ettirilebilir.'))
        return redirect('subscriptions:my')
    if not sub.expires_at or sub.expires_at <= timezone.now():
        messages.error(
            request,
            _('Bu aboneliğin süresi dolmuş. Yeni bir paket seçmen gerekiyor.')
        )
        return redirect('subscriptions:plans')

    sub.status = Subscription.STATUS_ACTIVE
    sub.save(update_fields=['status', 'updated_at'])
    messages.success(request, _('Aboneliğin tekrar aktif.'))
    return redirect('subscriptions:my')
