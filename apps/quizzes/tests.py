from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.topics.models import Topic
from apps.vocabulary.models import Word
from services.claude_client import ClaudeClientError

from . import tasks
from .models import QuizTemplate


def item(prompt='Translate: cat'):
    return {
        'question_type': 'translate_en_tr',
        'prompt': prompt,
        'correct_answer': 'kedi',
        'choices': None,
    }


class GenerateViewTests(TestCase):
    """Üretim istek yolunda ÇALIŞMAMALI — eskiden ~100s gunicorn worker'ı bloke ediyordu."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='sifre123')
        self.client.force_login(self.user)
        self.topic = Topic.objects.create(name='Present Simple', slug='present-simple')

    def test_topic_generate_queues_and_returns_immediately(self):
        with mock.patch.object(tasks.generate_topic_template, 'delay') as delay, \
             mock.patch('services.claude_client.generate_topic_quiz') as ai:
            resp = self.client.post(reverse('quizzes:generate_topic', args=[self.topic.slug]))

        ai.assert_not_called()  # istek içinde AI çağrısı olmamalı
        tmpl = QuizTemplate.objects.get(user=self.user, kind=QuizTemplate.TOPIC)
        self.assertEqual(tmpl.status, QuizTemplate.PENDING)
        self.assertEqual(tmpl.questions_data, [])
        delay.assert_called_once_with(tmpl.pk, self.topic.pk)
        self.assertRedirects(resp, reverse('quizzes:topic_picker', args=[self.topic.slug]))

    def test_second_request_does_not_queue_a_duplicate(self):
        QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.TOPIC, topic=self.topic,
            name='Quiz #1', status=QuizTemplate.PENDING,
        )
        with mock.patch.object(tasks.generate_topic_template, 'delay') as delay:
            self.client.post(reverse('quizzes:generate_topic', args=[self.topic.slug]))
        delay.assert_not_called()
        self.assertEqual(QuizTemplate.objects.filter(user=self.user).count(), 1)

    def test_word_generate_queues(self):
        for i in range(12):
            Word.objects.create(user=self.user, english=f'w{i}', turkish=f'k{i}')
        with mock.patch.object(tasks.generate_word_template, 'delay') as delay, \
             mock.patch('services.claude_client.generate_word_quiz_extras') as ai:
            resp = self.client.post(reverse('quizzes:generate_word'))
        ai.assert_not_called()
        tmpl = QuizTemplate.objects.get(user=self.user, kind=QuizTemplate.WORD)
        self.assertEqual(tmpl.status, QuizTemplate.PENDING)
        delay.assert_called_once_with(tmpl.pk, self.user.pk)
        self.assertRedirects(resp, reverse('quizzes:word_picker'))

    def test_cannot_start_a_template_that_is_not_ready(self):
        tmpl = QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.TOPIC, topic=self.topic,
            name='Quiz #1', status=QuizTemplate.PENDING, questions_data=[item()],
        )
        resp = self.client.post(reverse('quizzes:start_template', args=[tmpl.pk]))
        self.assertRedirects(resp, reverse('quizzes:topic_picker', args=[self.topic.slug]))
        self.assertFalse(tmpl.sessions.exists())

    def test_status_endpoint_reports_progress(self):
        tmpl = QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.WORD, name='Quiz #1',
            status=QuizTemplate.PENDING, questions_data=[item('a'), item('b')],
        )
        resp = self.client.get(reverse('quizzes:template_status', args=[tmpl.pk]))
        self.assertEqual(
            resp.json(),
            {'status': 'pending', 'ready_count': 2, 'total': tasks.QUESTION_TARGET},
        )

    def test_picker_renders_pending_ready_and_failed_side_by_side(self):
        QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.TOPIC, topic=self.topic, name='Hazirlanan',
            status=QuizTemplate.PENDING,
        )
        QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.TOPIC, topic=self.topic, name='Hazir olan',
            status=QuizTemplate.READY, questions_data=[item()],
        )
        QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.TOPIC, topic=self.topic, name='Dusen',
            status=QuizTemplate.FAILED, error_message='AI yanit vermedi.',
        )
        resp = self.client.get(reverse('quizzes:topic_picker', args=[self.topic.slug]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('data-pending-template', body)   # bekleyen yoklanıyor
        self.assertIn('AI yanit vermedi.', body)       # hata kullanıcıya görünüyor
        # "Başla" yalnızca hazır şablon için çıkmalı.
        self.assertIn(reverse('quizzes:start_template', args=[
            QuizTemplate.objects.get(name='Hazir olan').pk]), body)
        self.assertNotIn(reverse('quizzes:start_template', args=[
            QuizTemplate.objects.get(name='Hazirlanan').pk]), body)

    def test_status_endpoint_hides_other_users_templates(self):
        other = get_user_model().objects.create_user(username='veli', password='x')
        tmpl = QuizTemplate.objects.create(user=other, kind=QuizTemplate.WORD, name='Quiz #1')
        resp = self.client.get(reverse('quizzes:template_status', args=[tmpl.pk]))
        self.assertEqual(resp.status_code, 404)


class GenerateTaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='x')
        self.topic = Topic.objects.create(name='Present Simple', slug='present-simple')
        self.tmpl = QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.TOPIC, topic=self.topic,
            name='Quiz #1', status=QuizTemplate.PENDING,
        )

    def _refresh(self):
        self.tmpl.refresh_from_db()
        return self.tmpl

    def test_chunks_are_collected_and_marked_ready(self):
        def _chunk(_name, _expl, _ex, n, focus):
            return [item(f'{focus} {i}') for i in range(n)]

        with mock.patch('services.claude_client.generate_topic_quiz', side_effect=_chunk):
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)
        t = self._refresh()
        self.assertEqual(t.status, QuizTemplate.READY)
        self.assertEqual(len(t.questions_data), tasks.QUESTION_TARGET)

    def test_each_chunk_gets_a_distinct_focus(self):
        with mock.patch(
            'services.claude_client.generate_topic_quiz', return_value=[item()],
        ) as ai:
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)
        focuses = [c.kwargs['focus'] for c in ai.call_args_list]
        self.assertEqual(len(focuses), len(tasks._chunk_plan(tasks.QUESTION_TARGET, tasks.TOPIC_FOCUS)))
        self.assertEqual(len(set(focuses)), len(focuses), focuses)
        # Aynı soru her parçadan döndü — tekilleştirme bire indirmeli.
        self.assertEqual(len(self._refresh().questions_data), 1)

    def test_partial_results_are_saved_while_still_pending(self):
        saves = []
        original_save = QuizTemplate.save

        def _spy(instance, *args, **kwargs):
            saves.append((instance.status, len(instance.questions_data or [])))
            return original_save(instance, *args, **kwargs)

        def _chunk(_name, _expl, _ex, n, focus):
            return [item(f'{focus} {i}') for i in range(n)]

        with mock.patch.object(QuizTemplate, 'save', _spy), \
             mock.patch('services.claude_client.generate_topic_quiz', side_effect=_chunk):
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)

        partial = [
            count for status, count in saves
            if status == QuizTemplate.PENDING and 0 < count < tasks.QUESTION_TARGET
        ]
        self.assertTrue(partial, saves)
        self.assertEqual(partial, sorted(partial))

    def test_one_failing_chunk_still_delivers_the_rest(self):
        calls = []

        def _chunk(_name, _expl, _ex, n, focus):
            calls.append(focus)
            if len(calls) == 1:
                raise ClaudeClientError('bu parça patladı')
            return [item(f'{focus} {i}') for i in range(n)]

        with mock.patch('services.claude_client.generate_topic_quiz', side_effect=_chunk):
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)
        t = self._refresh()
        self.assertEqual(t.status, QuizTemplate.READY)
        self.assertTrue(t.questions_data)
        self.assertLess(len(t.questions_data), tasks.QUESTION_TARGET)

    def test_total_failure_is_shown_to_user(self):
        err = ClaudeClientError('AI şu an çok yoğun.')
        with mock.patch('services.claude_client.generate_topic_quiz', side_effect=err):
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)
        t = self._refresh()
        self.assertEqual(t.status, QuizTemplate.FAILED)
        self.assertIn('yoğun', t.error_message)

    def test_unexpected_error_does_not_leak_raw_text(self):
        with mock.patch('services.claude_client.generate_topic_quiz', side_effect=RuntimeError('boom')):
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)
        t = self._refresh()
        self.assertEqual(t.status, QuizTemplate.FAILED)
        self.assertNotIn('boom', t.error_message)
        self.assertTrue(t.error_message)

    def test_already_ready_template_is_not_regenerated(self):
        self.tmpl.status = QuizTemplate.READY
        self.tmpl.save(update_fields=['status'])
        with mock.patch('services.claude_client.generate_topic_quiz') as ai:
            tasks.generate_topic_template(self.tmpl.pk, self.topic.pk)
        ai.assert_not_called()

    def test_word_task_reads_the_pool_once_outside_the_threads(self):
        for i in range(12):
            Word.objects.create(user=self.user, english=f'w{i}', turkish=f'k{i}')
        tmpl = QuizTemplate.objects.create(
            user=self.user, kind=QuizTemplate.WORD, name='Quiz #1', status=QuizTemplate.PENDING,
        )

        def _chunk(pool, n, focus):
            # Havuz ana parçacıkta okunmuş olmalı; thread'den DB'ye bakmıyoruz.
            self.assertEqual(len(pool), 12)
            return [item(f'{focus} {i}') for i in range(n)]

        with mock.patch('services.claude_client.generate_word_quiz_extras', side_effect=_chunk):
            tasks.generate_word_template(tmpl.pk, self.user.pk)
        tmpl.refresh_from_db()
        self.assertEqual(tmpl.status, QuizTemplate.READY)
        self.assertEqual(len(tmpl.questions_data), tasks.QUESTION_TARGET)
