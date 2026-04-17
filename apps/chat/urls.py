from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_page, name='page'),
    path('send/', views.send, name='send'),
    path('new/', views.new_conversation, name='new'),
    path('<int:pk>/', views.open_conversation, name='open'),
    path('<int:pk>/rename/', views.rename_conversation, name='rename'),
    path('<int:pk>/delete/', views.delete_conversation, name='delete'),
]
