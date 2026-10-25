"""Kurs yönlendirmesi: prefix, middleware, eski yollar ve kurs seçici.

Bu katmanın en sinsi hatası contextvar sızıntısı olurdu: bir kullanıcının
Almanca kursu başkasının İngilizce isteğine karışırsa veri karışmaz ama
kullanıcı yanlış dilde içerik görür ve bunu kimse fark etmez. O yüzden
sızıntının kendisi test altında.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserCourse
from apps.accounts.services import ensure_active_course
from services import languages

from .current import activate_target, deactivate, get_current_target
from .prefix import PREFIX_ROOT, bind_reverse_cache, clear_reverse_cache


class PrefixReverseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ali', password='x')
        ensure_active_course(self.user, target='en', native='tr')
        self.client.force_login(self.user)
        self.addCleanup(deactivate)

    def test_app_urls_carry_the_course_prefix(self):
        """Şablonlardaki `{% url %}` çağrılarının hiçbiri değişmedi; prefix
        otomatik ekleniyor."""
        resp = self.client.get('/learn/en/topics/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'/{PREFIX_ROOT}/en/')

    def test_prefixed_url_resolves(self):
        for path in ('/learn/en/topics/', '/learn/en/wordbank/', '/learn/en/words/',
                     '/learn/en/chat/', '/learn/en/interviews/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_unknown_language_in_prefix_is_404(self):
        self.assertEqual(self.client.get('/learn/zz/topics/').status_code, 404)

    def test_unprefixed_app_path_redirects_to_the_active_course(self):
        resp = self.client.get('/topics/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/learn/en/topics/')

    def test_legacy_redirect_keeps_the_rest_of_the_path(self):
        resp = self.client.get('/wordbank/A1/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/learn/en/wordbank/A1/')

    def test_legacy_redirect_is_temporary_and_private(self):
        """302 ve `Cache-Control: private`: hedef kullanıcının aktif kursuna
        bağlı, paylaşılan cache'e yazılmamalı."""
        resp = self.client.get('/topics/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('private', resp['Cache-Control'])

    def test_seo_paths_are_not_captured_by_the_legacy_rule(self):
        """`apps.learn.legacy` yalnızca uygulama köklerini yakalıyor."""
        self.assertEqual(self.client.get('/english-grammar/').status_code, 200)

    def test_frozen_seo_redirects_still_win(self):
        resp = self.client.get('/ingilizce-gramer/')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/english-grammar/')


class ContextVarIsolationTests(TestCase):
    """Hedef dil istekler arasında SIZMAMALI."""

    def setUp(self):
        self.a = get_user_model().objects.create_user('a', password='x')
        self.b = get_user_model().objects.create_user('b', password='x')
        ensure_active_course(self.a, target='en', native='tr')
        ensure_active_course(self.b, target='en', native='tr')
        self.addCleanup(deactivate)

    def test_target_is_cleared_after_each_request(self):
        self.client.force_login(self.a)
        self.client.get('/learn/en/topics/')
        self.assertIsNone(
            get_current_target(),
            'contextvar istek sonrası temizlenmedi — başka bir isteğe sızar',
        )

    def test_two_consecutive_requests_do_not_bleed(self):
        self.client.force_login(self.a)
        self.client.get('/learn/en/topics/')
        self.client.logout()

        self.client.force_login(self.b)
        resp = self.client.get('/topics/')
        self.assertEqual(resp['Location'], '/learn/en/topics/')
        self.assertIsNone(get_current_target())

    def test_anonymous_request_leaves_no_target(self):
        self.client.get('/english-grammar/')
        self.assertIsNone(get_current_target())


class SetLanguageRoundTripTests(TestCase):
    """`set_language` → `translate_url` → `resolve()` + `reverse()` zinciri.

    `CoursePrefixPattern.match()` çözümleme sırasında dili aktive etmezse
    `reverse` prefix'i bilemiyor ve kurs prefix'li bir sayfadan dil
    değiştirmek kullanıcıyı bozuk bir adrese atıyor.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user('ali', password='x')
        ensure_active_course(self.user, target='en', native='tr')
        self.client.force_login(self.user)
        self.addCleanup(deactivate)

    def test_switching_language_keeps_the_course_prefix(self):
        resp = self.client.post(
            '/i18n/setlang/', {'language': 'en', 'next': '/learn/en/topics/'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/en/learn/en/topics/')

    def test_switching_back_drops_the_interface_prefix_only(self):
        resp = self.client.post(
            '/en/i18n/setlang/', {'language': 'tr', 'next': '/en/learn/en/topics/'},
        )
        self.assertEqual(resp['Location'], '/learn/en/topics/')

    def test_query_string_survives_a_course_prefixed_page(self):
        resp = self.client.post(
            '/i18n/setlang/',
            {'language': 'en', 'next': '/learn/en/words/?q=book'},
        )
        self.assertEqual(resp['Location'], '/en/learn/en/words/?q=book')


class CourseSelectorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ali', password='x')
        self.client.force_login(self.user)
        self.addCleanup(deactivate)

    def test_course_list_renders(self):
        ensure_active_course(self.user, target='en', native='tr')
        resp = self.client.get(reverse('learn:courses'))
        self.assertEqual(resp.status_code, 200)

    def test_adding_an_unreleased_language_is_rejected(self):
        """Yayında olmayan dile kurs açılmamalı.

        Varsayılan İngilizce kursu bu istekte middleware tarafından açılıyor,
        bu yüzden iddia "hiç kurs yok" değil "ALMANCA kurs yok". Dört dilin
        hepsi bugün öğrenilebilir olduğu için kapı sicil kısıtlanarak
        sınanıyor.
        """
        with mock.patch.object(languages, 'LEARNABLE_CODES', ('en',)):
            resp = self.client.post(
                reverse('learn:add'), {'target_language': 'de'},
            )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            UserCourse.objects.filter(user=self.user, target_language='de').exists(),
        )

    def test_adding_a_second_course_deactivates_the_first(self):
        """İkinci kurs `IntegrityError` veriyordu.

        `one_active_course` kısmi tekilliği kullanıcı başına tek aktif satır
        bırakıyor; `ensure_active_course` yeni satırı aktif doğurup diğerlerini
        SONRA pasife çekiyordu, yani INSERT anında iki aktif satır oluyordu.
        """
        ensure_active_course(self.user, target='en', native='tr')
        resp = self.client.post(
            reverse('learn:add'),
            {'target_language': 'de', 'native_language': 'tr'},
        )
        self.assertEqual(resp.status_code, 302)
        german = UserCourse.objects.get(user=self.user, target_language='de')
        english = UserCourse.objects.get(user=self.user, target_language='en')
        self.assertTrue(german.is_active)
        self.assertFalse(english.is_active)

    def test_adding_a_released_language_creates_an_active_course(self):
        resp = self.client.post(
            reverse('learn:add'), {'target_language': 'en', 'native_language': 'tr'},
        )
        self.assertEqual(resp.status_code, 302)
        course = UserCourse.objects.get(user=self.user, target_language='en')
        self.assertTrue(course.is_active)

    def test_native_equal_to_target_falls_back(self):
        self.client.post(
            reverse('learn:add'), {'target_language': 'en', 'native_language': 'en'},
        )
        course = UserCourse.objects.get(user=self.user, target_language='en')
        self.assertNotEqual(course.native_language, 'en')

    def test_switching_activates_the_chosen_course(self):
        a = ensure_active_course(self.user, target='en', native='tr')
        b = UserCourse.objects.create(
            user=self.user, target_language='de', native_language='tr',
        )
        self.client.post(reverse('learn:switch'), {'course_id': b.pk})
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.is_active)
        self.assertTrue(b.is_active)

    def test_cannot_switch_to_another_users_course(self):
        other = get_user_model().objects.create_user('veli', password='x')
        foreign = ensure_active_course(other, target='en', native='tr')
        resp = self.client.post(reverse('learn:switch'), {'course_id': foreign.pk})
        self.assertEqual(resp.status_code, 404)

    def test_native_language_can_be_changed(self):
        course = ensure_active_course(self.user, target='en', native='tr')
        self.client.post(
            reverse('learn:set_native'),
            {'course_id': course.pk, 'native_language': 'en'},
        )
        course.refresh_from_db()
        # Hedefle aynı olamaz; değişiklik reddedilmeli.
        self.assertEqual(course.native_language, 'tr')

    def test_course_pages_require_login(self):
        self.client.logout()
        resp = self.client.get(reverse('learn:courses'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])


class MiddlewareBindingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ali', password='x')
        self.addCleanup(deactivate)

    def test_request_carries_the_course(self):
        ensure_active_course(self.user, target='en', native='tr')
        self.client.force_login(self.user)
        resp = self.client.get('/learn/en/topics/')
        self.assertEqual(resp.wsgi_request.target_language, 'en')
        self.assertEqual(resp.wsgi_request.native_language, 'tr')
        self.assertIsNotNone(resp.wsgi_request.course)

    def test_anonymous_request_has_no_course(self):
        resp = self.client.get('/english-grammar/')
        self.assertIsNone(resp.wsgi_request.course)

    def test_course_is_created_on_first_authenticated_request(self):
        """Sinyal kurs açmıyor; ilk istekte middleware açıyor."""
        self.client.force_login(self.user)
        self.assertEqual(UserCourse.objects.filter(user=self.user).count(), 0)
        self.client.get('/learn/en/topics/')
        self.assertEqual(UserCourse.objects.filter(user=self.user).count(), 1)


class ReverseCacheTests(TestCase):
    """`reverse()` AKTİF KURSU izlemek zorunda — önbellek onu unutuyordu.

    ÖLÇÜLMÜŞ HATA: Django `_reverse_dict`i yalnızca `get_language()`e göre
    anahtarlıyor. Kurs öneki anahtarın parçası olmadığı için süreçteki İLK
    `reverse()` kursu önbelleğe gömüyordu ve sonraki bütün çağrılar aktif
    kurs ne olursa olsun onu döndürüyordu::

        kurs=de -> /learn/de/topics/
        kurs=fr -> /learn/de/topics/   # yanlış

    Tek gunicorn işçisi birçok kullanıcıya hizmet ettiği için bu, ilk
    isteğin kursunun herkesin menü bağlantılarına sızması demekti: Almanca
    çalışan kullanıcı menüye basınca `/learn/en/...`e gidiyor ve
    `CourseMiddleware` onu farkında olmadan İngilizce kursuna taşıyordu.
    """

    def setUp(self):
        clear_reverse_cache()
        self.addCleanup(deactivate)
        self.addCleanup(clear_reverse_cache)

    def test_reverse_follows_the_active_course(self):
        for code in ('de', 'fr', 'tr', 'en', 'de'):
            with self.subTest(code=code):
                token = activate_target(code)
                try:
                    bind_reverse_cache()
                    self.assertEqual(reverse('topics:list'),
                                     f'/{PREFIX_ROOT}/{code}/topics/')
                    self.assertEqual(reverse('wordbank:quiz', args=['A1']),
                                     f'/{PREFIX_ROOT}/{code}/wordbank/A1/')
                finally:
                    deactivate(token)

    def test_public_urls_are_unaffected_by_the_course(self):
        """Kurs öneki yalnızca `course_patterns` altını etkilemeli."""
        seen = set()
        for code in ('de', 'fr'):
            token = activate_target(code)
            try:
                bind_reverse_cache()
                seen.add((reverse('dashboard:home'),
                          reverse('seo:grammar_index', kwargs={'lang': 'en'})))
            finally:
                deactivate(token)
        self.assertEqual(seen, {('/', '/english-grammar/')})

    def test_two_courses_in_sequence_get_their_own_links(self):
        """İstek akışında: Almanca kurstan üretilen bağlantı Almanca olmalı."""
        user = get_user_model().objects.create_user('veli', password='x')
        self.client.force_login(user)
        for target in ('en', 'de', 'fr'):
            self.client.post('/learn/add/', {'target_language': target,
                                             'native_language': 'tr'})
            with self.subTest(target=target):
                resp = self.client.get(f'/learn/{target}/topics/')
                self.assertEqual(resp.status_code, 200)
                self.assertIn(f'/{PREFIX_ROOT}/{target}/',
                              resp.content.decode())


class CourseBarTests(TestCase):
    """Uygulama içinde sürekli görünen kurs şeridi.

    Kullanıcı birden çok dil çalışabildiği için hangi kursta olduğu her
    sayfada görünmek zorunda; eskiden bu bilgi yalnızca URL'de
    (`/learn/de/...`) duruyordu ve sayfalar arasında gezerken kayboluyordu.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user('ayse', password='x')
        self.client.force_login(self.user)
        self.addCleanup(deactivate)

    def test_bar_names_the_active_course_with_correct_inflection(self):
        """Türkçe'de ünlü uyumu: "Almancayı", "Türkçeyi" — "Almanca" değil."""
        for target, expected in (('de', 'Almancayı'), ('fr', 'Fransızcayı'),
                                 ('tr', 'Türkçeyi'), ('en', 'İngilizceyi')):
            with self.subTest(target=target):
                native = 'tr' if target != 'tr' else 'en'
                self.client.post('/learn/add/', {'target_language': target,
                                                 'native_language': native})
                html = self.client.get(f'/learn/{target}/topics/').content.decode()
                self.assertIn('course-bar', html)
                self.assertIn(expected, html)

    def test_bar_offers_a_way_to_switch(self):
        ensure_active_course(self.user, target='en', native='tr')
        html = self.client.get('/learn/en/topics/').content.decode()
        self.assertIn(reverse('learn:courses'), html)

    def test_bar_is_absent_without_a_course(self):
        """Halka açık sayfalarda ve çıkış yapmış kullanıcıda şerit yok."""
        self.client.logout()
        for path in ('/english-grammar/', '/accounts/login/', '/'):
            with self.subTest(path=path):
                self.assertNotIn(
                    'course-bar',
                    self.client.get(path).content.decode(),
                )
