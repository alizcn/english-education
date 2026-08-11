from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from services.claude_client import ClaudeClientError
from . import tasks
from .models import InterviewSession

ITEM = {
    'question_tr': 'Kendinden bahseder misin?',
    'question_en': 'Tell me about yourself.',
    'answer_tr': 'Kısa bir özet.',
    'answer_en': 'A short summary.',
}


class InterviewTaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='x')
        self.session = InterviewSession.objects.create(
            user=self.user,
            source=InterviewSession.CATEGORY,
            job_category='backend_dev',
            status=InterviewSession.PENDING,
        )

    def _refresh(self):
        self.session.refresh_from_db()
        return self.session

    def test_success_marks_ready(self):
        with mock.patch.object(tasks.claude, 'generate_interview_questions', return_value=[ITEM]):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')
        s = self._refresh()
        self.assertEqual(s.status, InterviewSession.READY)
        self.assertEqual(s.questions_data, [ITEM])
        self.assertEqual(s.error_message, '')

    def test_client_error_is_shown_to_user(self):
        err = ClaudeClientError('AI bağlantısı zaman aşımına uğradı, tekrar dene.')
        with mock.patch.object(tasks.claude, 'generate_interview_questions', side_effect=err):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')
        s = self._refresh()
        self.assertEqual(s.status, InterviewSession.FAILED)
        self.assertIn('zaman aşımına', s.error_message)

    def test_unexpected_error_is_caught(self):
        with mock.patch.object(tasks.claude, 'generate_interview_questions', side_effect=RuntimeError('boom')):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')
        s = self._refresh()
        self.assertEqual(s.status, InterviewSession.FAILED)
        # Ham istisna metni kullanıcıya sızmamalı.
        self.assertNotIn('boom', s.error_message)
        self.assertTrue(s.error_message)

    def test_empty_result_marks_failed(self):
        with mock.patch.object(tasks.claude, 'generate_interview_questions', return_value=[]):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')
        self.assertEqual(self._refresh().status, InterviewSession.FAILED)

    def test_deleted_session_does_not_raise(self):
        pk = self.session.pk
        self.session.delete()
        with mock.patch.object(tasks.claude, 'generate_interview_questions', return_value=[ITEM]) as gen:
            tasks.generate_from_title(pk, 'Backend Developer')
        # Oturum yoksa üretime hiç girilmemeli — boşa API çağrısı yapmayalım.
        gen.assert_not_called()

    def test_cv_task_writes_questions(self):
        with mock.patch.object(tasks.claude, 'generate_interview_from_cv', return_value=[ITEM]) as gen:
            tasks.generate_from_cv(self.session.pk, 'cv metni')
        # Üretim paralel parçalara bölünüyor: her parça CV'nin tamamını görür,
        # ama farklı bir odak alır ki parçalar aynı soruyu üretmesin.
        self.assertEqual(gen.call_count, len(tasks._chunk_plan(tasks.QUESTION_COUNT)))
        for call in gen.call_args_list:
            self.assertEqual(call.args, ('cv metni',))
            self.assertEqual(call.kwargs['n'], tasks.CHUNK_SIZE)
        focuses = [c.kwargs['focus'] for c in gen.call_args_list]
        self.assertEqual(len(set(focuses)), len(focuses), focuses)
        self.assertEqual(self._refresh().status, InterviewSession.READY)

    def test_chunks_are_collected_into_one_set(self):
        def _chunk(_cv, n, focus):
            # Her parça kendi odağına göre farklı sorular üretiyormuş gibi davran.
            return [dict(ITEM, question_en=f'{focus} q{i}') for i in range(n)]

        with mock.patch.object(tasks.claude, 'generate_interview_from_cv', side_effect=_chunk):
            tasks.generate_from_cv(self.session.pk, 'cv metni')
        s = self._refresh()
        self.assertEqual(s.status, InterviewSession.READY)
        self.assertEqual(len(s.questions_data), tasks.QUESTION_COUNT)

    def test_partial_results_are_saved_while_still_pending(self):
        """Kullanıcı hepsini beklemesin: biten parça anında oturuma yazılmalı.

        Kayıtları save() üzerinden gözetliyoruz — worker parçacıklarından DB'ye
        bakmak yanıltıcı olurdu, Django orada ayrı bir bağlantı açar.
        """
        saves = []
        original_save = InterviewSession.save

        def _spy(instance, *args, **kwargs):
            saves.append((instance.status, len(instance.questions_data or [])))
            return original_save(instance, *args, **kwargs)

        def _chunk(_title, n, focus):
            return [dict(ITEM, question_en=f'{focus} q{i}') for i in range(n)]

        with mock.patch.object(InterviewSession, 'save', _spy), \
             mock.patch.object(tasks.claude, 'generate_interview_questions', side_effect=_chunk):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')

        partial = [
            count for status, count in saves
            if status == InterviewSession.PENDING and 0 < count < tasks.QUESTION_COUNT
        ]
        self.assertTrue(partial, saves)          # en az bir kısmi kayıt olmalı
        self.assertEqual(partial, sorted(partial))  # sorular birikerek artmalı
        self.assertEqual(self._refresh().status, InterviewSession.READY)

    def test_one_failing_chunk_still_delivers_the_rest(self):
        calls = []

        def _chunk(_title, n, focus):
            calls.append(focus)
            if len(calls) == 1:
                raise ClaudeClientError('bu parça patladı')
            return [dict(ITEM, question_en=f'{focus} q{i}') for i in range(n)]

        with mock.patch.object(tasks.claude, 'generate_interview_questions', side_effect=_chunk):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')
        s = self._refresh()
        # Eldeki sorular teslim edilmeli — hiç yoktan iyi.
        self.assertEqual(s.status, InterviewSession.READY)
        self.assertTrue(s.questions_data)
        self.assertLess(len(s.questions_data), tasks.QUESTION_COUNT)

    def test_redelivery_does_not_duplicate_partial_results(self):
        """acks_late yeniden teslim ederse yarım kalan sorular üst üste binmemeli."""
        self.session.questions_data = [dict(ITEM, question_en='eski yarim sonuc')]
        self.session.save(update_fields=['questions_data'])

        def _chunk(_title, n, focus):
            return [dict(ITEM, question_en=f'{focus} q{i}') for i in range(n)]

        with mock.patch.object(tasks.claude, 'generate_interview_questions', side_effect=_chunk):
            tasks.generate_from_title(self.session.pk, 'Backend Developer')
        s = self._refresh()
        self.assertEqual(len(s.questions_data), tasks.QUESTION_COUNT)
        self.assertNotIn('eski yarim sonuc', [q['question_en'] for q in s.questions_data])


class InterviewViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='ali', password='sifre123')
        self.client.force_login(self.user)

    def test_create_returns_immediately_and_queues(self):
        with mock.patch.object(tasks.generate_from_title, 'delay') as delay:
            resp = self.client.post('/interviews/create/', {'job_category': 'backend_dev'})
        session = InterviewSession.objects.get(user=self.user)
        self.assertEqual(session.status, InterviewSession.PENDING)
        self.assertEqual(session.questions_data, [])
        delay.assert_called_once_with(session.pk, 'Backend Developer')
        self.assertRedirects(resp, f'/interviews/{session.pk}/')

    def test_status_endpoint_reports_state(self):
        session = InterviewSession.objects.create(
            user=self.user, source=InterviewSession.CATEGORY,
            job_category='backend_dev', status=InterviewSession.PENDING,
        )
        resp = self.client.get(f'/interviews/{session.pk}/status/')
        # Sayfa biriken soruları erken gösterebilsin diye ilerleme de dönüyor.
        self.assertEqual(
            resp.json(),
            {'status': 'pending', 'ready_count': 0, 'total': tasks.QUESTION_COUNT},
        )

    def test_status_endpoint_reports_partial_progress(self):
        session = InterviewSession.objects.create(
            user=self.user, source=InterviewSession.CATEGORY, job_category='backend_dev',
            status=InterviewSession.PENDING, questions_data=[ITEM, ITEM, ITEM],
        )
        resp = self.client.get(f'/interviews/{session.pk}/status/')
        self.assertEqual(resp.json()['ready_count'], 3)
        self.assertEqual(resp.json()['status'], 'pending')

    def test_status_endpoint_hides_other_users_sessions(self):
        other = get_user_model().objects.create_user(username='veli', password='x')
        session = InterviewSession.objects.create(
            user=other, source=InterviewSession.CATEGORY, job_category='backend_dev',
        )
        resp = self.client.get(f'/interviews/{session.pk}/status/')
        self.assertEqual(resp.status_code, 404)
