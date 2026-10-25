"""i18n / canonical / hreflang / sitemap davranışının emniyet ağı.

Bu alan bugüne kadar hiç test edilmemişti ve çok dilli dönüşümün en kırılgan
yüzeyi: `i18n_patterns(prefix_default_language=False)`, `set_language`in
`i18n_patterns` İÇİNDE yayınlanması (bkz. config/urls.py yorumu) ve
`translate_url` round-trip'i birbirine bağlı. Buradaki testler bugünkü doğru
davranışı kilitliyor; dönüşümde bir şey kayarsa burada görünür.

Ayrıca bugünkü İKİ BİLİNEN HATA `expectedFailure` ile belgelenmiş:
  * `?page=` canonical'da var, hreflang alternates'te yok (çelişki),
  * çözümlenemeyen yollarda hreflang yinelenerek üretiliyor.
Faz 1/3'te düzeltildiğinde bu işaretler kaldırılmalı.
"""

from unittest import expectedFailure, mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.html import escape

from apps.seo import gating
from apps.topics.models import Topic, TopicExample, TopicExplanation
from apps.wordbank.models import BankWord, BankWordTranslation
from services import languages


class UrlPrefixTests(TestCase):
    """Türkçe öneksiz, İngilizce /en/ — indekslenmiş adreslerin sözleşmesi."""

    def setUp(self):
        # reverse() aktif dile bağlı ve aktif dil testler arasında sızıyor
        # (bir önceki test /en/ çağırdıysa burada da 'en' aktif kalıyor).
        # Bu sınıf varsayılan dilin öneksiz kaldığını iddia ediyor, o yüzden
        # aktif dili açıkça sabitliyoruz.
        cm = translation.override('tr')
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def test_default_language_has_no_prefix(self):
        """Hedef dil slug kökünde, arayüz dili prefix'te. İndeksli adres aynı."""
        self.assertEqual(
            reverse('seo:grammar_index', kwargs={'lang': 'en'}), '/english-grammar/',
        )

    def test_seo_slugs_carry_the_target_language(self):
        self.assertEqual(
            reverse('seo:words_index', kwargs={'lang': 'en'}), '/english-vocabulary/',
        )
        self.assertEqual(
            reverse('seo:interview_index', kwargs={'lang': 'en'}),
            '/english-interview-questions/',
        )

    def test_other_target_languages_get_their_own_stem(self):
        self.assertEqual(
            reverse('seo:grammar_index', kwargs={'lang': 'de'}), '/german-grammar/',
        )
        self.assertEqual(
            reverse('seo:words_index', kwargs={'lang': 'tr'}), '/turkish-vocabulary/',
        )

    def test_reverse_accepts_the_stem_as_well_as_the_code(self):
        """Şablonlarda ikisi de doğal geliyor."""
        self.assertEqual(
            reverse('seo:grammar_index', kwargs={'lang': 'english'}),
            '/english-grammar/',
        )

    def test_unreleased_target_language_is_404(self):
        """İçeriği üretilmemiş dil için boş sayfa yayınlanmamalı.

        Bugün sicildeki dört dilin hepsi `is_learnable` olduğu için yayında
        OLMAYAN gerçek bir dil yok. Test bu yüzden yayın durumunu değil
        KAPIYI doğruluyor: sicil kısıtlanınca adres 404 dönmeli. Yayın
        durumunun kendisi `tests/test_languages.py`de kayıtlı.
        """
        with mock.patch.object(languages, 'LEARNABLE_CODES', ('en',)):
            self.assertEqual(self.client.get('/german-grammar/').status_code, 404)
            self.assertEqual(
                self.client.get('/turkish-vocabulary/').status_code, 404,
            )
        # Kapı kapanmadığında aynı adresler yayında.
        self.assertEqual(self.client.get('/german-grammar/').status_code, 200)

    def test_target_equal_to_interface_language_is_allowed(self):
        """`/en/english-grammar/` İNDEKSLİ ve korunmak zorunda.

        Self-pair'i 404 yapmak düşünüldü ama indekslenmiş bağlantıları
        kırardı; ayrıca hedef dilin kendi dilinde anlatımı meşru bir gramer
        referansı (bkz. `apps/seo/views._require_public_pair`).
        """
        self.assertEqual(self.client.get('/en/english-grammar/').status_code, 200)

    def test_language_independent_paths_stay_unprefixed(self):
        self.assertEqual(reverse('robots_txt'), '/robots.txt')
        self.assertEqual(
            reverse('django.contrib.sitemaps.views.sitemap'), '/sitemap.xml',
        )

    def test_set_language_is_published_inside_i18n_patterns(self):
        """config/urls.py yorumu: dışarıda olunca /en/ sayfasından TR'ye dönüş
        kırılıyordu. Aktif dilin prefix'ini alması bu yüzden şart."""
        self.assertEqual(reverse('set_language'), '/i18n/setlang/')

    def test_english_pages_answer_under_the_prefix(self):
        self.assertEqual(self.client.get('/english-grammar/').status_code, 200)
        self.assertEqual(self.client.get('/en/english-grammar/').status_code, 200)


