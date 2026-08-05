"""Eski Türkçe slug'lardan yeni İngilizce adreslere kalıcı yönlendirmeler.

URL'ler İngilizceye geçirilirken indekslenmiş bağlantıların ölmemesi gerekiyor:
arama sonuçları, paylaşılan linkler ve dış siteler hâlâ eski adresleri işaret
ediyor. `RedirectView` 301 döndürdüğü için arama motorları sinyali yeni adrese
taşır; `pattern_name` sayesinde slug/level parametreleri de birlikte gider.

Bu liste bilinçli olarak dondurulmuştur — yeni yollar buraya eklenmez.
"""
from django.urls import path
from django.views.generic import RedirectView


def _moved(pattern_name):
    return RedirectView.as_view(pattern_name=pattern_name, permanent=True)


urlpatterns = [
    path('ingilizce-gramer/', _moved('seo:grammar_index')),
    path('ingilizce-gramer/<slug:slug>/', _moved('seo:grammar_detail')),
    path('ingilizce-kelimeler/', _moved('seo:words_index')),
    path('ingilizce-kelimeler/<slug:level>/', _moved('seo:words_level')),
    path('ingilizce-mulakat-sorulari/', _moved('seo:interview_index')),
    path('site-haritasi/', _moved('seo:html_sitemap')),
    path('uygulamayi-yukle/', _moved('dashboard:install_guide')),
    path('accounts/profil/', _moved('accounts:profile')),
    path('accounts/hesap-sil/', _moved('accounts:delete_account')),
]

# İngilizce tarafta hiçbir adres değişmedi: /en/... yolları zaten bu slug'ları
# kullanıyordu, bu yüzden EN için yönlendirmeye gerek yok.
