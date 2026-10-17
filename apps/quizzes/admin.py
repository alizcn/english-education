from django.contrib import admin

from .models import QuizTemplate, QuizSession, QuizQuestion


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0
    readonly_fields = ('order', 'question_type', 'prompt', 'correct_answer',
                       'user_answer', 'is_correct', 'answered_at')
    can_delete = False
    max_num = 0


@admin.register(QuizTemplate)
class QuizTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'user', 'status', 'question_count', 'created_at')
    list_filter = ('kind', 'status')
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at', 'questions_data')
    ordering = ('-created_at',)

    def question_count(self, obj):
        return obj.question_count
    question_count.short_description = 'Soru'


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'kind', 'correct_count', 'wrong_count',
                    'total_questions', 'is_finished', 'started_at')
    list_filter = ('kind', 'started_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('started_at', 'finished_at')
    inlines = [QuizQuestionInline]

    def is_finished(self, obj):
        return obj.is_finished
    is_finished.boolean = True
    is_finished.short_description = 'Bitti?'
