"""Kurs prefix'i olmayan eski uygulama yollarını aktif kursa taşır.

`/topics/present-simple/` → `/learn/en/topics/present-simple/`

**302, 301 DEĞİL** ve `Cache-Control: private`: hedef, isteği yapan
kullanıcının aktif kursuna bağlı. Kalıcı yönlendirme ya da paylaşılan cache,
bir kullanıcının Almanca kursunu başkasının tarayıcısına yazardı.

Bu liste SEO'nun `legacy_urls.py`sinden ayrı: oradakiler indekslenmiş Türkçe
slug'lar için dondurulmuş 301'ler, buradakiler oturum içi yollar.
"""

from django.http import HttpResponsePermanentRedirect  # noqa: F401 (belge amaçlı)
from django.shortcuts import redirect
from django.urls import path, re_path

from .current import get_current_target_or_default
from .prefix import PREFIX_ROOT

#: Kurs kapsamına alınan uygulama kökleri.
APP_ROOTS = ('words', 'topics', 'quiz', 'chat', 'wordbank', 'interviews')


def _to_course(request, root, rest=''):
    target = get_current_target_or_default()
    response = redirect(f'/{PREFIX_ROOT}/{target}/{root}/{rest}', permanent=False)
    # Paylaşılan cache'e yazılmamalı: hedef kullanıcıya özel.
    response['Cache-Control'] = 'private, no-store'
    return response


urlpatterns = [
    re_path(
        rf'^(?P<root>{"|".join(APP_ROOTS)})/(?P<rest>.*)$',
        lambda request, root, rest: _to_course(request, root, rest),
    ),
    path(
        'learn-switch/',
        lambda request: redirect('learn:courses'),
    ),
]
