from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse


class AccountPasswordResetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ali',
            email='ali@example.com',
            password='sifre123',
        )

    def test_login_has_forgot_password_link(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Şifremi unuttum')

    def test_password_reset_sends_email(self):
        resp = self.client.post(reverse('accounts:password_reset'), {'email': 'ali@example.com'})
        self.assertRedirects(resp, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ali@example.com', mail.outbox[0].to)
        self.assertIn('reset', mail.outbox[0].body.lower())
