"""Canonical/alternate URL üretimi için ortak yardımcılar."""
from django.conf import settings
from django.urls import translate_url


def site_url() -> str:
    return settings.SITE_URL.rstrip('/')


def absolute(path: str) -> str:
    """Göreli yolu canonical köküne bağlar. Zaten mutlaksa dokunmaz."""
    if not path:
        return site_url() + '/'
    if path.startswith(('http://', 'https://')):
        return path
    return site_url() + ('/' + path.lstrip('/'))


def canonical_for(request) -> str:
    """
    Sorgu parametreleri canonical'a girmez — tek istisna sayfalama (`page`),
    çünkü sayfalı listelerin her sayfası kendi kanoniğidir.
    """
    url = absolute(request.path)
    page = request.GET.get('page')
    if page and page.isdigit() and int(page) > 1:
        url = f'{url}?page={page}'
    return url


def language_alternates(request):
    """
    i18n_patterns altındaki her dil için hreflang adayı üretir.
    Çevirisi olmayan/eşlenemeyen yollar sessizce atlanır.
    """
    out = []
    path = request.path
    for code, _name in settings.LANGUAGES:
        try:
            translated = translate_url(path, code)
        except Exception:  # noqa: BLE001 - reverse edilemeyen yollar (admin vb.)
            continue
        out.append({'code': code, 'url': absolute(translated)})
    return out
