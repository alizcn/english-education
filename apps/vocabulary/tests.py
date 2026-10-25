"""Kişisel kelime listesi: model kısıtları ve quiz seçimi.

Çok dilli dönüşümün emniyet ağı. `Word` bugün `(user, english)` ile tekil;
dönüşümde `(user, target_language, term)` olacak. Buradaki testler bugünkü
davranışı kilitliyor, böylece alan yeniden adlandırma ve dil ekseni eklenirken
gözden kaçan bir regresyon görünür hâle geliyor.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from . import services
from .models import Word


EN, TR = 'en', 'tr'


def make_word(user, term='book', meaning='kitap', target=EN, native=TR, **kw):
    return Word.objects.create(
        user=user, term=term, meaning=meaning,
        target_language=target, native_language=native, **kw,
    )


class WordModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')

    def test_same_word_cannot_repeat_for_one_user(self):
        make_word(self.user, 'book')
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_word(self.user, 'book', meaning='başka')

    def test_two_users_can_hold_the_same_word(self):
        other = User.objects.create_user('veli', password='x')
        make_word(self.user, 'book')
        make_word(other, 'book')
        self.assertEqual(Word.objects.filter(term='book').count(), 2)

    def test_same_term_can_exist_in_two_courses(self):
        """Benzersizlik `(user, target_language, term)`: "die" hem İngilizce
        hem Almanca listede bulunabilir."""
        make_word(self.user, 'die', 'ölmek', target='en')
        make_word(self.user, 'die', 'belirli tanımlık', target='de')
        self.assertEqual(Word.objects.filter(user=self.user, term='die').count(), 2)

    def test_personal_stats_are_scoped_to_the_course(self):
        make_word(self.user, 'book', target='en')
        make_word(self.user, 'Buch', target='de')
        self.assertEqual(services.personal_stats(self.user, 'en')['total'], 1)
        self.assertEqual(services.personal_stats(self.user, 'de')['total'], 1)

    def test_accuracy_is_none_before_any_question(self):
        self.assertIsNone(make_word(self.user).accuracy)

    def test_accuracy_rounds_to_percent(self):
        word = make_word(self.user, times_asked=3, times_correct=1)
        self.assertEqual(word.accuracy, 33)

    def test_newest_word_comes_first(self):
        make_word(self.user, 'first')
        make_word(self.user, 'second')
        self.assertEqual(
            [w.term for w in Word.objects.filter(user=self.user)],
            ['second', 'first'],
        )


class PersonalStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')

    def test_empty_list_reports_zeroes(self):
        stats = services.personal_stats(self.user, EN)
        self.assertEqual(stats, {
            'total': 0, 'mastered': 0, 'retry': 0, 'unseen': 0, 'percent': 0,
        })

    def test_counts_split_across_mastered_retry_and_unseen(self):
        make_word(self.user, 'a', mastered=True)
        make_word(self.user, 'b', times_asked=2)
        make_word(self.user, 'c')
        stats = services.personal_stats(self.user, EN)
        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['mastered'], 1)
        self.assertEqual(stats['retry'], 1)
        self.assertEqual(stats['unseen'], 1)
        self.assertEqual(stats['percent'], 33)

    def test_other_users_words_are_not_counted(self):
        other = User.objects.create_user('veli', password='x')
        make_word(other, 'a')
        self.assertEqual(services.personal_stats(self.user, EN)['total'], 0)


class PickNextTests(TestCase):
    """`pick_next` görülmemiş kelime varken DE %25 olasılıkla tekrar döndürüyor.

    Bu kasıtlı bir davranış (yanlış cevaplanan kelime arada bir geri gelsin),
    ama test edilebilmesi için rastgeleliği sabitlemek gerekiyor — yoksa
    testler dört koşuda bir kırılır.
    """

    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')

    def _no_retry_roll(self):
        """Rastgele atışı 0.25 eşiğinin ÜSTÜNE sabitler: tekrar seçilmez."""
        return mock.patch('apps.vocabulary.services.random.random', return_value=0.99)

    def _force_retry_roll(self):
        """Atışı eşiğin ALTINA sabitler: tekrar seçilir."""
        return mock.patch('apps.vocabulary.services.random.random', return_value=0.0)

    def test_unseen_word_comes_first(self):
        make_word(self.user, 'seen', times_asked=1)
        unseen = make_word(self.user, 'unseen')
        with self._no_retry_roll():
            picked, is_retry = services.pick_next(self.user, EN)
        self.assertEqual(picked.pk, unseen.pk)
        self.assertFalse(is_retry)

    def test_retry_can_jump_the_queue(self):
        seen = make_word(self.user, 'seen', times_asked=1)
        make_word(self.user, 'unseen')
        with self._force_retry_roll():
            picked, is_retry = services.pick_next(self.user, EN)
        self.assertEqual(picked.pk, seen.pk)
        self.assertTrue(is_retry)

    def test_pick_next_is_scoped_to_the_course(self):
        make_word(self.user, 'Buch', target='de')
        picked, _ = services.pick_next(self.user, EN)
        self.assertIsNone(picked)

    def test_only_retries_left_returns_retry_flag(self):
        word = make_word(self.user, 'seen', times_asked=1)
        picked, is_retry = services.pick_next(self.user, EN)
        self.assertEqual(picked.pk, word.pk)
        self.assertTrue(is_retry)

    def test_all_mastered_returns_none(self):
        make_word(self.user, 'a', mastered=True)
        self.assertEqual(services.pick_next(self.user, EN), (None, False))


class BuildQuestionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')

    def test_answer_present_and_capped_at_four(self):
        word = make_word(self.user, 'book', 'kitap')
        for i in range(6):
            make_word(self.user, f'w{i}', f'anlam{i}')
        options = services.build_question(word, self.user)
        self.assertIn('kitap', options)
        self.assertEqual(len(options), 4)

    def test_distractors_stay_within_the_user(self):
        other = User.objects.create_user('veli', password='x')
        make_word(other, 'other', 'baskasinin')
        word = make_word(self.user, 'book', 'kitap')
        make_word(self.user, 'pen', 'kalem')
        options = services.build_question(word, self.user)
        self.assertNotIn('baskasinin', options)

    def test_answer_is_never_duplicated(self):
        word = make_word(self.user, 'book', 'kitap')
        make_word(self.user, 'tome', 'kitap')
        make_word(self.user, 'pen', 'kalem')
        options = services.build_question(word, self.user)
        self.assertEqual(options.count('kitap'), 1)


class RecordAnswerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')
        self.word = make_word(self.user, 'book', 'kitap')

    def test_correct_answer_masters_and_counts(self):
        services.record_answer(self.word, True)
        self.word.refresh_from_db()
        self.assertTrue(self.word.mastered)
        self.assertEqual(self.word.times_asked, 1)
        self.assertEqual(self.word.times_correct, 1)

    def test_wrong_answer_counts_without_mastering(self):
        services.record_answer(self.word, False)
        self.word.refresh_from_db()
        self.assertFalse(self.word.mastered)
        self.assertEqual(self.word.times_asked, 1)
        self.assertEqual(self.word.times_correct, 0)