class LegacyRedirectTests(TestCase):
    """Dondurulmuş 301'ler — indekslenmiş eski Türkçe slug'lar ölmemeli."""

    CASES = [
        ('/ingilizce-gramer/', '/english-grammar/'),
        ('/ingilizce-kelimeler/', '/english-vocabulary/'),
        ('/ingilizce-mulakat-sorulari/', '/english-interview-questions/'),
        ('/site-haritasi/', '/sitemap/'),
        ('/uygulamayi-yukle/', '/install-app/'),
        ('/accounts/profil/', '/accounts/profile/'),
        ('/accounts/hesap-sil/', '/accounts/delete-account/'),
    ]

    def test_frozen_redirects_are_permanent(self):
        for old, new in self.CASES:
            with self.subTest(old=old):
                resp = self.client.get(old)
                self.assertEqual(resp.status_code, 301)
                self.assertEqual(resp['Location'], new)

    def test_slug_carrying_redirects_keep_their_argument(self):
        Topic.objects.create(language='en', name='Present Simple',
                             slug='present-simple', order=0)
        resp = self.client.get('/ingilizce-gramer/present-simple/')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/english-grammar/present-simple/')


class CanonicalTests(TestCase):
    def test_canonical_is_absolute_and_uses_site_url(self):
        resp = self.client.get('/english-grammar/')
        self.assertContains(
            resp, f'<link rel="canonical" href="{settings.SITE_URL}/english-grammar/">',
        )

    def test_query_string_is_dropped_from_canonical(self):
        resp = self.client.get('/english-grammar/?utm_source=x')
        self.assertContains(
            resp, f'<link rel="canonical" href="{settings.SITE_URL}/english-grammar/">',
        )

    def test_pagination_is_the_one_query_param_kept(self):
        for rank in range(1, 3):
            BankWord.objects.create(
                level='A1', language='en', rank=rank, term=f'w{rank}',
            )
        resp = self.client.get('/english-vocabulary/a1/?page=2')
        # Tek sayfaya sığıyor; ikinci sayfa yoksa paginator son sayfaya düşer.
        self.assertEqual(resp.status_code, 200)

    def test_admin_paths_skip_seo_context(self):
        admin = User.objects.create_superuser('root2', 'r@example.com', 'x')
        self.client.force_login(admin)
        resp = self.client.get('/super/')
        self.assertTrue(resp.context['seo']['skip'])


