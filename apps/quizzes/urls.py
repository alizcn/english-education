from django.urls import path
from . import views

app_name = 'quizzes'

urlpatterns = [
    path('words/', views.word_picker, name='word_picker'),
    path('words/generate/', views.generate_word_quiz, name='generate_word'),
    path('topics/<slug:slug>/', views.topic_picker, name='topic_picker'),
    path('topics/<slug:slug>/generate/', views.generate_topic_quiz_view, name='generate_topic'),
    path('start/<int:template_id>/', views.start_template, name='start_template'),
    path('<int:pk>/', views.run_quiz, name='run'),
    path('<int:pk>/answer/', views.submit_answer, name='answer'),
    path('<int:pk>/result/', views.result, name='result'),
]
