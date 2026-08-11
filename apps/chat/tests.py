from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from . import views
from .models import ChatConversation, ChatMessage


class ChatDeleteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='sifre123')
        self.client.force_login(self.user)
        self.conv = ChatConversation.objects.create(user=self.user, title='Sohbet')
        ChatMessage.objects.create(conversation=self.conv, role=ChatMessage.USER, content='selam')
        ChatMessage.objects.create(conversation=self.conv, role=ChatMessage.ASSISTANT, content='hello')

    def test_delete_removes_conversation_and_messages(self):
        resp = self.client.post(f'/chat/{self.conv.pk}/delete/')
        self.assertRedirects(resp, '/chat/')
        self.assertFalse(ChatConversation.objects.filter(pk=self.conv.pk).exists())
        # CASCADE: mesajlar da gitmeli, yoksa yetim satır kalır.
        self.assertFalse(ChatMessage.objects.filter(conversation_id=self.conv.pk).exists())

    def test_delete_clears_active_session_pointer(self):
        session = self.client.session
        session['chat_conv_id'] = self.conv.pk
        session.save()
        self.client.post(f'/chat/{self.conv.pk}/delete/')
        self.assertNotIn('chat_conv_id', self.client.session)

    def test_cannot_delete_other_users_conversation(self):
        other = get_user_model().objects.create_user(username='veli', password='x')
        foreign = ChatConversation.objects.create(user=other)
        resp = self.client.post(f'/chat/{foreign.pk}/delete/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ChatConversation.objects.filter(pk=foreign.pk).exists())

    def test_delete_requires_post(self):
        resp = self.client.get(f'/chat/{self.conv.pk}/delete/')
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(ChatConversation.objects.filter(pk=self.conv.pk).exists())


class ChatSendTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='sifre123')
        self.client.force_login(self.user)

    def test_reply_is_saved(self):
        with mock.patch.object(views.claude, 'chat', return_value='Hello!'):
            resp = self.client.post('/chat/send/', {'message': 'selam'})
        self.assertRedirects(resp, '/chat/')
        conv = ChatConversation.objects.get(user=self.user)
        self.assertEqual(
            list(conv.messages.values_list('role', 'content')),
            [(ChatMessage.USER, 'selam'), (ChatMessage.ASSISTANT, 'Hello!')],
        )

    def test_client_error_shows_message(self):
        from services.claude_client import ClaudeClientError
        with mock.patch.object(views.claude, 'chat', side_effect=ClaudeClientError('AI yoğun.')):
            resp = self.client.post('/chat/send/', {'message': 'selam'})
        self.assertRedirects(resp, '/chat/')
        conv = ChatConversation.objects.get(user=self.user)
        # Kullanıcı mesajı kalmalı, asistan yanıtı olmamalı.
        self.assertEqual(conv.messages.count(), 1)

    def test_empty_reply_is_not_saved(self):
        with mock.patch.object(views.claude, 'chat', return_value='   '):
            self.client.post('/chat/send/', {'message': 'selam'})
        self.assertFalse(ChatMessage.objects.filter(role=ChatMessage.ASSISTANT).exists())


class ChatSendRaceTests(TransactionTestCase):
    """Yanıt üretilirken sohbetin silinmesi.

    TestCase değil TransactionTestCase: Django SQLite'ta FK'ları
    DEFERRABLE INITIALLY DEFERRED kuruyor, yani ihlal ancak COMMIT anında
    ortaya çıkıyor. TestCase her testi geri sardığı için commit hiç olmuyor
    ve hata üretilemiyordu — üretimde ise istek 500'e düşüyordu.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='sifre123')
        self.client.force_login(self.user)

    def test_conversation_deleted_mid_generation_does_not_500(self):
        def _delete_then_reply(_messages):
            ChatConversation.objects.filter(user=self.user).delete()
            return 'Hello!'

        with mock.patch.object(views.claude, 'chat', side_effect=_delete_then_reply):
            # assertLogs: IntegrityError yakalama dalının gerçekten çalıştığını
            # doğrular. Olmazsa test "hata hiç oluşmadı" diye boşuna geçerdi.
            with self.assertLogs('apps.chat.views', level='INFO') as logs:
                resp = self.client.post('/chat/send/', {'message': 'selam'})

        self.assertTrue(any('silinmiş' in line for line in logs.output), logs.output)
        self.assertRedirects(resp, '/chat/')
        self.assertFalse(ChatMessage.objects.filter(role=ChatMessage.ASSISTANT).exists())
