from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_page, name='page'),
    path('send/', views.send, name='send'),
    path('new/', views.new_conversation, name='new'),
]
