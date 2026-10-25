"""Halka açık SEO sayfaları.

İki eksen URL'de ayrışıyor:

* **Hedef dil** slug kökünde: `/english-grammar/`, `/german-grammar/`
* **Arayüz (ve anlatım) dili** `i18n_patterns` prefix'inde: `/en/...`

Örnekler::

    /english-grammar/              TR arayüz, İngilizce öğreniyor   ← MEVCUT
    /en/english-grammar/           EN arayüz, İngilizce öğreniyor   ← MEVCUT
    /en/turkish-grammar/           EN arayüz, Türkçe öğreniyor      ← yeni
    /de/french-grammar/            DE arayüz, Fransızca öğreniyor   ← yeni

İndekslenmiş adresler bayt bayt korunuyor: converter sayesinde
`/english-grammar/` aynı URL, aynı view. Eski Türkçe slug'lar
`legacy_urls` içinden kalıcı olarak (301) yeni adreslere taşınır.
"""
from django.urls import path, register_converter

from . import views
from .converters import TargetLangConverter

register_converter(TargetLangConverter, 'target')

app_name = 'seo'

urlpatterns = [
    # Hedef dil giriş sayfaları — DÖRDÜ DE. `/learn-english/` bir ara `/`ye
    # yönlendiriliyordu çünkü `/` İngilizce landing'iydi ve iki adres aynı
    # metni gösterirdi. Artık `/` platformu anlatan GENEL sayfa, dolayısıyla
    # İngilizce'nin de kendi hedefli sayfası var.
    path('learn-<target:lang>/', views.learn_landing, name='learn_landing'),
    path('<target:lang>-grammar/', views.grammar_index, name='grammar_index'),
    path('<target:lang>-grammar/<slug:slug>/', views.grammar_detail, name='grammar_detail'),
    path('<target:lang>-vocabulary/', views.words_index, name='words_index'),
    path('<target:lang>-vocabulary/<slug:level>/', views.words_level, name='words_level'),
    path('<target:lang>-interview-questions/', views.interview_index, name='interview_index'),
    path('sitemap/', views.html_sitemap, name='html_sitemap'),
    # Slug çevrilmiyor: `sitemap/` gibi diğer yardımcı sayfalar da tek
    # biçimde duruyor ve adres dört arayüz dilinde aynı kalıyor.
    path('licenses/', views.licenses, name='licenses'),
    path('gizlilik-politikasi/', views.privacy_policy, name='privacy_policy'),
    path('kullanim-kosullari/', views.terms_of_service, name='terms_of_service'),
    path('llm.txt', views.llm_txt, name='llm_txt'),
    # i18n_patterns içinde: her dil kendi manifestini alıyor ve start_url o
    # dilin prefix'ini taşıyor.
    path('manifest.webmanifest', views.manifest, name='manifest'),
]
