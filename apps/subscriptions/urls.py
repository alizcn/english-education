from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('', views.plans, name='plans'),
    path('paketler/', views.plans, name='plans_alt'),
    path('paketlerim/', views.my_subscriptions, name='my'),
    path('iptal/<int:pk>/', views.cancel_subscription, name='cancel'),
    path('devam/<int:pk>/', views.resume_subscription, name='resume'),
    path('odeme/<slug:slug>/', views.checkout, name='checkout'),
    path('callback/', csrf_exempt(views.callback), name='callback'),
    path('basarili/<int:payment_id>/', views.success, name='success'),
    path('basarisiz/<int:payment_id>/', views.failed, name='failed'),
]
