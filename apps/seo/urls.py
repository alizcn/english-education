"""Halka açık SEO sayfaları.

Yollar her dilde İngilizce'dir: `/english-grammar/`, `/en/english-grammar/`.
Tek bir slug seti tutmak hem paylaşılan bağlantıları hem de analitik
raporlarını sadeleştirir. Eski Türkçe slug'lar `legacy_redirects` içinden
kalıcı olarak (301) yeni adreslere taşınır — indekslenmiş bağlantılar ölmez.
"""
from django.urls import path

from . import views

app_name = 'seo'

urlpatterns = [
    path('english-grammar/', views.grammar_index, name='grammar_index'),
    path('english-grammar/<slug:slug>/', views.grammar_detail, name='grammar_detail'),
    path('english-vocabulary/', views.words_index, name='words_index'),
    path('english-vocabulary/<slug:level>/', views.words_level, name='words_level'),
    path('english-interview-questions/', views.interview_index, name='interview_index'),
    path('sitemap/', views.html_sitemap, name='html_sitemap'),
]
