from django.conf import settings
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('levelenai-admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('apps.dashboard.urls')),
    path('words/', include('apps.vocabulary.urls')),
    path('topics/', include('apps.topics.urls')),
    path('quiz/', include('apps.quizzes.urls')),
    path('chat/', include('apps.chat.urls')),
    path('wordbank/', include('apps.wordbank.urls')),
    path('interviews/', include('apps.interviews.urls')),
    path('abonelik/', include('apps.subscriptions.urls')),
    path('super/', include('apps.superadmin.urls')),
]
