from django.urls import path
from . import views

app_name = 'vocabulary'

urlpatterns = [
    path('', views.word_list, name='list'),
    path('add/', views.bulk_add, name='bulk_add'),
    path('quiz/', views.word_quiz, name='quiz'),
    path('quiz/answer/', views.word_quiz_answer, name='quiz_answer'),
    path('quiz/reset/', views.word_quiz_reset, name='quiz_reset'),
    path('<int:pk>/edit/', views.word_edit, name='edit'),
    path('<int:pk>/delete/', views.word_delete, name='delete'),
]
