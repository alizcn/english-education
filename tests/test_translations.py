"""Çeviri kataloglarının çalışma anı davranışı.

Katalog hataları sessizdir: metin çevrilmemiş görünür ama hiçbir yerde hata
çıkmaz. Bu dosya daha önce gerçekten bozuk olan vakaları kilitliyor, böylece
`makemessages` bir daha koşturulduğunda geri gelmiyorlar.
"""

import io
import tempfile
import unittest
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import translation
from django.utils.translation import gettext, pgettext

from services import languages


class ContextualTranslationTests(unittest.TestCase):
    """`pgettext` bağlamları — aynı Türkçe metin iki yerde farklı çevriliyor."""

    def test_quiz_and_interview_status_do_not_share_a_translation(self):
        """`msgctxt "quiz durumu"` katalogda HİÇ YOKTU.

        `apps/quizzes/models.py` `pgettext_lazy('quiz durumu', …)` kullanıyordu
        ama katalog altı ay boyunca yenilenmediği için bu bağlam hiç
        çıkarılmamıştı: İngilizce arayüzde quiz durumları Türkçe kalıyordu.
        """
        with translation.override('en'):
            for msgid, expected in (
                ('Hazırlanıyor', 'Preparing'),
                ('Hazır', 'Ready'),
                ('Başarısız', 'Failed'),
            ):
                with self.subTest(msgid=msgid):
                    self.assertEqual(pgettext('quiz durumu', msgid), expected)
                    self.assertEqual(pgettext('mülakat durumu', msgid), expected)

    def test_contextual_lookup_does_not_leak_to_the_plain_msgid(self):
        """Bağlamlı girdi, bağlamsız aramayı etkilememeli."""
        with translation.override('en'):
            self.assertEqual(gettext('Hazırlanıyor...'), 'Preparing...')


class PlaceholderTranslationTests(unittest.TestCase):
    def test_brace_placeholders_survive_translation(self):
        """`{% trans %}` içindeki literal `%` kalıcı bir çeviri hatasıydı.

        `makemessages` `%(done)s`i `%%(done)s` olarak çıkarıyor, oysa çalışma
        anında arama tek `%` ile yapılıyor — msgid hiç eşleşmiyordu, yani metin
        İngilizce arayüzde de Türkçe kalıyordu. Yer tutucular `{}` kalıbına
        taşındı; bu test o kalıbın çalıştığını ve adların korunduğunu gösteriyor.
        """
        with translation.override('en'):
            out = gettext('{done} / {total} soru hazır...')
        self.assertEqual(out, '{done} / {total} questions ready...')
        self.assertIn('{done}', out)
        self.assertIn('{total}', out)

    def test_named_placeholders_are_preserved(self):
        with translation.override('en'):
            out = gettext('%(count)d kelime eklendi.')
        self.assertIn('%(count)d', out)


class RecoveredTranslationTests(unittest.TestCase):
    """`msgmerge` tarafından yanlış doldurulmuş fuzzy girdiler.

    Fuzzy bayrağı olan bir girdiyi gettext yok sayar; üstelik benzerlik
    eşleşmesi tamamen alakasız bir çeviri kopyalayabiliyor. Gerçek örnekler:
    "Şifre değiştirildi" → "Toggle theme", "Şifreyi sıfırla" →
    "Reset %(level)s" (msgid'de olmayan bir yer tutucuyla!).
    """

    CASES = [
        ('Şifre değiştirildi', 'Password changed'),
        ('Şifreniz başarıyla güncellendi.', 'Your password has been updated successfully.'),
        ('Şifreyi sıfırla', 'Reset password'),
        ('E-posta adresi', 'Email address'),
        ('Giriş sayfasına dön', 'Back to sign in'),
        ('Tamamlandı', 'Completed'),
        ('Devam ediyor', 'In progress'),
        ('Durum', 'Status'),
        ('Detay', 'Details'),
        ('Açıklama', 'Explanation'),
    ]

    def test_recovered_entries_are_translated(self):
        with translation.override('en'):
            for msgid, expected in self.CASES:
                with self.subTest(msgid=msgid):
                    self.assertEqual(gettext(msgid), expected)

    def test_reset_password_carries_no_stray_placeholder(self):
        """Yanlış fuzzy eşleşmesi buraya `%(level)s` sokmuştu."""
        with translation.override('en'):
            self.assertNotIn('%', gettext('Şifreyi sıfırla'))


class StaleCatalogTests(unittest.TestCase):
    """Katalog altı ay donduğu için çıkarılmamış string'ler."""

    CASES = [
        ('Şifremi unuttum', 'Forgot my password'),
        ('Yeni şifre belirle', 'Set a new password'),
        ('Sıfırlama bağlantısı gönder', 'Send reset link'),
        ('E-posta gönderildi', 'Email sent'),
        ('Bu quiz henüz hazır değil.', 'This quiz is not ready yet.'),
        ('Dil seç', 'Choose language'),
    ]

    def test_newly_extracted_strings_are_translated(self):
        with translation.override('en'):
            for msgid, expected in self.CASES:
                with self.subTest(msgid=msgid):
                    self.assertEqual(gettext(msgid), expected)


