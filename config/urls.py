from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin

admin.site.site_header = 'LevelEnAI Yönetim'
admin.site.site_title = 'LevelEnAI Admin'
admin.site.index_title = 'Kontrol Paneli'
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include

from apps.learn.prefix import course_patterns
from apps.seo.sitemaps import SITEMAPS
from apps.seo.views import robots_txt

# Dile bağlı olmayan yollar: panel ve arama motoru dosyaları.
urlpatterns = [
    path('levelenai-admin/', admin.site.urls),
    path('super/', include('apps.superadmin.urls')),
    path('robots.txt', robots_txt, name='robots_txt'),
    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': SITEMAPS},
        name='django.contrib.sitemaps.views.sitemap',
    ),
]

# Türkçe varsayılan dil olduğu için öneksiz kalır (/konu), İngilizce /en/ alır.
# Böylece mevcut TR URL'leri bozulmaz ve her dil kendi kanonik adresine sahip olur.
urlpatterns += i18n_patterns(
    # set_language i18n_patterns İÇİNDE: aksi halde /en/... bir sayfadan TR'ye
    # dönerken aktif dil tr olduğu için translate_url yolu çözemiyor ve
    # kullanıcı İngilizce URL'de kalıyor.
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('apps.accounts.urls')),
    path('', include('apps.dashboard.urls')),
    # Uygulama yolları kurs prefix'i altında: /learn/<hedef_dil>/topics/...
    # Prefix otomatik eklendiği için şablonlardaki {% url %} çağrılarının
    # hiçbiri değişmiyor (bkz. apps/learn/prefix.py).
    *course_patterns(
        path('words/', include('apps.vocabulary.urls')),
        path('topics/', include('apps.topics.urls')),
        path('quiz/', include('apps.quizzes.urls')),
        path('chat/', include('apps.chat.urls')),
        path('wordbank/', include('apps.wordbank.urls')),
        path('interviews/', include('apps.interviews.urls')),
    ),
    path('learn/', include('apps.learn.urls')),
    path('', include('apps.seo.urls')),
    # Eski Türkçe slug'lar → yeni İngilizce adresler (301). En sonda: gerçek
    # yollar önce eşleşsin, yönlendirmeler yalnız artakalan istekleri yakalasın.
    path('', include('apps.seo.legacy_urls')),
    # Kurs prefix'i olmayan uygulama yolları → aktif kursa 302. seo'nun
    # dondurulmuş 301'lerinden SONRA: o adresler buraya düşmemeli.
    path('', include('apps.learn.legacy')),
    prefix_default_language=False,
)

handler404 = 'apps.seo.views.not_found'
handler500 = 'apps.seo.views.server_error'
