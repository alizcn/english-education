"""Her şablona canonical/hreflang/OG ve dil listesi için ortak bağlamı verir."""
from django.conf import settings
from django.templatetags.static import static
from django.utils.translation import get_language

from services import languages

from .utils import absolute, canonical_for, language_alternates


def _ui_languages(active):
    """Dil seçicinin ve JSON-LD'nin kullandığı liste.

    Sicil sırasını korur (varsayılan dil başta) ve aktif dili işaretler, böylece
    şablon ikili `{% if %}` kurmak zorunda kalmıyor — üç ya da dört dilde de
    aynı döngü çalışıyor.
    """
    return [
        {
            'code': spec.code,
            'native_name': spec.native_name,
            'english_name': spec.english_name,
            'og_locale': spec.og_locale,
            'is_active': spec.code == active,
        }
        for spec in languages.UI_LANGUAGES
    ]


def seo(request):
    # Admin ve superadmin panelleri indekslenmez; boşuna URL çevirisi yapma.
    path = request.path
    if path.startswith(('/levelenai-admin/', '/super/')):
        return {'seo': {'site_name': settings.SITE_NAME, 'skip': True}}

    active = get_language()
    alternates = language_alternates(request)

    # x-default İngilizce: dört dilden hiçbirini bilmeyen bir ziyaretçiyi
    # okuyamadığı Türkçe sayfaya göndermek yerine ortak paydaya yönlendiriyoruz.
    # Türkçe kendi hreflang="tr" iddiasını ve öneksiz kanoniğini koruyor, yani
    # TR trafiği bundan etkilenmiyor.
    #
    # `alternates` boşsa (çözümlenemeyen yol — 404) hiç dil iddiası basmıyoruz:
    # var olmayan bir adres için hreflang vermek arama motoruna yanlış sinyal.
    x_default = ''
    if alternates:
        x_default = next(
            (a['url'] for a in alternates if a['code'] == 'en'),
            next((a['url'] for a in alternates if a['code'] == settings.LANGUAGE_CODE),
                 absolute(path)),
        )

    ui_languages = _ui_languages(active)
    try:
        active_locale = languages.get(active).og_locale
    except languages.UnknownLanguage:
        active_locale = languages.get(settings.LANGUAGE_CODE).og_locale

    return {
        'seo': {
            'skip': False,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
            'canonical': canonical_for(request),
            'alternates': alternates,
            'x_default': x_default,
            'default_image': absolute(static(settings.SEO_DEFAULT_IMAGE)),
            'twitter': settings.SEO_TWITTER_HANDLE,
            'google_verification': settings.GOOGLE_SITE_VERIFICATION,
            'ga_id': settings.GA_MEASUREMENT_ID,
            'turnstile_site_key': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
            # --- dil ekseni ---
            'ui_languages': ui_languages,
            'ui_codes': [item['code'] for item in ui_languages],
            'active_language': active,
            'og_locale': active_locale,
            'og_locale_alternates': [
                item['og_locale'] for item in ui_languages if not item['is_active']
            ],
            # robots.txt'in dil prefix'lerini döngüyle basması için: varsayılan
            # dil öneksiz olduğu için '' ile başlıyor.
            'lang_prefixes': [
                '' if item['code'] == settings.LANGUAGE_CODE else f"/{item['code']}"
                for item in ui_languages
            ],
        }
    }
