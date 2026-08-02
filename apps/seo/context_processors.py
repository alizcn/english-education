"""Her şablona canonical/hreflang/OG için gereken ortak SEO bağlamını verir."""
from django.conf import settings
from django.templatetags.static import static

from .utils import absolute, canonical_for, language_alternates


def seo(request):
    # Admin ve superadmin panelleri indekslenmez; boşuna URL çevirisi yapma.
    path = request.path
    if path.startswith(('/levelenai-admin/', '/super/')):
        return {'seo': {'site_name': settings.SITE_NAME, 'skip': True}}

    alternates = language_alternates(request)
    default_alt = next(
        (a['url'] for a in alternates if a['code'] == settings.LANGUAGE_CODE),
        absolute(path),
    )
    return {
        'seo': {
            'skip': False,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
            'canonical': canonical_for(request),
            'alternates': alternates,
            'x_default': default_alt,
            'default_image': absolute(static(settings.SEO_DEFAULT_IMAGE)),
            'twitter': settings.SEO_TWITTER_HANDLE,
            'google_verification': settings.GOOGLE_SITE_VERIFICATION,
            'ga_id': settings.GA_MEASUREMENT_ID,
        }
    }
