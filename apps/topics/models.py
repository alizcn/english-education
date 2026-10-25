from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from services import languages

from .markup import parse_sections


class Topic(models.Model):
    """Bir hedef dildeki gramer konusu.

    Konu listesi hedef dile ÖZGÜ: Almanca'da "Perfekt" var, "Present Perfect
    Continuous" yok. Bu yüzden `slug` tek başına tekil değil; `(language, slug)`
    tekil. Böylece aynı slug farklı dillerde yan yana yaşayabiliyor ve konu
    listeleri birbirine karışmıyor.

    Anlatım metni ayrı tabloda (`TopicExplanation`): SEO sayfası tek bir dilin
    anlatımını kendi başına çekiyor ve "hangi dilde anlatım eksik" sorusu
    raporlanıyor — ikisi de içeriğe göre sorgulama, yani normalize tablo.
    """

    language = models.CharField(
        max_length=5,
        choices=languages.LANGUAGE_CHOICES,
        default='en',
        db_index=True,
        verbose_name=_('Hedef dil'),
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['language', 'order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['language', 'slug'], name='unique_topic_language_slug',
            ),
        ]

    def __str__(self):
        return f'[{self.language}] {self.name}'

    # ------------------------------------------------------------ anlatım

    def explanation_for(self, language_code):
        """(gövde, dil_kodu) — istenen dil yoksa fallback zincirine düşer.

        Döndürülen kod GERÇEKTEN o gövdenin dili. Eski sürüm yalnızca `en`/`tr`
        biliyordu ve `fr`/`de` istendiğinde sessizce Türkçe gövdeyi döndürüp
        `'tr'` diyordu; `inLanguage` ve `lang` attribute'ları bu yüzden yanlış
        basılıyordu.
        """
        by_language = {e.language: e for e in self.explanations.all()}
        for code in self._fallback_order(language_code):
            entry = by_language.get(code)
            if entry and entry.body.strip():
                return entry.body, entry.language
        return '', ''

    @staticmethod
    def _fallback_order(requested):
        seen, order = set(), []
        for code in (requested, 'en', *languages.UI_CODES):
            if code and code not in seen:
                seen.add(code)
                order.append(code)
        return order

    def explanation_sections(self, language_code=None):
        """Anlatımı `Section` listesine ayırır.

        `language_code` verilmezse ilk bulunan anlatım kullanılır. Eski sürüm
        her zaman Türkçe gövdeyi okuyordu — `/en/` sayfasında başlıklar
        Türkçe'den geliyordu.
        """
        body, _code = self.explanation_for(language_code or 'en')
        return parse_sections(body)


class TopicExplanation(models.Model):
    """Bir konunun tek bir ana dildeki anlatımı.

    Gövde kısıtlı markdown: `##` başlık, `-`/`•` madde. Bkz. `apps/topics/markup.py`.
    """

    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name='explanations',
    )
    language = models.CharField(
        max_length=5,
        choices=languages.LANGUAGE_CHOICES,
        verbose_name=_('Anlatım dili'),
    )
    body = models.TextField(verbose_name=_('Anlatım (markdown)'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['topic', 'language']
        constraints = [
            models.UniqueConstraint(
                fields=['topic', 'language'], name='unique_topic_explanation',
            ),
        ]

    def __str__(self):
        return f'{self.topic.slug} [{self.language}]'


class TopicCompletion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='completed_topics',
    )
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'topic')]


class TopicExample(models.Model):
    """Konu örneği: hedef dilde cümle + ana dillere çevirileri.

    Çeviriler JSON, ayrı tablo değil — `TopicExplanation`la arasındaki fark tek
    kurala dayanıyor: bu örnekler HER ZAMAN konuyla birlikte 18'li okunuyor ve
    hiçbir sorguda içeriğine göre filtrelenmiyor. Ek olarak Django admin iki
    kademe nested inline desteklemiyor; ayrı tablo olsa örnek çevirileri
    `TopicExampleInline` içinden düzenlenemezdi.
    """

    POSITIVE = 'positive'
    NEGATIVE = 'negative'
    QUESTION = 'question'
    KIND_CHOICES = [
        (POSITIVE, _('Olumlu')),
        (NEGATIVE, _('Olumsuz')),
        (QUESTION, _('Soru')),
    ]

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='examples')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    order = models.PositiveIntegerField(default=0)
    sentence = models.CharField(
        max_length=300, verbose_name=_('Cümle (hedef dilde)'),
    )
    translations = models.JSONField(
        default=dict, blank=True,
        help_text=_('{"tr": "...", "en": "..."} — ana dil kodundan çeviriye.'),
    )

    class Meta:
        ordering = ['topic', 'kind', 'order', 'id']
        constraints = [
            # Seeder artık sil-yeniden-yarat yerine bu anahtarla upsert ediyor.
            models.UniqueConstraint(
                fields=['topic', 'kind', 'order'], name='unique_topic_example_order',
            ),
        ]

    def __str__(self):
        return f'[{self.kind}] {self.sentence}'

    def translation_for(self, language_code):
        """Çeviri ya da boş string. Sözlük anahtarları ana dil kodları."""
        if not isinstance(self.translations, dict):
            return ''
        return (self.translations.get(language_code) or '').strip()
