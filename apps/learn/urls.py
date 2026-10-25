"""Kurs seçici yolları. Prefix makinesi `apps/learn/prefix.py`de."""

from django.urls import path

from . import views

app_name = 'learn'

urlpatterns = [
    path('', views.course_list, name='courses'),
    path('switch/', views.switch_course, name='switch'),
    path('add/', views.add_course, name='add'),
    path('native/', views.set_native_language, name='set_native'),
]
