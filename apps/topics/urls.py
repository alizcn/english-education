from django.urls import path
from . import views

app_name = 'topics'

urlpatterns = [
    path('', views.topic_list, name='list'),
    path('<slug:slug>/', views.topic_detail, name='detail'),
    path('<slug:slug>/toggle-done/', views.toggle_done, name='toggle_done'),
]
