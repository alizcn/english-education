from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('', include('apps.dashboard.urls')),
    path('words/', include('apps.vocabulary.urls')),
    path('topics/', include('apps.topics.urls')),
    path('quiz/', include('apps.quizzes.urls')),
    path('chat/', include('apps.chat.urls')),
    path('wordbank/', include('apps.wordbank.urls')),
]
