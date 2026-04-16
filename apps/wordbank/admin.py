from django.contrib import admin
from .models import BankWord, BankProgress


@admin.register(BankWord)
class BankWordAdmin(admin.ModelAdmin):
    list_display = ('level', 'rank', 'english', 'part_of_speech', 'turkish')
    list_filter = ('level', 'part_of_speech')
    search_fields = ('english', 'turkish')


@admin.register(BankProgress)
class BankProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'word', 'mastered', 'correct_count', 'wrong_count', 'last_answered_at')
    list_filter = ('mastered', 'word__level')
