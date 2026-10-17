from django.contrib import admin

from .models import InterviewSession


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'user', 'source', 'status', 'question_count', 'created_at')
    list_filter = ('source', 'status', 'job_category')
    search_fields = ('user__username', 'user__email', 'custom_title', 'cv_filename')
    readonly_fields = ('created_at', 'questions_data')
    ordering = ('-created_at',)

    def question_count(self, obj):
        return obj.question_count
    question_count.short_description = 'Soru'
