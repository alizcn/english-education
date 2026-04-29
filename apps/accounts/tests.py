from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from apps.accounts.models import UserConsent


class KvkkModalTemplateTest(TestCase):
    """Verify the KVKK modal markup is correct on the signup page."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:signup')

    def test_signup_page_loads(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_kvkk_modal_hidden_by_default(self):
        """Modal must NOT have inline display:flex; it should use class-based visibility."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # The modal div should exist
        self.assertIn('id="kvkk-modal"', content)
        # Must NOT have inline display:flex on the modal (old bug)
        # The modal should use display:none by default via CSS, not hidden attribute with conflicting inline style
        self.assertIn('display: none', content.replace(' ', ''))
        # The modal should use .is-open class to show
        self.assertIn('is-open', content)

    def test_kvkk_modal_no_hidden_attribute(self):
        """Modal should not rely on the hidden attribute (which conflicts with inline display)."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        # The modal div should not have hidden attribute
        # We search for the modal opening tag specifically
        import re
        modal_tag = re.search(r'<div\s+id="kvkk-modal"[^>]*>', content)
        self.assertIsNotNone(modal_tag)
        self.assertNotIn('hidden', modal_tag.group())

    def test_accept_button_checks_checkbox(self):
        """The accept button script should set checkbox.checked = true."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn('checkbox.checked = true', content)

    def test_accept_button_text(self):
        """The accept button should say 'Okudum, anladım'."""
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn('Okudum, anladım', content)

    def test_kvkk_consent_checkbox_present(self):
        resp = self.client.get(self.url)
        content = resp.content.decode()
        self.assertIn('id="id_kvkk_consent"', content)
        self.assertIn('name="kvkk_consent"', content)


class SignupFormKvkkTest(TestCase):
    """Test that signup works correctly with KVKK consent."""

    def setUp(self):
        self.url = reverse('accounts:signup')

    def test_signup_without_kvkk_fails(self):
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            # kvkk_consent omitted
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form
        self.assertFalse(User.objects.filter(username='testuser').exists())

    def test_signup_with_kvkk_succeeds(self):
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'kvkk_consent': 'on',
        })
        self.assertEqual(resp.status_code, 302)  # redirect after success
        user = User.objects.get(username='testuser')
        self.assertEqual(user.email, 'test@example.com')
        # UserConsent record should be created
        self.assertTrue(UserConsent.objects.filter(user=user, kind=UserConsent.KVKK).exists())

    def test_signup_creates_consent_record(self):
        self.client.post(self.url, {
            'username': 'consentuser',
            'email': 'consent@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'kvkk_consent': 'on',
        })
        user = User.objects.get(username='consentuser')
        consent = UserConsent.objects.get(user=user)
        self.assertEqual(consent.kind, UserConsent.KVKK)
        self.assertIsNotNone(consent.accepted_at)
