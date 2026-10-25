"""Cevap normalizasyonu ve karşılaştırması.

Bu kod `views.py` içindeyken hiç testi yoktu ve iki dil varsayımı taşıyordu:
harfler elle whitelist'lenmişti (`ğüşıöçİĞÜŞÖÇ`), yani Fransızca `œ` ve
Almanca `ß` listede yoktu; ayrıca Fransızca'nın tipografik kesme işareti
(`’`, U+2019) atıldığı için `l’homme` yazan kullanıcının cevabı yanlış
sayılıyordu.
"""

import unittest

from .answers import check_answer, fold_accents, normalize


class NormalizeTests(unittest.TestCase):
    def test_case_and_whitespace_are_folded(self):
        self.assertEqual(normalize('  Book   Shop '), 'book shop')

    def test_empty_input_is_safe(self):
        self.assertEqual(normalize(''), '')
        self.assertEqual(normalize(None), '')

    def test_punctuation_is_dropped_but_apostrophe_and_hyphen_survive(self):
        self.assertEqual(normalize('Well-known, indeed!'), 'well-known indeed')
        self.assertEqual(normalize("don't"), "don't")

    def test_typographic_apostrophe_becomes_straight(self):
        """Fransızca'da `’` yaygın; eski whitelist onu atıyordu."""
        self.assertEqual(normalize('l’homme'), normalize("l'homme"))

    def test_non_breaking_space_is_a_normal_space(self):
        self.assertEqual(normalize('je suis'), 'je suis')

    def test_dashes_are_unified(self):
        self.assertEqual(normalize('bien–sûr'), normalize('bien-sûr'))

    def test_turkish_letters_survive_without_a_whitelist(self):
        """`str.isalnum()` Unicode farkında: hiçbir dilde harf listesi yok."""
        # `ı` -> `i`: noktalı/noktasız I bilinçli olarak birleştiriliyor
        # (aşağıdaki test). Diğer Türkçe harfler korunuyor.
        self.assertEqual(normalize('Çağrı Şöyle'), 'çağri şöyle')

    def test_french_letters_survive(self):
        self.assertEqual(normalize('Cœur Élégant'), 'cœur élégant')

    def test_german_sharp_s_folds_to_ss(self):
        """`casefold()` kullanılıyor, `lower()` değil: `'ß'.lower()` hâlâ `'ß'`."""
        self.assertEqual(normalize('Straße'), normalize('STRASSE'))

    def test_dotted_and_dotless_i_are_unified(self):
        """Türkçe klavye düzeni ve otomatik düzeltme bunu kolayca değiştiriyor;
        quiz cevabında yanlış-negatif üretmemeli."""
        self.assertEqual(normalize('İstanbul'), normalize('istanbul'))
        self.assertEqual(normalize('ılık'), normalize('ilik'))


class FoldAccentsTests(unittest.TestCase):
    def test_diacritics_are_removed(self):
        self.assertEqual(fold_accents('élégant'), 'elegant')
        self.assertEqual(fold_accents('für'), 'fur')
        # `ı` (U+0131) ayrı bir harf, birleşen diakritiği yok — NFKD onu
        # değiştirmiyor. `normalize` onu zaten `i`ye eşliyor.
        self.assertEqual(fold_accents('çağrı'), 'cagrı')

    def test_plain_text_is_unchanged(self):
        self.assertEqual(fold_accents('book'), 'book')


class CheckAnswerTests(unittest.TestCase):
    def test_exact_match(self):
        verdict = check_answer('kitap', 'kitap')
        self.assertTrue(verdict.is_correct)
        self.assertFalse(verdict.diacritics_only)

    def test_case_insensitive(self):
        self.assertTrue(check_answer('KİTAP', 'kitap').is_correct)

    def test_empty_answer_is_wrong(self):
        self.assertFalse(check_answer('', 'kitap').is_correct)
        self.assertFalse(check_answer('   ', 'kitap').is_correct)

    def test_wrong_answer_is_wrong(self):
        self.assertFalse(check_answer('kalem', 'kitap').is_correct)

    def test_slash_alternatives_are_accepted(self):
        for given in ('colour', 'color'):
            with self.subTest(given=given):
                self.assertTrue(check_answer(given, 'colour / color').is_correct)

    def test_whole_string_with_slash_also_matches(self):
        self.assertTrue(check_answer('colour / color', 'colour / color').is_correct)

    def test_missing_diacritics_count_as_correct_but_are_flagged(self):
        """Fransızca ve Almanca'da gerçek bir öğrenme sinyali: cevap kabul
        ediliyor ama kullanıcıya ipucu gösteriliyor."""
        verdict = check_answer('elegant', 'élégant')
        self.assertTrue(verdict.is_correct)
        self.assertTrue(verdict.diacritics_only)

    def test_correct_diacritics_are_not_flagged(self):
        verdict = check_answer('élégant', 'élégant')
        self.assertTrue(verdict.is_correct)
        self.assertFalse(verdict.diacritics_only)

    def test_german_umlaut_folding(self):
        verdict = check_answer('Fur', 'für')
        self.assertTrue(verdict.is_correct)
        self.assertTrue(verdict.diacritics_only)

    def test_diacritic_folding_does_not_make_different_words_equal(self):
        self.assertFalse(check_answer('mur', 'mûre').is_correct)

    def test_french_apostrophe_variants_both_accepted(self):
        for given in ("l'homme", 'l’homme'):
            with self.subTest(given=given):
                self.assertTrue(check_answer(given, "l'homme").is_correct)


class MultipleChoiceNormalizationTests(unittest.TestCase):
    """`normalization.py` artık tam 4 şık varsaymıyor."""

    def _item(self, choices, correct):
        from .normalization import normalize_item
        return normalize_item({
            'question_type': 'multiple_choice',
            'prompt': 'Which one?',
            'choices': choices,
            'correct_answer': correct,
        })

    def test_letter_answer_resolves_with_four_choices(self):
        item = self._item(['alfa', 'beta', 'gama', 'delta'], 'C')
        self.assertEqual(item['correct_answer'], 'gama')

    def test_letter_answer_resolves_with_two_choices(self):
        """Eski `'ABCD'.index` iki şıkta yanlış indeks veriyordu."""
        item = self._item(['doğru', 'yanlış'], 'B')
        self.assertEqual(item['correct_answer'], 'yanlış')

    def test_letter_answer_resolves_with_five_choices(self):
        """Eski kod beşinci şıkta `ValueError` fırlatıyordu."""
        item = self._item(['a', 'b', 'c', 'd', 'e'], 'E')
        self.assertEqual(item['correct_answer'], 'e')

    def test_out_of_range_letter_is_left_alone(self):
        item = self._item(['a', 'b'], 'D')
        self.assertEqual(item['correct_answer'], 'D')

    def test_labelled_choices_are_stripped(self):
        item = self._item(['A. alfa', 'B. beta', 'C. gama'], 'B')
        self.assertEqual(item['choices'], ['alfa', 'beta', 'gama'])
        self.assertEqual(item['correct_answer'], 'beta')

    def test_non_multiple_choice_has_no_choices(self):
        from .normalization import normalize_item
        item = normalize_item({
            'question_type': 'translate_to_native',
            'prompt': 'book',
            'correct_answer': 'kitap',
            'choices': ['a', 'b'],
        })
        self.assertIsNone(item['choices'])
