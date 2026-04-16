from django.conf import settings
from django.db import models


class ChatConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chats',
    )
    title = models.CharField(max_length=120, default='New chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    USER = 'user'
    ASSISTANT = 'assistant'
    ROLE_CHOICES = [(USER, 'User'), (ASSISTANT, 'Assistant')]

    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:40]}'