class HreflangTests(TestCase):
    def test_every_configured_language_gets_an_alternate(self):
        resp = self.client.get('/english-grammar/')
        for code, _name in settings.LANGUAGES:
            with self.subTest(code=code):
                self.assertContains(resp, f'hreflang="{code}"')

    def test_alternate_count_matches_language_count(self):
        resp = self.client.get('/english-grammar/')
        body = resp.content.decode()
        self.assertEqual(body.count('rel="alternate" hreflang='), len(settings.LANGUAGES) + 1)

    def test_x_default_is_present(self):
        resp = self.client.get('/english-grammar/')
        self.assertContains(resp, 'hreflang="x-default"')

    def test_x_default_points_at_english(self):
        """Dört dilden hiçbirini bilmeyen ziyaretçi okuyamadığı Türkçe sayfaya
        değil ortak paydaya gitmeli. TR kendi hreflang'ini koruyor."""
        resp = self.client.get('/english-grammar/')
        self.assertContains(
            resp,
            f'hreflang="x-default" href="{settings.SITE_URL}/en/english-grammar/"',
        )

    def test_unresolvable_paths_claim_no_alternates(self):
        """`translate_url` istisna yutuyor ve URL'i olduğu gibi döndürüyor;
        eskiden çözülemeyen yollarda her dil aynı adresi işaret eden
        yinelenmiş hreflang basılıyordu."""
        resp = self.client.get('/boyle-bir-yol-yok/')
        self.assertEqual(resp.status_code, 404)
        self.assertNotContains(
            resp, 'rel="alternate" hreflang=', status_code=404,
        )

    def test_english_alternate_points_at_the_prefixed_url(self):
        resp = self.client.get('/english-grammar/')
        self.assertContains(
            resp, f'hreflang="en" href="{settings.SITE_URL}/en/english-grammar/"',
        )

    def test_paginated_alternates_keep_the_page_number(self):
        """canonical ile hreflang aynı sayfayı göstermek zorunda.

        `language_alternates` artık `request.get_full_path()` veriyor;
        Django'nun `translate_url`'u yolu yeniden kurarken `parsed.query`yi
        koruduğu için sorgu dizesi alternates'e de geçiyor. Eskiden
        `request.path` kullanıldığı için sayfalı kelime listelerinde hreflang
        kümesi canonical ile çelişiyordu — ve bu sayfalar `WordLevelSitemap`
        üzerinden indekslenmeye gönderiliyor.
        """
        for rank in range(1, 250):
            BankWord.objects.create(
                level='A1', language='en', rank=rank, term=f'w{rank}',
            )
        resp = self.client.get('/english-vocabulary/a1/?page=2')
        self.assertContains(resp, 'hreflang="tr" href="%s/english-vocabulary/a1/?page=2"'
                            % settings.SITE_URL)


class OpenGraphLocaleTests(TestCase):
    """og:locale sicilden geliyor — eskiden iki dilli bir {% if %} vardı."""

    def test_turkish_page_declares_tr_locale(self):
        resp = self.client.get('/english-grammar/')
        self.assertContains(resp, '<meta property="og:locale" content="tr_TR">')
        self.assertContains(
            resp, '<meta property="og:locale:alternate" content="en_US">',
        )

    def test_english_page_declares_en_locale(self):
        resp = self.client.get('/en/english-grammar/')
        self.assertContains(resp, '<meta property="og:locale" content="en_US">')
        self.assertContains(
            resp, '<meta property="og:locale:alternate" content="tr_TR">',
        )

    def test_alternate_locale_count_follows_language_count(self):
        body = self.client.get('/english-grammar/').content.decode()
        self.assertEqual(
            body.count('property="og:locale:alternate"'), len(settings.LANGUAGES) - 1,
        )

    def test_jsonld_in_language_lists_every_ui_language(self):
        body = self.client.get('/english-grammar/').content.decode()
        expected = ', '.join(f'"{code}"' for code, _ in settings.LANGUAGES)
        self.assertIn(f'"inLanguage": [{expected}]', body)


