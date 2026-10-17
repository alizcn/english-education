from django.contrib import admin

from .models import ChatConversation, ChatMessage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = False
    show_change_link = False
    max_num = 0


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'message_count', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ChatMessageInline]

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Mesaj'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'short_content', 'created_at')
    list_filter = ('role',)
    search_fields = ('content', 'conversation__user__username')
    readonly_fields = ('created_at',)

    def short_content(self, obj):
        return obj.content[:80]
    short_content.short_description = 'İçerik'