class TurkishCatalogTests(unittest.TestCase):
    """Kaynakta İngilizce yazılmış msgid'ler Türkçe arayüzde çevrilmeli.

    Türkçe katalog bilinçli olarak no-op (msgid'ler Türkçe), ama kaynakta
    İngilizce yazılmış bir avuç string vardı ve onlar Türkçe arayüzde
    İngilizce görünüyordu.
    """

    CASES = [
        ('User', 'Kullanıcı'),
        ('Assistant', 'Asistan'),
        ('English', 'İngilizce'),
        ('AI Chat', 'AI Sohbet'),
        ('Chat', 'Sohbet'),
        # `"Level up your English. Land the interview."` BU LİSTEDEN ÇIKARILDI:
        # artık çevrilebilir bir string değil, her dilde İngilizce kalan marka
        # sloganı (`accounts/_auth_base.html`). Bir ara `{% lang_name 'en' %}`
        # ile parametreleştirilmişti ve Türkçe arayüzde "Level up your
        # İngilizce." üretiyordu.
    ]

    def test_english_source_strings_are_turkish_in_turkish_ui(self):
        with translation.override('tr'):
            for msgid, expected in self.CASES:
                with self.subTest(msgid=msgid):
                    self.assertEqual(gettext(msgid), expected)

    def test_turkish_source_strings_fall_through_to_the_msgid(self):
        """No-op katalogun çalıştığının kanıtı: boş msgstr msgid'i döndürür."""
        with translation.override('tr'):
            self.assertEqual(gettext('Konular'), 'Konular')

    def test_job_titles_stay_in_english_on_purpose(self):
        """Türk yazılım sektöründe bu unvanlar İngilizce kullanılıyor;
        çevirmek tanınırlığı düşürürdü. Alan adları zaten Türkçe yazılı."""
        with translation.override('tr'):
            self.assertEqual(gettext('Backend Developer'), 'Backend Developer')
            self.assertEqual(gettext('DevOps / SRE'), 'DevOps / SRE')


class CheckTranslationsCommandTests(unittest.TestCase):
    def test_gate_passes_on_the_shipped_catalogs(self):
        """Depodaki kataloglar temiz olmak zorunda — bu testin kendisi kapı."""
        call_command('check_translations', verbosity=0)

    def test_gate_is_strict_about_non_no_op_catalogs(self):
        """`--strict-empty` Türkçe katalogu da zorlar; no-op olduğu için
        başarısız olmalı. Kapının gerçekten bir şey ölçtüğünün kanıtı."""
        with self.assertRaises(CommandError):
            # Komut bulduğu her boş çeviriyi yazıyor; test çıktısını kirletmesin.
            call_command(
                'check_translations', '--strict-empty',
                verbosity=0, stdout=io.StringIO(), stderr=io.StringIO(),
            )

    def test_status_report_does_not_count_fuzzy_as_translated(self):
        """`translate_catalog --status` fuzzy'yi DOLU saymamalı.

        Ölçülmüş yanılgı: rapor yalnızca `msgstr` boş mu diye bakıyordu ve
        `makemessages`in benzerlik eşleştirmesiyle kopyaladığı bayat
        çevirileri "çevrili" gösteriyordu. gettext fuzzy girdiyi çalışma
        anında YOK SAYIYOR, yani kullanıcı Türkçe msgid'i görüyor — rapor
        %100 derken sayfa yarı Türkçeydi.
        """
        import polib

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fr' / 'LC_MESSAGES'
            path.mkdir(parents=True)
            catalog = polib.POFile()
            catalog.append(polib.POEntry(msgid='Temiz', msgstr='Propre'))
            catalog.append(polib.POEntry(msgid='Bayat', msgstr='Rassis',
                                         flags=['fuzzy']))
            catalog.append(polib.POEntry(msgid='Boş', msgstr=''))
            catalog.save(str(path / 'django.po'))

            out = io.StringIO()
            with override_settings(LOCALE_PATHS=[tmp]):
                call_command('translate_catalog', '--lang', 'fr', '--status',
                             stdout=out)
            line = out.getvalue()
        # Üç girdiden yalnızca biri kullanılabilir: fuzzy ve boş sayılmıyor.
        self.assertIn('1/3 kullanılabilir', line)
        self.assertIn('1 fuzzy', line)

    def test_every_live_ui_language_has_a_catalog(self):
        from pathlib import Path

        from django.conf import settings

        for spec in languages.UI_LANGUAGES:
            with self.subTest(code=spec.code):
                path = (Path(settings.LOCALE_PATHS[0]) / spec.code
                        / 'LC_MESSAGES' / 'django.po')
                self.assertTrue(path.exists(), f'{spec.code}: {path} yok')
