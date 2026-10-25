from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from services import languages


class BankWord(models.Model):
    """Bir hedef dildeki başlık kelime (lemma).

    Hedef taraf ile ana dil tarafı bilinçli olarak AYRI: örnek cümle hedef
    dilde bir kez üretiliyor, yalnızca çevirisi ana dile göre değişiyor. Anlamı
    aynı satırda tutmak (meaning_tr/en/fr/de) cümleyi her ana dil için yeniden
    üretmek demekti — ölçümde 45.436 gereksiz üretim. Bkz. `BankWordTranslation`.

    `(language, level, rank)` tekil; `term` DEĞİL. Çok anlamlılık böylece
    serbest kalıyor: A1'deki `about` "yaklaşık" ve "hakkında" olarak iki ayrı
    satır. Eski şema `(level, english, part_of_speech)` ile eşleştiği ve
    `part_of_speech` kaynak veride %90 boş olduğu için bu kelimeler tek satıra
    çöküyor, 6.218 kaydın 55'i veritabanına hiç girmiyordu.
    """

    LEVELS = [(level, level) for level in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')]

    language = models.CharField(
        max_length=5,
        choices=languages.LANGUAGE_CHOICES,
        db_index=True,
        verbose_name=_('Hedef dil'),
    )
    level = models.CharField(max_length=2, choices=LEVELS, db_index=True)
    rank = models.PositiveIntegerField(
        help_text=_('Kaynak listedeki sıra. Quiz ilerleyişini bu belirler.'),
    )
    term = models.CharField(max_length=120, verbose_name=_('Terim'))
    part_of_speech = models.CharField(max_length=40, blank=True)
    example = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('Örnek cümle (hedef dilde)'),
    )
    # Dile özgü morfoloji: Almanca artikel + çoğul, Fransızca cinsiyet, vb.
    # Hiçbir sorguda filtrelenmediği için JSON doğru araç — dil başına ayrı
    # sütun açmak yerine.
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['language', 'level', 'rank']
        constraints = [
            models.UniqueConstraint(
                fields=['language', 'level', 'rank'],
                name='unique_bank_word_rank',
            ),
        ]
        indexes = [
            # Arama ve çeldirici seçimi; tekil DEĞİL.
            models.Index(fields=['language', 'level', 'term'],
                         name='bankword_lang_level_term'),
            # pick_next() görülmemiş kelimeyi rank sırasıyla çekiyor.
            models.Index(fields=['language', 'level', 'rank'],
                         name='bankword_lang_level_rank'),
        ]

    def __str__(self):
        return f'[{self.language}] {self.level}:{self.term} ({self.part_of_speech})'

    def translation_for(self, native_language):
        """Verilen ana dildeki çeviri ya da None."""
        for tr in self.translations.all():
            if tr.language == native_language:
                return tr
        return None


class BankWordTranslation(models.Model):
    """Bir başlık kelimenin tek bir ana dildeki anlamı ve örnek çevirisi.

    (hedef × ana dil) matrisi bu tabloda yaşıyor: aynı `BankWord` satırı
    Türkçe, İngilizce, Fransızca ve Almanca anlamlarını yan yana taşıyabiliyor.
    """

    word = models.ForeignKey(
        BankWord, on_delete=models.CASCADE, related_name='translations',
    )
    language = models.CharField(
        max_length=5,
        choices=languages.LANGUAGE_CHOICES,
        verbose_name=_('Ana dil'),
    )
    meaning = models.CharField(max_length=400, verbose_name=_('Anlam'))
    example_translation = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['word', 'language']
        constraints = [
            models.UniqueConstraint(
                fields=['word', 'language'], name='unique_word_translation',
            ),
        ]
        indexes = [
            # Çeldirici örneklemesi ana dile göre filtreliyor.
            models.Index(fields=['language'], name='wordtranslation_lang'),
        ]

    def __str__(self):
        return f'{self.word.term} [{self.language}] {self.meaning}'


class BankProgress(models.Model):
    """Kullanıcının bir kelimedeki durumu.

    Dil alanı YOK ve gerekmiyor: `word` zaten hedef dili taşıyor, dolayısıyla
    çok dilli ilerleme bedelsiz geliyor.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bank_progress',
    )
    word = models.ForeignKey(BankWord, on_delete=models.CASCADE, related_name='progress')
    mastered = models.BooleanField(default=False)
    wrong_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    last_answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'word'], name='unique_user_word_progress'),
        ]
