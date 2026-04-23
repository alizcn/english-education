from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django_ratelimit.decorators import ratelimit

from . import views

app_name = 'accounts'

_rate_limited_login = ratelimit(
    key='ip', rate='20/h', method='POST', block=False,
)(LoginView.as_view(template_name='accounts/login.html'))

urlpatterns = [
    path('login/', _rate_limited_login, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profil/', views.profile, name='profile'),
    path('hesap-sil/', views.delete_account, name='delete_account'),
]
