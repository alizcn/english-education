from django.contrib import admin

from .models import Topic, TopicExample, TopicCompletion


class TopicExampleInline(admin.TabularInline):
    model = TopicExample
    extra = 1
    fields = ('kind', 'sentence_en', 'sentence_tr')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'example_count', 'updated_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('order', 'name')
    inlines = [TopicExampleInline]

    def example_count(self, obj):
        return obj.examples.count()
    example_count.short_description = 'Örnek'


@admin.register(TopicExample)
class TopicExampleAdmin(admin.ModelAdmin):
    list_display = ('topic', 'kind', 'sentence_en', 'sentence_tr')
    list_filter = ('kind', 'topic')
    search_fields = ('sentence_en', 'sentence_tr', 'topic__name')


@admin.register(TopicCompletion)
class TopicCompletionAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'completed_at')
    list_filter = ('topic',)
    search_fields = ('user__username', 'topic__name')
    readonly_fields = ('completed_at',)
