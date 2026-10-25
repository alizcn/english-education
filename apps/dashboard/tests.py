"""Landing yüzeyi: hedef dil başına şablon + SSS'nin tek kaynaklılığı.

İki şey test altında:

* **Öneksiz `/` İngilizce landing'i render ediyor.** Pazarlama metni hedef dil
  başına ayrı şablona taşındı (`templates/dashboard/landing/`); yanlış şablona
  bağlanmak en çok trafik alan sayfayı sessizce boşaltırdı, çünkü bloklarda
  varsayılan metin yok.
* **JSON-LD ile görünür SSS aynı metni taşıyor.** Eskiden iki liste elle
  kopyalanmıştı ve ayrışmıştı (bir cevapta fazladan cümle, bazı msgid'lerde
  HTML entity). Artık ikisi de `apps/dashboard/faq.py`den dönüyor; bu test
  ayrışmanın geri gelmediğini gösteriyor.
"""

import json
import re

from django.test import TestCase
from django.urls import reverse

from apps.dashboard import faq
from services import languages

_JSONLD = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S,
)


def _faq_schema(html):
    """Sayfadaki `FAQPage` bloğunu döndürür.

    Sayfada birden fazla JSON-LD bloğu var (`_jsonld_site.html` site
    bilgisini yazıyor); `@type` ile ayırt etmek şart.
    """
    for block in _JSONLD.findall(html):
        payload = json.loads(block)
        if payload.get('@type') == 'FAQPage':
            return payload
    return None


class LandingTests(TestCase):
    def test_root_renders_the_generic_multi_language_landing(self):
        """`/` PLATFORMU anlatıyor, tek bir dili değil.

        Bir ara İngilizce landing'iydi; ürün dört dil öğretirken sayfanın
        yalnızca İngilizce'den söz etmesi yanlış izlenim veriyordu. Her hedef
        dilin kendi sayfası ayrı (`/learn-english/`, `/learn-german/`, …).
        """
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'dashboard/landing/index.html')

    def test_every_learnable_language_is_linked_from_the_root(self):
        """Ziyaretçi dört programı da `/` üzerinden görebilmeli."""
        html = self.client.get('/').content.decode()
        for spec in languages.LEARNABLE_LANGUAGES:
            with self.subTest(code=spec.code):
                self.assertIn(f'/learn-{spec.seo_stem}/', html)

    def test_every_prose_block_is_filled(self):
        """`_base.html` bloklarında varsayılan metin yok.

        Boş bir blok görünür bir boşluk bırakıyor — bu da eksik çeviriyi
        gözden kaçırmamak için bilinçli bir seçim. Burada İngilizce sayfanın
        hepsini doldurduğu doğrulanıyor: başlık boş kalırsa `<h1>` boşalır.
        """
        html = self.client.get('/').content.decode()
        self.assertNotRegex(html, r'<h1 class="l-hero-title">\s*</h1>')
        self.assertNotRegex(html, r'<p class="l-hero-desc">\s*</p>')
        self.assertIn('l-metric-value', html)

    def test_landing_links_to_the_sources_page(self):
        html = self.client.get('/').content.decode()
        self.assertIn(reverse('seo:licenses'), html)


class FaqSingleSourceTests(TestCase):
    def test_visible_and_structured_faq_carry_the_same_text(self):
        html = self.client.get('/').content.decode()
        schema = _faq_schema(html)
        self.assertIsNotNone(schema, 'sayfada FAQPage JSON-LD bloğu yok')

        questions = [q['name'] for q in schema['mainEntity']]
        answers = [q['acceptedAnswer']['text'] for q in schema['mainEntity']]
        self.assertEqual(len(questions), len(faq.ITEMS))

        # Görünür liste: her soru bir <details> içinde.
        visible = re.findall(
            r'<details class="l-faq-item">\s*<summary>(.*?)<span', html, re.S,
        )
        self.assertEqual(len(visible), len(faq.ITEMS))
        for question, shown in zip(questions, visible):
            # JSON-LD düz metin, görünür sürüm Django tarafından escape'li —
            # karşılaştırma apostrof entity'si çözülerek yapılıyor.
            self.assertEqual(question, shown.strip().replace('&#x27;', "'"))
        self.assertTrue(all(answers))

    def test_schema_json_escapes_script_terminators(self):
        """`</script>` kaçışı olmasa gömülü JSON scripti kapatabilirdi."""
        body = faq.as_schema_json()
        self.assertNotIn('<', body)
        self.assertNotIn('>', body)
