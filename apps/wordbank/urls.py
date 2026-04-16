from django.urls import path
from . import views

app_name = 'wordbank'

urlpatterns = [
    path('', views.levels, name='levels'),
    path('<str:level>/', views.quiz, name='quiz'),
    path('<str:level>/answer/', views.answer, name='answer'),
    path('<str:level>/reset/', views.reset, name='reset'),
]
