from django.urls import path
from . import views

app_name = 'interviews'

urlpatterns = [
    path('', views.interview_list, name='list'),
    path('create/', views.interview_create, name='create'),
    path('create-cv/', views.interview_create_cv, name='create_cv'),
    path('<int:pk>/', views.interview_detail, name='detail'),
    path('<int:pk>/delete/', views.interview_delete, name='delete'),
]
