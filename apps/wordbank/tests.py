"""Kelime hazinesi: yükleyici ve soru seçimi testleri.

Bu dosya çok dilli dönüşümün emniyet ağı olarak yazıldı. İki işi var:

1. Bugün doğru çalışan davranışı kilitlemek (seviye istatistikleri, görülmemiş
   kelime seçimi, çeldirici üretimi, ilerleme kaydı).
2. Bugün YANLIŞ olan davranışı belgelemek: `load_wordbank` kayıtları
   `(level, english, part_of_speech)` anahtarıyla eşlediği ve `part_of_speech`
   kaynak veride %90 boş olduğu için, aynı yazımın farklı anlamları tek satıra
   çöküyor ve JSON'daki 6.218 kaydın 55'i veritabanına hiç girmiyor. İlgili test
   `expectedFailure` ile işaretli — dönüşümün dördüncü fazında yükleyici `rank`
   anahtarına geçtiğinde bu test kendiliğinden geçmeye başlayacak ve işareti
   kaldırmak gerekecek.
"""

import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from . import services
from .models import BankProgress, BankWord, BankWordTranslation


EN, TR = 'en', 'tr'


def make_word(level='A1', rank=1, term='book', meaning='kitap', pos='noun',
              language=EN, native=TR, example='', example_translation='', **kw):
    """Başlık kelime + (varsa) çevirisi.

    `meaning` boş verilirse çeviri hiç yaratılmıyor — "anlamı olmayan kelime"
    durumunu kurmanın yolu bu (eskiden `meaning=''` idi).
    """
    word = BankWord.objects.create(
        language=language, level=level, rank=rank, term=term,
        part_of_speech=pos, example=example, **kw,
    )
    if meaning:
        BankWordTranslation.objects.create(
            word=word, language=native, meaning=meaning,
            example_translation=example_translation,
        )
    return word


class LevelStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')

    def test_empty_level_reports_zeroes(self):
        stats = services.level_stats(self.user, 'A1', target_language=EN, native_language=TR)
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['percent'], 0)

    def test_words_without_translation_are_not_counted(self):
        make_word(rank=1, term='book', meaning='kitap')
        make_word(rank=2, term='pen', meaning='')
        self.assertEqual(services.level_stats(self.user, 'A1', target_language=EN, native_language=TR)['total'], 1)

    def test_mastered_drives_percent(self):
        a = make_word(rank=1, term='book', meaning='kitap')
        make_word(rank=2, term='pen', meaning='kalem')
        services.record_answer(self.user, a, True)

        stats = services.level_stats(self.user, 'A1', target_language=EN, native_language=TR)
        self.assertEqual(stats['mastered'], 1)
        self.assertEqual(stats['answered'], 1)
        self.assertEqual(stats['unseen'], 1)
        self.assertEqual(stats['percent'], 50)

    def test_levels_are_isolated(self):
        make_word(level='A1', rank=1, term='book', meaning='kitap')
        make_word(level='B2', rank=1, term='ubiquitous', meaning='her yerde')
        self.assertEqual(services.level_stats(self.user, 'A1', target_language=EN, native_language=TR)['total'], 1)
        self.assertEqual(services.level_stats(self.user, 'B2', target_language=EN, native_language=TR)['total'], 1)


class PickNextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')

    def test_unseen_words_come_in_rank_order(self):
        make_word(rank=5, term='five', meaning='beş')
        make_word(rank=2, term='two', meaning='iki')
        word, is_retry = services.pick_next(self.user, 'A1', target_language=EN, native_language=TR)
        self.assertEqual(word.term, 'two')
        self.assertFalse(is_retry)

    def test_untranslated_words_are_skipped(self):
        make_word(rank=1, term='empty', meaning='')
        make_word(rank=2, term='two', meaning='iki')
        word, _ = services.pick_next(self.user, 'A1', target_language=EN, native_language=TR)
        self.assertEqual(word.term, 'two')

    def test_completed_level_returns_none(self):
        word = make_word(rank=1, term='book', meaning='kitap')
        services.record_answer(self.user, word, True)
        self.assertEqual(services.pick_next(self.user, 'A1', target_language=EN, native_language=TR), (None, False))

    def test_wrong_answer_comes_back_as_retry(self):
        word = make_word(rank=1, term='book', meaning='kitap')
        services.record_answer(self.user, word, False)
        picked, is_retry = services.pick_next(self.user, 'A1', target_language=EN, native_language=TR)
        self.assertEqual(picked.pk, word.pk)
        self.assertTrue(is_retry)

    def test_progress_is_per_user(self):
        other = User.objects.create_user('veli', password='x')
        word = make_word(rank=1, term='book', meaning='kitap')
        services.record_answer(self.user, word, True)

        self.assertEqual(services.pick_next(self.user, 'A1', target_language=EN, native_language=TR), (None, False))
        picked, _ = services.pick_next(other, 'A1', target_language=EN, native_language=TR)
        self.assertEqual(picked.pk, word.pk)


class BuildQuestionTests(TestCase):
    def test_correct_answer_is_always_present(self):
        word = make_word(rank=1, term='book', meaning='kitap')
        for i in range(2, 8):
            make_word(rank=i, term=f'w{i}', meaning=f'anlam{i}')
        correct, options = services.build_question(word, native_language=TR)
        self.assertEqual(correct.meaning, 'kitap')
        self.assertIn(correct, options)
        self.assertEqual(len(options), 4)

    def test_options_are_translation_objects_not_strings(self):
        """Cevap kimlikle karşılaştırılıyor: aynı metne sahip iki çeviri
        şıkları teke indirmemeli."""
        word = make_word(rank=1, term='book', meaning='kitap')
        make_word(rank=2, term='tome', meaning='kitap')
        make_word(rank=3, term='pen', meaning='kalem')
        correct, options = services.build_question(word, native_language=TR)
        self.assertTrue(all(isinstance(o, BankWordTranslation) for o in options))
        # Doğru cevabın metni çeldiriciler arasında tekrar etmemeli.
        self.assertEqual(
            sum(1 for o in options if o.meaning == correct.meaning), 1,
        )

    def test_fewer_candidates_yield_shorter_option_list(self):
        word = make_word(rank=1, term='book', meaning='kitap')
        make_word(rank=2, term='pen', meaning='kalem')
        _correct, options = services.build_question(word, native_language=TR)
        self.assertEqual(sorted(o.meaning for o in options), ['kalem', 'kitap'])

    def test_distractors_come_from_the_same_level(self):
        word = make_word(level='A1', rank=1, term='book', meaning='kitap')
        make_word(level='C1', rank=1, term='tome', meaning='cilt')
        _correct, options = services.build_question(word, native_language=TR)
        self.assertNotIn('cilt', [o.meaning for o in options])

    def test_distractors_come_from_the_same_target_language(self):
        word = make_word(language='en', rank=1, term='book', meaning='kitap')
        make_word(language='de', rank=1, term='Buch', meaning='kitap(de)')
        _correct, options = services.build_question(word, native_language=TR)
        self.assertNotIn('kitap(de)', [o.meaning for o in options])

    def test_missing_translation_yields_no_question(self):
        word = make_word(rank=1, term='book', meaning='')
        correct, options = services.build_question(word, native_language=TR)
        self.assertIsNone(correct)
        self.assertEqual(options, [])


class RecordAnswerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ali', password='x')
        self.word = make_word(rank=1, term='book', meaning='kitap')

    def test_correct_answer_masters_the_word(self):
        progress = services.record_answer(self.user, self.word, True)
        self.assertTrue(progress.mastered)
        self.assertEqual(progress.correct_count, 1)
        self.assertEqual(progress.wrong_count, 0)

    def test_wrong_answer_only_counts(self):
        progress = services.record_answer(self.user, self.word, False)
        self.assertFalse(progress.mastered)
        self.assertEqual(progress.wrong_count, 1)

    def test_recovering_after_a_mistake_masters_the_word(self):
        services.record_answer(self.user, self.word, False)
        progress = services.record_answer(self.user, self.word, True)
        self.assertTrue(progress.mastered)
        self.assertEqual(progress.wrong_count, 1)
        self.assertEqual(progress.correct_count, 1)
        self.assertEqual(BankProgress.objects.count(), 1)


class LoadWordbankTests(TestCase):
    """`load_wordbank` komutunun dosya→DB sözleşmesi."""

    def _run(self, items_by_level, target='en', **opts):
        """Geçici bir veri dizini kurup komutu ona yönlendirir."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data_dir = Path(tmp.name)
        lang_dir = data_dir / target
        lang_dir.mkdir()
        for level, items in items_by_level.items():
            (lang_dir / f'{level.lower()}.json').write_text(
                json.dumps(items, ensure_ascii=False), encoding='utf-8',
            )
        # Komut çıktısı test akışını kirletmesin.
        call_command(
            'load_wordbank', data_dir=str(data_dir), target=target, verbosity=0,
            stdout=io.StringIO(), stderr=io.StringIO(), **opts
        )
        return data_dir

    @staticmethod
    def record(rank, term, meaning, pos='', example='', example_translation='',
               native='tr'):
        return {
            'rank': rank, 'term': term, 'part_of_speech': pos, 'example': example,
            'translations': {
                native: {'meaning': meaning,
                         'example_translation': example_translation},
            },
        }

    def test_loads_entries(self):
        self._run({'A1': [
            self.record(1, 'book', 'kitap', pos='noun',
                        example='A book.', example_translation='Bir kitap.'),
            self.record(2, 'pen', 'kalem', pos='noun'),
        ]})
        self.assertEqual(BankWord.objects.count(), 2)
        book = BankWord.objects.get(term='book')
        self.assertEqual(book.example, 'A book.')
        translation = book.translation_for('tr')
        self.assertEqual(translation.meaning, 'kitap')
        self.assertEqual(translation.example_translation, 'Bir kitap.')

    def test_entries_without_translation_are_skipped(self):
        self._run({'A1': [
            self.record(1, 'book', 'kitap'),
            self.record(2, 'pen', ''),      # anlam boş
            self.record(3, '', 'kalem'),    # terim boş
        ]})
        self.assertEqual(BankWord.objects.count(), 1)

    def test_running_twice_does_not_duplicate(self):
        items = {'A1': [self.record(1, 'book', 'kitap', pos='noun')]}
        self._run(items)
        self._run(items)
        self.assertEqual(BankWord.objects.count(), 1)
        self.assertEqual(BankWordTranslation.objects.count(), 1)

    def test_reset_clears_previous_rows(self):
        make_word(rank=99, term='stale', meaning='bayat')
        self._run({'A1': [self.record(1, 'book', 'kitap', pos='noun')]}, reset=True)
        self.assertEqual(BankWord.objects.count(), 1)
        self.assertFalse(BankWord.objects.filter(term='stale').exists())

    def test_homographs_are_kept_as_separate_rows(self):
        """Aynı yazımın farklı anlamları ayrı satır.

        Eski yükleyici `(level, english, part_of_speech)` ile eşleşiyordu ve
        `part_of_speech` kaynak veride %90 boş olduğu için `about`
        ("yaklaşık") ile `about` ("hakkında") tek satıra çöküyordu: gerçek
        veride 6.218 kaydın 55'i veritabanına hiç girmiyordu. Anahtar artık
        `(language, level, rank)`.
        """
        self._run({'A1': [
            self.record(2, 'about', 'yaklaşık'),
            self.record(3, 'about', 'hakkında'),
        ]})
        rows = BankWord.objects.filter(term='about').order_by('rank')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(
            [r.translation_for('tr').meaning for r in rows],
            ['yaklaşık', 'hakkında'],
        )

    def test_existing_rows_pick_up_new_translations(self):
        """Dosyadaki güncel çeviri mevcut satıra yazılmalı.

        Eski yükleyici `get_or_create(..., defaults=...)` kullanıyordu: satır
        varsa `defaults` hiç uygulanmıyor, yani bir çeviriyi düzeltip yeniden
        yüklemek sessizce hiçbir şey yapmıyordu.
        """
        self._run({'A1': [self.record(1, 'book', 'yanlış', pos='noun')]})
        self._run({'A1': [self.record(1, 'book', 'kitap', pos='noun')]})
        word = BankWord.objects.get(term='book')
        self.assertEqual(word.translation_for('tr').meaning, 'kitap')

    def test_duplicate_rank_in_one_file_is_reported(self):
        """`(language, level, rank)` tekil; dosya bunu ihlal ederse hata."""
        with self.assertRaises(CommandError):
            self._run({'A1': [
                self.record(1, 'book', 'kitap'),
                self.record(1, 'pen', 'kalem'),
            ]})

    def test_check_reports_difference_without_writing(self):
        make_word(rank=1, term='book', meaning='kitap')
        with self.assertRaises(CommandError):
            self._run({'A1': [
                self.record(1, 'book', 'kitap'),
                self.record(2, 'pen', 'kalem'),
            ]}, check=True)
        # --check yazmıyor.
        self.assertEqual(BankWord.objects.count(), 1)

    def test_prune_removes_rows_missing_from_the_file(self):
        self._run({'A1': [
            self.record(1, 'book', 'kitap'),
            self.record(2, 'pen', 'kalem'),
        ]})
        self._run({'A1': [self.record(1, 'book', 'kitap')]}, prune=True)
        self.assertEqual(BankWord.objects.count(), 1)
        self.assertFalse(BankWord.objects.filter(term='pen').exists())

    def test_multiple_native_languages_on_one_term(self):
        """(hedef × ana dil) matrisinin yükleyici tarafı."""
        self._run({'A1': [{
            'rank': 1, 'term': 'book', 'part_of_speech': 'noun',
            'example': 'A book.',
            'translations': {
                'tr': {'meaning': 'kitap', 'example_translation': 'Bir kitap.'},
                'fr': {'meaning': 'livre', 'example_translation': 'Un livre.'},
            },
        }]})
        word = BankWord.objects.get(term='book')
        self.assertEqual(word.translations.count(), 2)
        self.assertEqual(word.translation_for('tr').meaning, 'kitap')
        self.assertEqual(word.translation_for('fr').meaning, 'livre')

    def test_short_translation_form_is_accepted(self):
        """{"tr": "kitap"} kısa biçimi de okunuyor."""
        self._run({'A1': [{
            'rank': 1, 'term': 'book', 'translations': {'tr': 'kitap'},
        }]})
        self.assertEqual(
            BankWord.objects.get(term='book').translation_for('tr').meaning, 'kitap',
        )

    def test_legacy_flat_record_is_still_read(self):
        """Eski anahtarlar (english/turkish/example_en/example_tr) okunmaya
        devam ediyor: dosyalar dönüştürülürken geçiş kolaylığı."""
        self._run({'A1': [{
            'rank': 1, 'english': 'book', 'turkish': 'kitap',
            'part_of_speech': 'noun', 'example_en': 'A book.',
            'example_tr': 'Bir kitap.',
        }]})
        word = BankWord.objects.get(term='book')
        self.assertEqual(word.example, 'A book.')
        self.assertEqual(word.translation_for('tr').meaning, 'kitap')

    def test_target_language_is_recorded(self):
        self._run({'A1': [self.record(1, 'Buch', 'kitap')]}, target='de')
        self.assertEqual(BankWord.objects.get(term='Buch').language, 'de')


class ShippedDataTests(TestCase):
    """Repoyla gelen JSON dosyalarının sözleşmesi.

    Yeni diller bu hattan geçecek; dosya biçimi bozulursa burada görünür.
    """

    DATA_DIR = Path(__file__).resolve().parent / 'data'
    TARGET = 'en'
    LEVELS = ['a1', 'a2', 'b1', 'b2', 'c1', 'c2']

    def _load(self, level):
        path = self.DATA_DIR / self.TARGET / f'{level}.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def test_every_level_file_exists_and_is_a_list(self):
        for level in self.LEVELS:
            with self.subTest(level=level):
                self.assertIsInstance(self._load(level), list)

    def test_required_fields_are_present_and_non_empty(self):
        for level in self.LEVELS:
            for item in self._load(level):
                self.assertIsInstance(item.get('rank'), int, f'{level}: {item}')
                self.assertTrue((item.get('term') or '').strip(), f'{level}: {item}')
                translations = item.get('translations') or {}
                self.assertTrue(translations, f'{level}: çevirisiz kayıt {item}')
                for code, entry in translations.items():
                    self.assertTrue(
                        (entry.get('meaning') or '').strip(),
                        f'{level}/{code}: boş anlam {item}',
                    )

    def test_rank_is_unique_within_a_level(self):
        """`(language, level, rank)` kısıtının ön koşulu."""
        for level in self.LEVELS:
            with self.subTest(level=level):
                ranks = [item['rank'] for item in self._load(level)]
                self.assertEqual(len(ranks), len(set(ranks)))

    def test_field_lengths_fit_the_model(self):
        """Taşan metin arayüzü bozuyor; üretim hattının kapısı burada."""
        limits = {'term': 120, 'part_of_speech': 40, 'example': 500}
        for level in self.LEVELS:
            for item in self._load(level):
                for field, limit in limits.items():
                    value = item.get(field) or ''
                    with self.subTest(level=level, field=field, term=item.get('term')):
                        self.assertLessEqual(len(value), limit)
                for code, entry in (item.get('translations') or {}).items():
                    with self.subTest(level=level, code=code):
                        self.assertLessEqual(len(entry.get('meaning') or ''), 400)
                        self.assertLessEqual(
                            len(entry.get('example_translation') or ''), 500,
                        )

    def test_shipped_data_holds_every_entry(self):
        """Dosyalardaki toplam kayıt sayısı sabitlenmiş.

        Eski yükleyici `(level, english, part_of_speech)` anahtarı yüzünden
        bunun 6.163'ünü içe alıyordu; 55 kayıt sessizce kayboluyordu. Yeni
        anahtar `(language, level, rank)` ve `rank` dosya içinde tekil, yani
        tüm kayıtlar veritabanına giriyor.
        """
        total = sum(len(self._load(level)) for level in self.LEVELS)
        self.assertEqual(total, 6466)  # en/C2 genişledi: 498 (eski 250 + 248 yeni)

    def test_loading_the_shipped_data_keeps_every_entry(self):
        """Dosya sayısı = DB satır sayısı. Eski yükleyicide bu tutmuyordu."""
        call_command(
            'load_wordbank', target=self.TARGET, verbosity=0,
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
        for level in self.LEVELS:
            with self.subTest(level=level):
                self.assertEqual(
                    BankWord.objects.filter(
                        language=self.TARGET, level=level.upper(),
                    ).count(),
                    len(self._load(level)),
                )
        self.assertEqual(BankWord.objects.count(), 6466)

    def test_homographs_survive_the_shipped_load(self):
        """A1'deki `about` iki ayrı anlamla duruyor mu — gerçek veri üzerinde."""
        call_command(
            'load_wordbank', target=self.TARGET, level='A1', verbosity=0,
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
        meanings = [
            w.translation_for('tr').meaning
            for w in BankWord.objects.filter(
                language='en', level='A1', term='about',
            ).order_by('rank')
        ]
        self.assertEqual(len(meanings), 2, meanings)
