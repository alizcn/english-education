from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from services import languages


class Word(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='words',
    )
    # Düz sütun, ayrı çeviri tablosu YOK: kişisel liste zaten tek bir
    # (hedef, ana dil) çifti içinde yaşıyor — matris boyutu kurs tarafından
    # sabitlenmiş. Paylaşılan kelime hazinesinde durum farklı, bkz.
    # apps/wordbank/models.BankWordTranslation.
    target_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, default='en',
        db_index=True, verbose_name=_('Öğrenilen dil'),
    )
    native_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, default='tr',
        verbose_name=_('Anlatım dili'),
    )
    term = models.CharField(max_length=120, verbose_name=_('Terim'))
    meaning = models.CharField(max_length=200, verbose_name=_('Anlam'))
    example = models.CharField(max_length=400, blank=True)
    example_translation = models.CharField(max_length=400, blank=True)
    part_of_speech = models.CharField(max_length=30, blank=True)
    source = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    mastered = models.BooleanField(default=False)
    times_asked = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'target_language', 'term'],
                name='unique_user_target_term',
            ),
        ]

    def __str__(self):
        return f'[{self.target_language}] {self.term} — {self.meaning}'

    @property
    def accuracy(self):
        if self.times_asked == 0:
            return None
        return round(100 * self.times_correct / self.times_asked)
