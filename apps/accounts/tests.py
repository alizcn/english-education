from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils import translation

from apps.quizzes.models import QuizSession

from services import languages

from . import services
from .models import UserCourse


class AccountPasswordResetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ali',
            email='ali@example.com',
            password='sifre123',
        )

    def test_login_has_forgot_password_link(self):
        """Çevrilen metne değil ADRESE bakıyoruz.

        Kural: çevrilebilir proza asla assert edilmez — arayüz dili değişince
        ya da katalog güncellenince test kırılır ve kırılma gerçek bir
        regresyonu göstermez.
        """
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('accounts:password_reset'))

    def test_password_reset_sends_email(self):
        resp = self.client.post(reverse('accounts:password_reset'), {'email': 'ali@example.com'})
        self.assertRedirects(resp, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ali@example.com', mail.outbox[0].to)
        self.assertIn('reset', mail.outbox[0].body.lower())


class UserCourseTests(TestCase):
    """Kullanıcı başına çok kurs — `UserLevel`in OneToOne kısıtının yerine."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('veli', password='x')

    def test_no_course_is_created_automatically_on_signup_signal(self):
        """Kurs sinyalle AÇILMIYOR: sinyalin `request`e erişimi yok, yani ana
        dili tahmin edemiyor. İngilizce konuşan kullanıcıya native='tr' kurs
        açmak sessiz bir veri hatası olurdu."""
        fresh = get_user_model().objects.create_user('yeni', password='x')
        self.assertEqual(UserCourse.objects.filter(user=fresh).count(), 0)

    def test_ensure_active_course_creates_the_default_pair(self):
        course = services.ensure_active_course(self.user)
        self.assertEqual(course.target_language, 'en')
        self.assertTrue(course.is_active)

    def test_ensure_active_course_is_idempotent(self):
        first = services.ensure_active_course(self.user)
        second = services.ensure_active_course(self.user)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(UserCourse.objects.filter(user=self.user).count(), 1)

    def test_user_can_hold_two_courses(self):
        services.ensure_active_course(self.user, target='en', native='tr')
        UserCourse.objects.create(
            user=self.user, target_language='de', native_language='tr',
        )
        self.assertEqual(UserCourse.objects.filter(user=self.user).count(), 2)

    def test_only_one_course_can_be_active(self):
        a = services.ensure_active_course(self.user, target='en', native='tr')
        b = UserCourse.objects.create(
            user=self.user, target_language='de', native_language='tr',
        )
        services.activate(b)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.is_active)
        self.assertTrue(b.is_active)
        self.assertEqual(
            UserCourse.objects.filter(user=self.user, is_active=True).count(), 1,
        )

    def test_partial_unique_constraint_blocks_two_active_courses(self):
        services.ensure_active_course(self.user, target='en', native='tr')
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserCourse.objects.create(
                user=self.user, target_language='de', native_language='tr',
                is_active=True,
            )

    def test_same_target_cannot_repeat_for_one_user(self):
        services.ensure_active_course(self.user, target='en', native='tr')
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserCourse.objects.create(
                user=self.user, target_language='en', native_language='fr',
            )

    def test_native_equal_to_target_is_rejected(self):
        course = UserCourse(
            user=self.user, target_language='en', native_language='en',
        )
        with self.assertRaises(ValidationError):
            course.full_clean()

    def test_unreleased_target_language_is_rejected(self):
        """Alan `choices`ı tam dil listesi (migration churn'ünü önlemek için);
        "şu an öğrenilebilir mi" kontrolü `clean()`de.

        Sicildeki dört dilin hepsi bugün öğrenilebilir, o yüzden kapı
        sicil kısıtlanarak sınanıyor — yayın durumu değil mekanizma.
        """
        course = UserCourse(
            user=self.user, target_language='de', native_language='tr',
        )
        with mock.patch.object(languages, 'LEARNABLE_CODES', ('en',)):
            with self.assertRaises(ValidationError):
                course.full_clean()
        course.full_clean()      # kapı kapanmadığında geçerli

    def test_auth_page_tagline_is_language_neutral(self):
        """Giriş/kayıt sayfasının sloganı tek satır ve dil-NÖTR.

        İki ölçülmüş hata burada kilitleniyor:

        * Slogan bir ara `{% lang_name 'en' %}` ile parametreleştirilmişti ve
          Türkçe arayüzde "Level up your İngilizce." üretiyordu — İngilizce
          cümlenin içine Türkçe kelime.
        * İngilizce arayüzde slogan ile altındaki yerelleşmiş satır birebir
          aynı çıkıyordu.

        Giriş yapılmadığı için kurs yok; slogan artık platformun dört dilli
        olduğunu söylüyor ve tek satır.
        """
        import re
        from html import unescape

        for prefix in ('', '/en', '/fr', '/de'):
            with self.subTest(prefix=prefix or '/'):
                html = self.client.get(f'{prefix}/accounts/login/').content.decode()
                self.assertNotIn('Level up your İngilizce', html)
                self.assertNotIn('Level up your anglais', html)
                taglines = [
                    unescape(t.strip()) for t in re.findall(
                        r'margin-top:0\.3rem;">(.*?)</div>', html, re.S,
                    )
                ]
                self.assertEqual(len(taglines), 1, f'tek slogan bekleniyor: {taglines}')
                self.assertEqual(len(taglines), len(set(taglines)))
                # Tek bir dile kilitli olmamalı.
                self.assertNotRegex(taglines[0], r'^Level up your English')

    def test_default_native_avoids_clashing_with_the_target(self):
        """İngilizce arayüz + İngilizce kurs çakışıyor; varsayılana düşmeli."""
        with translation.override('en'):
            self.assertNotEqual(services.default_native_for('en'), 'en')

    def test_default_native_follows_the_interface_language(self):
        with translation.override('en'):
            # Hedef İngilizce değilse arayüz dili ana dil olabilir.
            self.assertEqual(services.default_native_for('de'), 'en')

    def test_advance_moves_the_level(self):
        course = services.ensure_active_course(self.user)
        course.advance(160)
        self.assertEqual(course.score, 160)
        self.assertEqual(course.current_level, 'B1')

    def test_advance_never_goes_below_zero(self):
        course = services.ensure_active_course(self.user)
        course.advance(-50)
        self.assertEqual(course.score, 0)
        self.assertEqual(course.current_level, 'A1')


class QuizScoreRoutingTests(TestCase):
    """Puan, oturumun AİT OLDUĞU kursa yazılmalı.

    Kullanıcının birden çok kursu olduğu için `filter(user=...)` tek başına
    yetmiyor: Almanca quizinin puanı İngilizce seviyesini yükseltemez.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user('ayse', password='x')
        self.en = UserCourse.objects.create(
            user=self.user, target_language='en', native_language='tr',
            is_active=True,
        )
        self.de = UserCourse.objects.create(
            user=self.user, target_language='de', native_language='tr',
        )

    def _finish_quiz(self, target, correct=10, wrong=0):
        session = QuizSession.objects.create(
            user=self.user, kind='word', target_language=target,
            native_language='tr', total_questions=correct + wrong,
        )
        session.correct_count, session.wrong_count = correct, wrong
        session.finished_at = timezone.now()
        session.save()
        return session

    def test_score_lands_on_the_matching_course(self):
        self._finish_quiz('de', correct=10)
        self.en.refresh_from_db()
        self.de.refresh_from_db()
        self.assertEqual(self.en.score, 0)
        self.assertEqual(self.de.score, 10)

    def test_wrong_answers_halve_into_the_penalty(self):
        self._finish_quiz('en', correct=10, wrong=4)
        self.en.refresh_from_db()
        self.assertEqual(self.en.score, 8)

    def test_unfinished_session_awards_nothing(self):
        QuizSession.objects.create(
            user=self.user, kind='word', target_language='en',
            native_language='tr', total_questions=10, correct_count=10,
        )
        self.en.refresh_from_db()
        self.assertEqual(self.en.score, 0)

    def test_missing_course_does_not_raise(self):
        """Kursu olmayan bir dilde quiz bitirmek 500 vermemeli."""
        self.de.delete()
        self._finish_quiz('de', correct=5)   # istisna fırlatmamalı
