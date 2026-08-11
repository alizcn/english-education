from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy
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
    path('profile/', views.profile, name='profile'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path(
        'password-reset/',
        PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/complete/',
        PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
        name='password_reset_complete',
    ),
]
