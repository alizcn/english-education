from django.contrib import admin

from .models import Topic, TopicCompletion, TopicExample, TopicExplanation


class TopicExplanationInline(admin.TabularInline):
    """Anlatımlar ayrı tabloda; konuyla birlikte düzenlenebilsin."""

    model = TopicExplanation
    extra = 0
    fields = ('language', 'body')


class TopicExampleInline(admin.TabularInline):
    model = TopicExample
    extra = 1
    # `translations` JSON: Django admin iki kademe nested inline desteklemediği
    # için çeviriler ayrı tablo olsaydı buradan hiç düzenlenemezdi.
    fields = ('kind', 'order', 'sentence', 'translations')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('language', 'name', 'slug', 'order', 'explanation_languages',
                    'example_count', 'updated_at')
    list_filter = ('language',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('language', 'order', 'name')
    inlines = [TopicExplanationInline, TopicExampleInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('explanations', 'examples')

    @admin.display(description='Anlatım dilleri')
    def explanation_languages(self, obj):
        codes = sorted(e.language for e in obj.explanations.all())
        return ', '.join(codes) or '—'

    @admin.display(description='Örnek')
    def example_count(self, obj):
        return obj.examples.count()


@admin.register(TopicExplanation)
class TopicExplanationAdmin(admin.ModelAdmin):
    list_display = ('topic', 'language', 'updated_at')
    list_filter = ('language', 'topic__language')
    search_fields = ('body', 'topic__name', 'topic__slug')
    list_select_related = ('topic',)


@admin.register(TopicExample)
class TopicExampleAdmin(admin.ModelAdmin):
    list_display = ('topic', 'kind', 'order', 'sentence')
    list_filter = ('kind', 'topic__language', 'topic')
    search_fields = ('sentence', 'topic__name')
    list_select_related = ('topic',)


@admin.register(TopicCompletion)
class TopicCompletionAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'completed_at')
    list_filter = ('topic__language', 'topic')
    search_fields = ('user__username', 'topic__name')
    readonly_fields = ('completed_at',)
    list_select_related = ('user', 'topic')
