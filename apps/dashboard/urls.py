from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('install-app/', views.install_guide, name='install_guide'),
]
