"""iyzico Checkout Form wrapper.

Docs: https://docs.iyzico.com/en/api/checkout-form
"""
import json
import uuid
from typing import Dict

import iyzipay
from django.conf import settings


def _options() -> Dict[str, str]:
    # iyzipay SDK expects a bare hostname (no scheme/trailing slash) because
    # it feeds this directly to http.client.HTTPSConnection.
    base = settings.IYZICO_BASE_URL
    for prefix in ('https://', 'http://'):
        if base.startswith(prefix):
            base = base[len(prefix):]
            break
    base = base.rstrip('/')
    return {
        'api_key': settings.IYZICO_API_KEY,
        'secret_key': settings.IYZICO_SECRET_KEY,
        'base_url': base,
    }


def new_conversation_id() -> str:
    return uuid.uuid4().hex


def _buyer_dict(user) -> dict:
    """
    Mandatory buyer fields per iyzico docs. We don't collect most of these —
    fill defaults so sandbox accepts the request. Production should gather
    real identity + address.
    """
    name = user.first_name or user.username or 'User'
    surname = user.last_name or 'User'
    email = user.email or f'{user.username}@example.com'
    return {
        'id': f'U{user.pk}',
        'name': name,
        'surname': surname,
        'gsmNumber': '+905350000000',
        'email': email,
        'identityNumber': '74300864791',
        'registrationAddress': 'Kemeralti Mah. Sok. No:1',
        'ip': '127.0.0.1',
        'city': 'Istanbul',
        'country': 'Turkey',
        'zipCode': '34000',
    }


def _address_dict(user) -> dict:
    name = (user.first_name or user.username or 'User')
    surname = (user.last_name or 'User')
    return {
        'contactName': f'{name} {surname}',
        'city': 'Istanbul',
        'country': 'Turkey',
        'address': 'Kemeralti Mah. Sok. No:1',
        'zipCode': '34000',
    }


def initialize_checkout(*, user, plan, payment, callback_url: str) -> dict:
    """
    Create a hosted Checkout Form session on iyzico.
    Returns dict with keys: status, paymentPageUrl, token, checkoutFormContent, errorMessage.
    """
    basket_item = {
        'id': plan.slug,
        'name': plan.name,
        'category1': 'Egitim',
        'itemType': 'VIRTUAL',
        'price': plan.price_str,
    }
    request = {
        'locale': 'tr',
        'conversationId': payment.conversation_id,
        'price': plan.price_str,
        'paidPrice': plan.price_str,
        'currency': 'TRY',
        'basketId': f'B{payment.pk}',
        'paymentGroup': 'PRODUCT',
        'callbackUrl': callback_url,
        'enabledInstallments': [1, 2, 3, 6, 9],
        'buyer': _buyer_dict(user),
        'shippingAddress': _address_dict(user),
        'billingAddress': _address_dict(user),
        'basketItems': [basket_item],
    }

    raw = iyzipay.CheckoutFormInitialize().create(request, _options())
    body = raw.read().decode('utf-8')
    return json.loads(body)


def retrieve_checkout(*, conversation_id: str, token: str) -> dict:
    request = {
        'locale': 'tr',
        'conversationId': conversation_id,
        'token': token,
    }
    raw = iyzipay.CheckoutForm().retrieve(request, _options())
    body = raw.read().decode('utf-8')
    return json.loads(body)
