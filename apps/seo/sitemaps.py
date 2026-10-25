"""sitemap.xml kaynakları.

Tüm haritalar `SITE_URL`'i zorlar: sitemap'in request host'una göre değişmesi
(www / çıplak alan adı karışması) canonical ile çelişir ve Search Console'da
"alternate page with proper canonical tag" uyarısı üretir.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Count
from django.urls import reverse

from apps.topics.models import Topic
from apps.wordbank.models import BankWord
from services import languages

from .views import PUBLIC_TARGET, WORDS_PER_PAGE


class _CanonicalSite:
    """django.contrib.sites kurulu değil; sitemap view'ının beklediği arayüz."""

    def __init__(self):
        parts = urlsplit(settings.SITE_URL)
        self.domain = parts.netloc
        self.name = settings.SITE_NAME
        self.scheme = parts.scheme or 'https'


class BaseSitemap(Sitemap):
    i18n = True
    alternates = True
    x_default = True
    protocol = 'https'

    def get_urls(self, page=1, site=None, protocol=None):
        canonical = _CanonicalSite()
        return super().get_urls(page=page, site=canonical, protocol=canonical.scheme)


class StaticViewSitemap(BaseSitemap):
    changefreq = 'weekly'

    # Hedef dil gerektiren yollar `lang` kwarg'ı alıyor.
    _PRIORITIES = {
        'dashboard:home': 1.0,
        'seo:grammar_index': 0.9,
        'seo:words_index': 0.9,
        'seo:interview_index': 0.9,
        'seo:html_sitemap': 0.3,
        'seo:licenses': 0.2,
        'seo:privacy_policy': 0.2,
        'seo:terms_of_service': 0.2,
        'dashboard:install_guide': 0.4,
        'accounts:signup': 0.6,
    }
    _NEEDS_TARGET = {'seo:grammar_index', 'seo:words_index', 'seo:interview_index'}

    def items(self):
        return list(self._PRIORITIES)

    def location(self, item):
        if item in self._NEEDS_TARGET:
            return reverse(item, kwargs={'lang': PUBLIC_TARGET})
        return reverse(item)

    def priority(self, item):
        return self._PRIORITIES[item]


class LearnLandingSitemap(BaseSitemap):
    """Hedef dil giriş sayfaları — `/learn-english/` ve kardeşleri.

    `StaticViewSitemap` hedef gerektiren yolları yalnızca `PUBLIC_TARGET` için
    yayınlıyor; bu sayfalar ise var olma sebebi dil başına ayrı olmak olan tek
    yüzey. DÖRDÜ DE burada: `/learn-english/` bir ara `/`ye yönlendiriliyordu
    (o zaman `/` İngilizce landing'iydi), artık kendi hedefli sayfası var.
    """
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        return list(languages.LEARNABLE_CODES)

    def location(self, code):
        return reverse('seo:learn_landing', kwargs={'lang': code})


class GrammarTopicSitemap(BaseSitemap):
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        # Yalnızca halka açık hedef dil; diğer diller Faz 3'te kendi
        # slug kökleriyle (`<target>-grammar/`) sitemap'e girecek.
        return Topic.objects.filter(language=PUBLIC_TARGET).order_by('order', 'name')

    def location(self, obj):
        return reverse('seo:grammar_detail',
                       kwargs={'lang': obj.language, 'slug': obj.slug})

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at


class WordLevelSitemap(BaseSitemap):
    changefreq = 'monthly'

    def items(self):
        counts = {
            row['level']: row['c']
            for row in BankWord.objects.filter(language=PUBLIC_TARGET)
                                       .values('level').annotate(c=Count('id'))
        }
        items = []
        for code, _label in BankWord.LEVELS:
            total = counts.get(code, 0)
            if not total:
                continue
            pages = (total + WORDS_PER_PAGE - 1) // WORDS_PER_PAGE
            items.extend((code, p) for p in range(1, pages + 1))
        return items

    def location(self, item):
        level, page = item
        url = reverse('seo:words_level',
                      kwargs={'lang': PUBLIC_TARGET, 'level': level.lower()})
        return url if page == 1 else f'{url}?page={page}'

    def priority(self, item):
        # İlk sayfa hub'a en yakın; derin sayfalar daha düşük ağırlıklı.
        return 0.8 if item[1] == 1 else 0.4


SITEMAPS = {
    'static': StaticViewSitemap,
    'learn': LearnLandingSitemap,
    'grammar': GrammarTopicSitemap,
    'words': WordLevelSitemap,
}
