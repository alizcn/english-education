"""Canonical/alternate URL üretimi için ortak yardımcılar."""
from django.conf import settings
from django.urls import Resolver404, resolve, translate_url


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
    """i18n_patterns altındaki her dil için hreflang adayı üretir.

    İki şeye dikkat:

    * `translate_url` istisna FIRLATMIYOR — `Resolver404` ve `NoReverseMatch`'i
      içeride yutup URL'i olduğu gibi geri veriyor. Eskiden buradaki
      `except Exception: continue` bu yüzden hiç çalışmıyordu ve çözümlenemeyen
      bir yolda her dil aynı (çevrilmemiş) adresi işaret eden yinelenmiş
      hreflang üretiliyordu. Artık yolu önce kendimiz çözüyoruz ve
      çözülemiyorsa hiç iddia basmıyoruz.
    * Sorgu dizesi `get_full_path()` ile taşınıyor: `canonical_for` `?page=N`
      koruduğu için alternates de korumak zorunda, yoksa sayfalı listelerde
      hreflang kümesi canonical ile çelişiyor. `translate_url` yolu yeniden
      kurarken `parsed.query`yi koruyor, bu yüzden tam yolu vermek yeterli.
    """
    try:
        resolve(request.path)
    except Resolver404:
        return []

    full_path = request.get_full_path()
    out = []
    for code, _name in settings.LANGUAGES:
        out.append({
            'code': code,
            'url': absolute(translate_url(full_path, code)),
        })
    return out
