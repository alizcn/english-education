"""Halka açık SEO sayfaları.

Yollar çevrilebilir: TR'de `/ingilizce-gramer/`, EN'de `/en/english-grammar/`.
Böylece her dil kendi anahtar kelimesini URL'de taşır. Çeviri yoksa Türkçe
slug'a düşer — kırılmaz.
"""
from django.urls import path
from django.utils.translation import gettext_lazy as _

from . import views

app_name = 'seo'

urlpatterns = [
    path(_('ingilizce-gramer/'), views.grammar_index, name='grammar_index'),
    path(_('ingilizce-gramer/<slug:slug>/'), views.grammar_detail, name='grammar_detail'),
    path(_('ingilizce-kelimeler/'), views.words_index, name='words_index'),
    path(_('ingilizce-kelimeler/<slug:level>/'), views.words_level, name='words_level'),
    path(_('ingilizce-mulakat-sorulari/'), views.interview_index, name='interview_index'),
    path(_('site-haritasi/'), views.html_sitemap, name='html_sitemap'),
]
