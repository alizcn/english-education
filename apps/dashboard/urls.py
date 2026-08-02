from django.urls import path
from django.utils.translation import gettext_lazy as _

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path(_('uygulamayi-yukle/'), views.install_guide, name='install_guide'),
]