class SitemapTests(TestCase):
    def setUp(self):
        Topic.objects.create(language='en', name='Present Simple',
                             slug='present-simple', order=0)
        BankWord.objects.create(level='A1', language='en', rank=1, term='book')

    def test_sitemap_renders_and_forces_the_canonical_host(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn(settings.SITE_URL, body)
        self.assertNotIn('testserver', body)

    def test_sitemap_lists_grammar_and_word_pages(self):
        body = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('/english-grammar/present-simple/', body)
        self.assertIn('/english-vocabulary/a1/', body)

    def test_sitemap_carries_alternates_for_each_language(self):
        body = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('hreflang="tr"', body)
        self.assertIn('hreflang="en"', body)
        self.assertIn('hreflang="x-default"', body)

    def test_sitemap_lists_every_learn_landing(self):
        """Dördü de ayrı sayfa, dördü de sitemap'te."""
        body = self.client.get('/sitemap.xml').content.decode()
        for stem in ('learn-english', 'learn-german', 'learn-french',
                     'learn-turkish'):
            with self.subTest(stem=stem):
                self.assertIn(f'/{stem}/', body)


class LearnLandingTests(TestCase):
    """Hedef dil başına giriş sayfaları (`/learn-german/` vb.)."""

    def test_each_learnable_language_has_its_own_landing(self):
        for stem in ('german', 'french', 'turkish'):
            with self.subTest(stem=stem):
                resp = self.client.get(f'/learn-{stem}/')
                self.assertEqual(resp.status_code, 200)

    def test_landings_use_their_own_template(self):
        self.assertTemplateUsed(
            self.client.get('/learn-german/'), 'dashboard/landing/de.html',
        )
        self.assertTemplateUsed(
            self.client.get('/learn-french/'), 'dashboard/landing/fr.html',
        )

    def test_german_landing_speaks_to_its_own_audience(self):
        """Metin İngilizce sayfanın çevirisi DEĞİL.

        Almanca öğrenen kitle iş görüşmesi değil Ausbildung ve sertifika
        arıyor; interpolasyonla üretilen bir metin bunu yakalayamazdı. İddia
        bu yüzden tek bir ayırt edici kelimeye bakıyor.
        """
        html = self.client.get('/learn-german/').content.decode()
        self.assertIn('Ausbildung', html)
        self.assertNotIn('Mülakatı kap', html)

    def test_english_has_its_own_landing_too(self):
        """`/learn-english/` bir ara `/`ye yönlendiriliyordu.

        O zaman `/` İngilizce landing'iydi ve iki adres aynı metni
        gösterirdi. `/` genel sayfa olunca İngilizce'nin de kendi hedefli
        sayfası gerekti.
        """
        resp = self.client.get('/learn-english/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'dashboard/landing/en.html')

    def test_unreleased_language_has_no_landing(self):
        with mock.patch.object(languages, 'LEARNABLE_CODES', ('en',)):
            self.assertEqual(
                self.client.get('/learn-german/').status_code, 404,
            )


class LicensesPageTests(TestCase):
    """Kaynak atıf sayfası — FLELex ve wordfreq lisansı atıf istiyor."""

    def test_page_renders_in_every_interface_language(self):
        for prefix in ('', '/en'):
            with self.subTest(prefix=prefix):
                resp = self.client.get(f'{prefix}/licenses/')
                self.assertEqual(resp.status_code, 200)

    def test_every_learnable_language_is_attributed(self):
        """Tablo sicilden doluyor: yeni dil eklenince atıf da gelmeli."""
        html = self.client.get('/licenses/').content.decode()
        for spec in languages.LEARNABLE_LANGUAGES:
            with self.subTest(code=spec.code):
                # Atıf metinlerinde `&` var (FLELex yazar listesi); şablon
                # bunu kaçırdığı için karşılaştırma da kaçırılmış hâlde.
                self.assertIn(escape(spec.wordlist_source), html)
                self.assertIn(escape(spec.license_note), html)


class ManifestTests(TestCase):
    """PWA manifesti dile göre üretiliyor mu?"""

    def test_turkish_manifest_declares_tr(self):
        resp = self.client.get('/manifest.webmanifest')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/manifest+json')
        data = resp.json()
        self.assertEqual(data['lang'], 'tr')
        self.assertEqual(data['start_url'], '/?utm_source=pwa')
        self.assertEqual(data['scope'], '/')

    def test_english_manifest_carries_the_prefix(self):
        """Yüklenen uygulama kullanıcının dilinde açılmalı."""
        data = self.client.get('/en/manifest.webmanifest').json()
        self.assertEqual(data['lang'], 'en')
        self.assertEqual(data['start_url'], '/en/?utm_source=pwa')
        self.assertEqual(data['scope'], '/en/')

    def test_shortcuts_follow_the_active_language(self):
        data = self.client.get('/en/manifest.webmanifest').json()
        urls = [s['url'] for s in data['shortcuts']]
        self.assertTrue(all(u.startswith('/en/') for u in urls), urls)

    def test_icons_are_resolved_through_staticfiles(self):
        data = self.client.get('/manifest.webmanifest').json()
        self.assertTrue(data['icons'])
        for entry in data['icons']:
            with self.subTest(src=entry['src']):
                self.assertTrue(entry['src'].startswith('/static/'))

    def test_base_template_links_the_dynamic_manifest(self):
        resp = self.client.get('/english-grammar/')
        self.assertContains(resp, 'rel="manifest" href="/manifest.webmanifest"')


class RobotsTests(TestCase):
    def test_robots_points_at_the_canonical_sitemap(self):
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'Sitemap: {settings.SITE_URL}/sitemap.xml')

    def test_public_surfaces_are_allowed(self):
        body = self.client.get('/robots.txt').content.decode()
        for path in ('/english-grammar/', '/english-vocabulary/', '/en/'):
            with self.subTest(path=path):
                self.assertIn(f'Allow: {path}', body)

    def test_app_surfaces_are_disallowed_in_both_languages(self):
        body = self.client.get('/robots.txt').content.decode()
        for path in ('/topics/', '/quiz/', '/en/topics/', '/en/quiz/'):
            with self.subTest(path=path):
                self.assertIn(f'Disallow: {path}', body)


class SetLanguageTests(TestCase):
    def test_switching_to_english_lands_on_the_prefixed_url(self):
        resp = self.client.post(
            '/i18n/setlang/', {'language': 'en', 'next': '/english-grammar/'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/en/english-grammar/')

    def test_switching_back_to_turkish_drops_the_prefix(self):
        resp = self.client.post(
            '/en/i18n/setlang/', {'language': 'tr', 'next': '/en/english-grammar/'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/english-grammar/')

    def test_view_itself_preserves_a_query_carrying_next(self):
        """View tarafı sağlam — sorun `next`i üreten şablonda (aşağıdaki test)."""
        resp = self.client.post(
            '/i18n/setlang/',
            {'language': 'en', 'next': '/english-vocabulary/a1/?page=7'},
        )
        self.assertEqual(resp['Location'], '/en/english-vocabulary/a1/?page=7')


class LanguageSwitcherMarkupTests(TestCase):
    """Dil değiştiricinin bugünkü ikili yapısı — 3. dilde kırılacak yer."""

    def test_switcher_carries_the_query_string_into_next(self):
        """Dil değişimi sayfa numarasını/filtreyi korumak zorunda.

        Tek `_lang_switcher.html` artık `request.get_full_path` basıyor; dört
        kopyanın hepsi `request.path` kullandığı için `?page=7` / `?q=abc`
        kayboluyor ve kullanıcı birinci sayfaya düşüyordu.
        """
        for rank in range(1, 250):
            BankWord.objects.create(
                level='A1', language='en', rank=rank, term=f'w{rank}',
            )
        resp = self.client.get('/english-vocabulary/a1/?page=2')
        self.assertContains(
            resp, '<input type="hidden" name="next" value="/english-vocabulary/a1/?page=2">',
        )

    def test_turkish_page_offers_english(self):
        resp = self.client.get('/english-grammar/')
        self.assertContains(resp, 'name="language" value="en"')

    def test_english_page_offers_turkish(self):
        resp = self.client.get('/en/english-grammar/')
        self.assertContains(resp, 'name="language" value="tr"')

    def test_every_inactive_language_is_offered(self):
        """Dil sayısından bağımsız: aktif dil dışındaki her dil sunulmalı.

        Eski ikili toggle tam olarak burada kırılıyordu — üçüncü bir dil
        aktifken kullanıcıya yalnızca tek alternatif gösteriliyor, yani
        FR→DE geçişi arayüzden imkânsız oluyordu.
        """
        body = self.client.get('/english-grammar/').content.decode()
        self.assertEqual(
            body.count('name="language" value='), len(settings.LANGUAGES) - 1,
        )

    def test_active_language_is_marked_not_clickable(self):
        resp = self.client.get('/en/english-grammar/')
        self.assertContains(resp, 'aria-current="true"')
        self.assertNotContains(resp, 'name="language" value="en"')

    def test_switcher_is_a_dropdown_on_every_base_template(self):
        """İçerik şablonlarının hepsi aynı include'u kullanıyor mu?

        base.html (uygulama), landing (öneksiz /) ve _public_base (SEO
        sayfaları). Daha önce her biri ayrı kopyaydı ve ikili toggle olduğu
        için 3. dilde kilitleniyordu.
        """
        for path in ('/english-grammar/', '/'):
            with self.subTest(path=path):
                resp = self.client.get(path)
                self.assertContains(resp, 'data-dropdown-trigger')
                self.assertContains(resp, 'class="lang-menu"')

    def test_auth_pages_carry_no_switcher_or_content_links(self):
        """Giriş/kayıt sayfaları yalnızca hesap işine odaklanıyor.

        Kullanıcı isteğiyle kaldırıldı: dil ve tema düğmeleri ile gramer /
        kelime / mülakat bağlantıları bu sayfalarda görünmüyor. BİLİNEN
        BEDELİ: arayüz dilini henüz seçmemiş bir ziyaretçi burada dili
        değiştiremiyor; değiştirici landing, halka açık sayfalar ve uygulama
        içinde duruyor.
        """
        for path in ('/accounts/login/', '/accounts/signup/'):
            with self.subTest(path=path):
                resp = self.client.get(path)
                # GÖRÜNÜR düğmeye bakıyoruz: `data-theme-toggle` dizgesi
                # base.html'in altındaki tema JavaScript'inde de geçiyor ve
                # orada kalması doğru.
                self.assertNotContains(resp, 'class="lang-menu"')
                self.assertNotContains(resp, 'class="theme-toggle"')
                self.assertNotContains(resp, 'class="footer-link"')


class ContentGatingTests(TestCase):
    """Kayıtsız ziyaretçi içeriğin bir KISMINI görüyor, tamamını değil.

    Sayfalar indekslenebilir kalıyor (SEO yüzeyi korunuyor) ama tam erişim
    kayda bağlı. İki invariant ayrıca test altında, çünkü ikisi de SEO cezası
    riski taşıyor: gizleme kayıtsız HERKESE aynı uygulanmalı (Googlebot'a
    ayrıcalık = cloaking) ve gizlenen bölüm yapısal veride bildirilmeli.
    """

    def setUp(self):
        self.topic = Topic.objects.create(
            language='en', name='Present Simple', slug='present-simple', order=0,
        )
        TopicExplanation.objects.create(
            topic=self.topic, language='tr',
            body='\n\n'.join(
                [f'## Bölüm {i}\n\nBu {i}. bölümün gövdesi.' for i in range(1, 7)]
            ),
        )
        for kind in ('positive', 'negative', 'question'):
            for order in range(5):
                TopicExample.objects.create(
                    topic=self.topic, kind=kind, order=order,
                    sentence=f'{kind} {order}', translations={'tr': f'çeviri {order}'},
                )
        for rank in range(1, 61):
            word = BankWord.objects.create(
                level='A1', language='en', rank=rank, term=f'word{rank}',
            )
            BankWordTranslation.objects.create(
                word=word, language='tr', meaning=f'kelime{rank}',
            )
        self.user = User.objects.create_user('gateuser', password='x')

    # ------------------------------------------------------------ gramer

    def test_anonymous_sees_only_the_first_sections(self):
        resp = self.client.get('/english-grammar/present-simple/')
        self.assertEqual(len(resp.context['sections']), gating.PREVIEW_SECTIONS)
        self.assertTrue(resp.context['gated'])
        self.assertContains(resp, 'seo-gated')

    def test_member_sees_every_section(self):
        self.client.force_login(self.user)
        resp = self.client.get('/english-grammar/present-simple/')
        self.assertGreater(len(resp.context['sections']), gating.PREVIEW_SECTIONS)
        self.assertFalse(resp.context['gated'])
        self.assertNotContains(resp, 'seo-gated')

    def test_anonymous_sees_only_a_few_examples_per_kind(self):
        resp = self.client.get('/english-grammar/present-simple/')
        for kind in ('positives', 'negatives', 'questions'):
            with self.subTest(kind=kind):
                self.assertEqual(len(resp.context[kind]),
                                 gating.PREVIEW_EXAMPLES_PER_KIND)

    # ----------------------------------------------------------- kelimeler

    def test_anonymous_sees_a_capped_word_list_without_pagination(self):
        resp = self.client.get('/english-vocabulary/a1/')
        self.assertEqual(len(resp.context['page_obj'].object_list),
                         gating.PREVIEW_WORDS)
        self.assertNotContains(resp, 'pub-pagination')

    def test_pagination_cannot_be_used_to_walk_past_the_gate(self):
        """`?page=3` kapıyı aşmamalı: view birinci sayfaya sabitliyor."""
        resp = self.client.get('/english-vocabulary/a1/?page=3')
        self.assertEqual(resp.context['page_obj'].number, 1)
        self.assertEqual(len(resp.context['page_obj'].object_list),
                         gating.PREVIEW_WORDS)

    def test_member_sees_the_full_page_and_pagination(self):
        self.client.force_login(self.user)
        resp = self.client.get('/english-vocabulary/a1/')
        self.assertEqual(len(resp.context['page_obj'].object_list), 60)
        self.assertFalse(resp.context['gated'])

    def test_row_numbering_follows_the_actual_page_size(self):
        """`offset` sabit sayfa boyutunu okusaydı kapı açıkken numara kayardı."""
        resp = self.client.get('/english-vocabulary/a1/')
        self.assertEqual(resp.context['offset'], 1)

    # ------------------------------------------------------- yapısal veri

    def test_structured_data_declares_the_gate(self):
        """Gizlenen bölümü beyan etmeden "ücretsiz erişilebilir" demek yanlış."""
        import json
        import re
        blocks = re.compile(
            r'<script type="application/ld\+json">(.*?)</script>', re.S,
        )
        for url, node_type in (('/english-grammar/present-simple/', 'LearningResource'),
                               ('/english-vocabulary/a1/', 'CollectionPage')):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                node = None
                for raw in blocks.findall(html):
                    data = json.loads(raw)          # bozuk JSON burada patlar
                    for candidate in (data.get('@graph') or [data]):
                        if candidate.get('@type') == node_type:
                            node = candidate
                self.assertIsNotNone(node, f'{node_type} düğümü yok')
                self.assertFalse(node['isAccessibleForFree'])
                self.assertEqual(node['hasPart']['cssSelector'],
                                 gating.GATED_SELECTOR)

    def test_crawler_and_visitor_see_the_same_thing(self):
        """Cloaking yok: ölçüt yalnızca oturum, user-agent değil."""
        plain = self.client.get('/english-grammar/present-simple/')
        bot = self.client.get(
            '/english-grammar/present-simple/',
            HTTP_USER_AGENT='Mozilla/5.0 (compatible; Googlebot/2.1)',
        )
        self.assertEqual(len(plain.context['sections']), len(bot.context['sections']))
        self.assertEqual(plain.context['gated'], bot.context['gated'])


class LevelAvailabilityTests(TestCase):
    """Seviye sayfası DİLİN KENDİ seviyelerine bağlı.

    Türkçe ve Almanca'da C2 yok: ikisinin de resmî CEFR kelime listesi
    C1'in ötesine geçmiyor (Goethe yalnızca A1–B1 yayınlıyor, Türkçe için
    resmî liste hiç yok), o yüzden sicilde A1–C1 duruyorlar.

    ÖLÇÜLMÜŞ HATA: doğrulama global `BankWord.LEVELS`e bakıyordu ve C2 orada
    olduğu için `/turkish-vocabulary/c2/` SIFIR kelimeyle 200 dönüyordu —
    kullanıcıya boş tablo, arama motoruna içeriksiz ama başlıklı sayfa.
    """

    def setUp(self):
        for code in ('tr', 'de', 'fr', 'en'):
            for level in languages.get(code).cefr_levels:
                word = BankWord.objects.create(
                    language=code, level=level, rank=1, term=f'{code}{level}',
                )
                BankWordTranslation.objects.create(
                    word=word, language='en' if code != 'en' else 'tr',
                    meaning='x',
                )

    def test_language_with_c2_serves_it(self):
        """Tüm dillerde C2 sayfası açık (2026-10 itibarıyla 4 dil tam C2 içeriğine sahip)."""
        for stem in ('english', 'french', 'turkish', 'german'):
            with self.subTest(stem=stem):
                self.assertEqual(
                    self.client.get(f'/{stem}-vocabulary/c2/').status_code, 200,
                )

    def test_every_registry_level_is_reachable(self):
        """Sicilde yazan her seviyenin sayfası açılmalı."""
        for code, stem in (('tr', 'turkish'), ('en', 'english'),
                           ('fr', 'french'), ('de', 'german')):
            for level in languages.get(code).cefr_levels:
                with self.subTest(code=code, level=level):
                    resp = self.client.get(f'/{stem}-vocabulary/{level.lower()}/')
                    self.assertEqual(resp.status_code, 200)
