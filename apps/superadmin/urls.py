from django.urls import path

from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('<slug:slug>/', views.list_view, name='list'),
    path('<slug:slug>/new/', views.create_view, name='create'),
    path('<slug:slug>/<int:pk>/', views.detail_view, name='detail'),
    path('<slug:slug>/<int:pk>/edit/', views.update_view, name='edit'),
    path('<slug:slug>/<int:pk>/delete/', views.delete_view, name='delete'),
]
