from django.urls import path
from . import views

app_name = 'vocabulary'

urlpatterns = [
    path('', views.word_list, name='list'),
    path('add/', views.bulk_add, name='bulk_add'),
    path('<int:pk>/edit/', views.word_edit, name='edit'),
    path('<int:pk>/delete/', views.word_delete, name='delete'),
]
