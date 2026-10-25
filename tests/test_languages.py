"""Dil sicili (services/languages.py) sözleşmesi.

Sicil `settings.LANGUAGES`i besliyor, SEO slug köklerini ve AI promptlarına
giden dil adlarını veriyor. Buradaki testler sicilin kendi içinde tutarlı
kalmasını ve ayarlarla ayrışmamasını güvenceye alıyor — bir dil eklenirken
yarım bırakılan alan burada görünür.
"""

import unittest

from django.conf import settings

from services import languages as L


class RegistryShapeTests(unittest.TestCase):
    def test_codes_are_unique(self):
        codes = [spec.code for spec in L.ALL]
        self.assertEqual(len(codes), len(set(codes)))

    def test_seo_stems_are_unique(self):
        """SEO slug kökü URL'de ayırt edici olmak zorunda."""
        stems = [spec.seo_stem for spec in L.ALL]
        self.assertEqual(len(stems), len(set(stems)))

    def test_lookup_tables_cover_every_language(self):
        self.assertEqual(set(L.BY_CODE), {spec.code for spec in L.ALL})
        self.assertEqual(set(L.BY_SEO_STEM), {spec.seo_stem for spec in L.ALL})

    def test_lookup_tables_are_read_only(self):
        with self.assertRaises(TypeError):
            L.BY_CODE['xx'] = None

    def test_every_language_declares_the_core_fields(self):
        for spec in L.ALL:
            with self.subTest(code=spec.code):
                self.assertTrue(spec.english_name)
                self.assertTrue(spec.native_name)
                self.assertTrue(spec.og_locale)
                self.assertTrue(spec.seo_stem)
                self.assertTrue(spec.cefr_levels)

    def test_cefr_levels_start_at_a1_and_stay_ordered(self):
        order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        for spec in L.ALL:
            with self.subTest(code=spec.code):
                self.assertEqual(spec.cefr_levels[0], 'A1')
                self.assertEqual(
                    list(spec.cefr_levels), order[:len(spec.cefr_levels)],
                )

    def test_learnable_languages_name_their_wordlist_source(self):
        """Kaynak ve lisans notu olmadan içerik yayınlanmamalı."""
        for spec in L.ALL:
            with self.subTest(code=spec.code):
                self.assertTrue(spec.wordlist_source, f'{spec.code}: kaynak yok')
                self.assertTrue(spec.license_note, f'{spec.code}: lisans notu yok')

    def test_unknown_code_raises(self):
        with self.assertRaises(L.UnknownLanguage):
            L.get('xx')
        with self.assertRaises(L.UnknownLanguage):
            L.by_seo_stem('klingon')


class SettingsAgreementTests(unittest.TestCase):
    def test_settings_languages_mirror_the_ui_registry(self):
        self.assertEqual(
            settings.LANGUAGES,
            [(spec.code, spec.native_name) for spec in L.UI_LANGUAGES],
        )

    def test_default_language_is_a_ui_language(self):
        self.assertIn(settings.LANGUAGE_CODE, L.UI_CODES)

    def test_default_language_comes_first(self):
        """`i18n_patterns(prefix_default_language=False)` varsayılanı öneksiz
        bırakıyor; sicil sırası dil seçicide de kullanıldığı için varsayılan
        başta olmalı."""
        self.assertEqual(L.UI_CODES[0], settings.LANGUAGE_CODE)


