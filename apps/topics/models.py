import re

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Topic(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    explanation = models.TextField(blank=True, verbose_name=_('Konu anlatımı (TR)'))
    # /en/ sayfalarında gövde de gerçekten İngilizce olsun diye ayrı alan.
    # Boşsa Türkçe metne düşülür.
    explanation_en = models.TextField(blank=True, verbose_name=_('Konu anlatımı (EN)'))
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def explanation_for(self, language_code):
        """(metin, dil_kodu) — istenen dil yoksa mevcut olana düşer."""
        if language_code == 'en' and self.explanation_en:
            return self.explanation_en, 'en'
        if self.explanation:
            return self.explanation, 'tr'
        return self.explanation_en, 'en'

    def explanation_sections(self):
        text = (self.explanation or self.explanation_en or '').strip()
        if not text:
            return []

        blocks = re.split(r'\n\s*\n+', text.strip())
        sections = []

        for block in blocks:
            lines = [line.rstrip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue

            title = None
            items = []

            for idx, line in enumerate(lines):
                stripped = line.strip()
                bullet = stripped.startswith(('•', '-', '*'))

                if idx == 0 and not bullet:
                    candidate = stripped
                    is_heading = (
                        candidate.endswith('?')
                        or candidate.endswith(':')
                        or candidate.upper() == candidate
                        or ' vs ' in candidate.lower()
                        or re.fullmatch(r'[A-Z0-9ÇĞİÖŞÜ\s\-/:()]+', candidate) is not None
                    )
                    if is_heading and len(candidate) <= 60:
                        title = candidate
                        continue

                if bullet:
                    items.append(stripped[1:].strip())
                    continue

                if title is None:
                    title = 'Özet'
                    items.append(stripped)
                    continue

                items.append(stripped)

            if title is None:
                title = 'Özet'

            if not items:
                items = [lines[0]]

            sections.append({'title': title, 'items': items})

        if not sections:
            return [{'title': 'Özet', 'items': [text]}]

        return sections


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
    sentence_en = models.CharField(max_length=300)
    sentence_tr = models.CharField(max_length=300)

    class Meta:
        ordering = ['kind', 'id']

    def __str__(self):
        return f'[{self.kind}] {self.sentence_en}'
