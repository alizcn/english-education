from django.contrib import admin

from .models import Word


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('english', 'turkish', 'part_of_speech', 'source',
                    'mastered', 'times_asked', 'times_correct', 'created_at')
    list_filter = ('mastered', 'part_of_speech', 'source')
    search_fields = ('english', 'turkish')
    readonly_fields = ('created_at', 'times_asked', 'times_correct')
    ordering = ('-created_at',)
