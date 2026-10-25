from django.contrib import admin

from .models import BankProgress, BankWord, BankWordTranslation


class BankWordTranslationInline(admin.TabularInline):
    """Anlamlar ayrı tabloda; başlık kelimeyle birlikte düzenlenebilsin."""

    model = BankWordTranslation
    extra = 0
    fields = ('language', 'meaning', 'example_translation')


@admin.register(BankWord)
class BankWordAdmin(admin.ModelAdmin):
    list_display = ('language', 'level', 'rank', 'term', 'part_of_speech',
                    'translation_count')
    list_filter = ('language', 'level', 'part_of_speech')
    search_fields = ('term', 'translations__meaning')
    inlines = [BankWordTranslationInline]
    ordering = ('language', 'level', 'rank')

    def get_queryset(self, request):
        # list_display'deki sayaç her satır için sorgu açmasın.
        return super().get_queryset(request).prefetch_related('translations')

    @admin.display(description='Çeviri')
    def translation_count(self, obj):
        return obj.translations.count()


@admin.register(BankWordTranslation)
class BankWordTranslationAdmin(admin.ModelAdmin):
    list_display = ('word', 'language', 'meaning')
    list_filter = ('language', 'word__language', 'word__level')
    search_fields = ('meaning', 'word__term')
    list_select_related = ('word',)


@admin.register(BankProgress)
class BankProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'word', 'mastered', 'correct_count', 'wrong_count',
                    'last_answered_at')
    list_filter = ('mastered', 'word__language', 'word__level')
    list_select_related = ('user', 'word')
