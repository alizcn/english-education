from django.test import TestCase

from .models import Topic


class TopicExplanationParsingTests(TestCase):
    def test_explanation_sections_group_titles_and_bullets(self):
        topic = Topic.objects.create(
            name='Present Perfect',
            slug='present-perfect',
            explanation=(
                'NE ZAMAN KULLANILIR?\n'
                '• Geçmişte belirsiz yaşanan deneyim\n\n'
                'YAPI\n'
                '• Özne + have/has + V3\n'
                '• I have eaten.'
            ),
        )

        sections = topic.explanation_sections()

        self.assertEqual(sections[0]['title'], 'NE ZAMAN KULLANILIR?')
        self.assertIn('deneyim', sections[0]['items'][0])
        self.assertEqual(sections[1]['title'], 'YAPI')
        self.assertIn('have/has', sections[1]['items'][0])

    def test_explanation_sections_keep_keyword_list_as_body_not_title(self):
        topic = Topic.objects.create(
            name='Present Perfect',
            slug='present-perfect-keywords',
            explanation=(
                'ANAHTAR KELİMELER\n'
                'just, already, yet, ever, never, since, for\n\n'
                'BEEN vs GONE\n'
                '• have/has BEEN to = gidip gelmiş\n'
                '• have/has GONE to = gitmiş'
            ),
        )

        sections = topic.explanation_sections()

        self.assertEqual(sections[0]['title'], 'ANAHTAR KELİMELER')
        self.assertIn('just', sections[0]['items'][0])
        self.assertEqual(sections[1]['title'], 'BEEN vs GONE')
        self.assertIn('gelmiş', sections[1]['items'][0])
