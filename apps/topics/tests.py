"""Konu anlatımı ayrıştırıcısı ve dil fallback zinciri.

Eski testler sezgisel başlık tanımayı doğruluyordu (ALL-CAPS satır, `?`/`:` ile
biten satır, `' vs '` içeren satır). O sezgi silindi: dilden bağımsız
olamıyordu ve ölçümde mevcut veride bile Türkçe metinlerin %30'u, İngilizce
metinlerin %24'ü başlık tanınmadığı için gövdeye düşüyordu. Yerine `##`
markdown konvansiyonu geldi — büyük-küçük harf, alfabe ve aksan önemsiz.
"""

from django.test import TestCase

from .markup import parse_sections
from .models import Topic, TopicExplanation


def make_topic(slug='present-perfect', language='en', name='Present Perfect',
               explanations=None):
    topic = Topic.objects.create(language=language, name=name, slug=slug, order=0)
    for code, body in (explanations or {}).items():
        TopicExplanation.objects.create(topic=topic, language=code, body=body)
    return topic


class ParseSectionsTests(TestCase):
    def test_heading_opens_a_section(self):
        sections = parse_sections('## NE ZAMAN KULLANILIR\n- Bir\n- İki')
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, 'NE ZAMAN KULLANILIR')
        self.assertEqual(sections[0].items, ['Bir', 'İki'])
        self.assertFalse(sections[0].prose)

    def test_multiple_headings_make_multiple_sections(self):
        sections = parse_sections(
            '## YAPI\n- have/has + V3\n\n## İPUÇLARI\n- Zaman zarfı kullanma'
        )
        self.assertEqual([s.title for s in sections], ['YAPI', 'İPUÇLARI'])

    def test_bullet_markers_are_all_stripped(self):
        """Eski kod `stripped[1:]` ile TEK karakter kesiyordu; çok baytlı
        işaretlerde (– —) metnin başı bozuluyordu."""
        for marker in ('-', '*', '+', '•', '‣', '–', '—'):
            with self.subTest(marker=marker):
                sections = parse_sections(f'## X\n{marker} içerik')
                self.assertEqual(sections[0].items, ['içerik'])

    def test_numbered_items_are_recognised(self):
        sections = parse_sections('## X\n1. birinci\n2) ikinci')
        self.assertEqual(sections[0].items, ['birinci', 'ikinci'])

    def test_untitled_block_is_prose_with_no_title(self):
        """Python ARTIK GÖRÜNÜR METİN ÜRETMİYOR.

        Eskiden başlıksız bloğa `'Özet'` yazılıyor ve şablon bunu
        `section.title == 'Özet'` ile karşılaştırıyordu — o metin çevrilse
        şablon mantığı sessizce bozulacaktı.
        """
        sections = parse_sections('Düz bir paragraf.\nİkinci satır.')
        self.assertEqual(len(sections), 1)
        self.assertIsNone(sections[0].title)
        self.assertTrue(sections[0].prose)

    def test_blank_line_splits_untitled_blocks(self):
        sections = parse_sections('Birinci blok.\n\nİkinci blok.')
        self.assertEqual(len(sections), 2)
        self.assertTrue(all(s.title is None for s in sections))

    def test_blank_line_does_not_drop_a_heading(self):
        sections = parse_sections('## YAPI\n- bir\n\n- iki')
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, 'YAPI')
        self.assertEqual(sections[0].items, ['bir', 'iki'])

    def test_empty_text_yields_nothing(self):
        self.assertEqual(parse_sections(''), [])
        self.assertEqual(parse_sections(None), [])
        self.assertEqual(parse_sections('   \n\n  '), [])

    def test_german_sharp_s_heading_survives(self):
        """`'ß'.upper() == 'SS'` olduğu için eski ALL-CAPS sezgisi bu başlığı
        tanıyamıyordu."""
        sections = parse_sections('## GROSSSCHREIBUNG UND ß\n- Regel')
        self.assertEqual(sections[0].title, 'GROSSSCHREIBUNG UND ß')

    def test_french_accented_heading_survives(self):
        sections = parse_sections("## QUAND L'UTILISER\n- Règle")
        self.assertEqual(sections[0].title, "QUAND L'UTILISER")

    def test_title_case_heading_survives(self):
        """Fransızca ve Almanca'da doğal olan Title Case eski sezgiyi tamamen
        çökertiyordu (`candidate.upper() == candidate` tutmuyor)."""
        sections = parse_sections('## Quand l’utiliser\n- Règle')
        self.assertEqual(sections[0].title, 'Quand l’utiliser')

    def test_parser_never_emits_a_visible_label(self):
        """Hiçbir girdi için Python tarafı kullanıcıya metin uydurmuyor."""
        for text in ('Düz metin', '## X\n- y', 'A\n\nB', '- madde'):
            with self.subTest(text=text):
                for section in parse_sections(text):
                    self.assertNotEqual(section.title, 'Özet')


class ExplanationFallbackTests(TestCase):
    def test_requested_language_wins(self):
        topic = make_topic(explanations={'tr': 'Türkçe metin', 'en': 'English text'})
        body, code = topic.explanation_for('tr')
        self.assertEqual(body, 'Türkçe metin')
        self.assertEqual(code, 'tr')

    def test_missing_language_falls_back_to_english(self):
        """Eski sürüm `fr`/`de` istendiğinde sessizce Türkçe gövdeyi döndürüp
        `'tr'` diyordu; `inLanguage` ve `lang` attribute'ları yanlış basılıyordu."""
        topic = make_topic(explanations={'tr': 'Türkçe', 'en': 'English'})
        body, code = topic.explanation_for('fr')
        self.assertEqual(body, 'English')
        self.assertEqual(code, 'en')

    def test_returned_code_is_always_the_real_language(self):
        topic = make_topic(explanations={'tr': 'Yalnızca Türkçe'})
        body, code = topic.explanation_for('de')
        self.assertEqual(body, 'Yalnızca Türkçe')
        self.assertEqual(code, 'tr')

    def test_no_explanation_returns_empty_pair(self):
        topic = make_topic()
        self.assertEqual(topic.explanation_for('tr'), ('', ''))

    def test_empty_body_is_skipped_in_the_chain(self):
        topic = make_topic(explanations={'tr': '   ', 'en': 'English'})
        body, code = topic.explanation_for('tr')
        self.assertEqual(body, 'English')
        self.assertEqual(code, 'en')

    def test_sections_read_the_requested_language(self):
        """Eski `explanation_sections()` HER ZAMAN Türkçe gövdeyi okuyordu —
        `/en/` sayfasında başlıklar Türkçe'den geliyordu."""
        topic = make_topic(explanations={
            'tr': '## TÜRKÇE BAŞLIK\n- madde',
            'en': '## ENGLISH HEADING\n- item',
        })
        self.assertEqual(topic.explanation_sections('en')[0].title, 'ENGLISH HEADING')
        self.assertEqual(topic.explanation_sections('tr')[0].title, 'TÜRKÇE BAŞLIK')


class TopicLanguageTests(TestCase):
    def test_same_slug_can_exist_in_two_languages(self):
        """Konu listesi hedef dile özgü; `slug` tek başına tekil DEĞİL."""
        make_topic(slug='present-simple', language='en', name='Present Simple')
        make_topic(slug='present-simple', language='de', name='Präsens')
        self.assertEqual(Topic.objects.filter(slug='present-simple').count(), 2)

    def test_duplicate_slug_in_one_language_is_rejected(self):
        from django.db import IntegrityError, transaction

        make_topic(slug='present-simple', language='en')
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_topic(slug='present-simple', language='en')