class DisplayNameTests(unittest.TestCase):
    def test_every_language_is_named_in_every_ui_language(self):
        """Dört dilin adı, yayında olan her arayüz dilinde yazılı olmalı."""
        for spec in L.ALL:
            for ui in L.UI_CODES:
                with self.subTest(code=spec.code, in_language=ui):
                    self.assertIn(ui, spec.display, f'{spec.code} -> {ui} eksik')
                    self.assertTrue(spec.display[ui].get('nom'))

    def test_turkish_declensions_are_complete(self):
        """Türkçe arayüz metinleri hâl eki istiyor; beşi de yazılı olmalı."""
        for spec in L.ALL:
            table = spec.display['tr']
            for case in ('nom', 'acc', 'dat', 'loc', 'abl'):
                with self.subTest(code=spec.code, case=case):
                    self.assertTrue(table.get(case), f'{spec.code}.tr.{case} eksik')

    def test_turkish_vowel_harmony_is_respected(self):
        """"İngilizceyi" ama "Almancayı" — ek son ünlüye göre değişir.

        Bu tam olarak dil adını şablona değişken olarak gömmenin neden
        yetmediğini gösteren kural.
        """
        self.assertEqual(L.display_name('en', in_language='tr', case='acc'), 'İngilizceyi')
        self.assertEqual(L.display_name('de', in_language='tr', case='acc'), 'Almancayı')
        self.assertEqual(L.display_name('tr', in_language='tr', case='loc'), 'Türkçede')
        self.assertEqual(L.display_name('fr', in_language='tr', case='loc'), 'Fransızcada')

    def test_missing_case_falls_back_to_nominative(self):
        # İngilizce'de hâl eki yok; 'abl' istenince yalın hâl dönmeli.
        self.assertEqual(L.display_name('de', in_language='en', case='abl'), 'German')

    def test_unknown_display_language_falls_back_to_english(self):
        self.assertEqual(L.display_name('de', in_language='klingon'), 'German')


class PairTests(unittest.TestCase):
    def test_pair_accepts_codes_and_specs(self):
        from_codes = L.pair('en', 'tr')
        from_specs = L.pair(L.ENGLISH, L.TURKISH)
        self.assertEqual(from_codes, from_specs)

    def test_pair_exposes_english_names_for_prompts(self):
        """Promptlara dil ADI gider, kod değil: model için 'de' belirsiz."""
        p = L.pair('de', 'tr')
        self.assertEqual(p.target_name, 'German')
        self.assertEqual(p.native_name, 'Turkish')

    def test_pair_rejects_the_same_language_twice(self):
        with self.assertRaises(ValueError):
            L.pair('en', 'en')

    def test_pair_is_hashable_and_comparable(self):
        self.assertEqual(len({L.pair('en', 'tr'), L.pair('en', 'tr')}), 1)

    def test_str_is_compact_and_directional(self):
        self.assertEqual(str(L.pair('de', 'tr')), 'de->tr')

    def test_course_pairs_never_pair_a_language_with_itself(self):
        for p in L.course_pairs():
            with self.subTest(pair=str(p)):
                self.assertFalse(p.is_mono)

    def test_course_pairs_cover_learnable_times_ui(self):
        expected = {
            (t.code, n.code)
            for t in L.LEARNABLE_LANGUAGES
            for n in L.UI_LANGUAGES
            if t.code != n.code
        }
        self.assertEqual(
            {(p.target_code, p.native_code) for p in L.course_pairs()}, expected,
        )


class RolloutStateTests(unittest.TestCase):
    """Bugünün yayın durumu — faz ilerledikçe bilinçli olarak güncellenir."""

    def test_all_four_languages_are_learnable_today(self):
        """Dört hedef dilin de kelime hazinesi ve gramer içeriği üretildi.

        Bu test bir kısıt değil, bir kayıt: sicilde bir dili `is_learnable`
        yapıp içeriğini üretmeyi atlamak sessizce boş sayfa yayınlamak olurdu.
        Tersi de geçerli — içerik üretilip sicil güncellenmezse kimse göremez.
        """
        self.assertEqual(L.LEARNABLE_CODES, ('tr', 'en', 'fr', 'de'))

    def test_all_four_are_live_ui_languages(self):
        """`fr`/`de` 2026-10-24'te açıldı: katalogları 675/675 dolduğunda.

        Sıra tersine çevrilemez — msgid'ler Türkçe olduğu için eksik katalogla
        açılan bir dil kullanıcıya yarı Türkçe sayfa gösterir. Kapı
        `manage.py check_translations`.
        """
        self.assertEqual(L.UI_CODES, ('tr', 'en', 'fr', 'de'))
