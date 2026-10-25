from django.contrib import admin

from .models import Word


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('term', 'meaning', 'target_language', 'native_language',
                    'part_of_speech', 'source', 'mastered', 'times_asked',
                    'times_correct', 'created_at')
    list_filter = ('target_language', 'native_language', 'mastered',
                   'part_of_speech', 'source')
    search_fields = ('term', 'meaning')
    readonly_fields = ('created_at', 'times_asked', 'times_correct')
    ordering = ('-created_at',)
    list_select_related = ('user',)
