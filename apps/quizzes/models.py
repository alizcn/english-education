from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from services import languages


class QuizTemplate(models.Model):
    WORD = 'word'
    TOPIC = 'topic'
    KIND_CHOICES = [(WORD, _('Kelime')), (TOPIC, _('Konu'))]

    PENDING = 'pending'
    READY = 'ready'
    FAILED = 'failed'
    # pgettext: aynı msgid mülakat tarafında da var ve orada mülakata özgü
    # çevrildi. Bağlam vermezsek biri diğerinin çevirisini miras alır.
    STATUS_CHOICES = [
        (PENDING, pgettext_lazy('quiz durumu', 'Hazırlanıyor')),
        (READY, pgettext_lazy('quiz durumu', 'Hazır')),
        (FAILED, pgettext_lazy('quiz durumu', 'Başarısız')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='quiz_templates',
    )
    # Dil çifti şablonun kendi özelliği, kullanıcının değil: seed şablonları
    # `user=None` olduğu için `UserCourse`a FK verilemiyor.
    target_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, default='en',
        db_index=True, verbose_name=_('Öğrenilen dil'),
    )
    native_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, default='tr',
        verbose_name=_('Anlatım dili'),
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='quiz_templates',
    )
    name = models.CharField(max_length=40)
    # Üretim arka planda ve parça parça ilerliyor: şablon PENDING olarak boş
    # doğuyor, sorular biriktikçe buraya yazılıyor.
    questions_data = models.JSONField(default=list)
    # Varsayılan READY: mevcut satırlar (seed quizler dahil) zaten dolu.
    # Üretimi kuyruğa atan view'ler status'ü açıkça PENDING veriyor.
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=READY)
    error_message = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.name} [{self.kind}]'

    @property
    def question_count(self):
        return len(self.questions_data) if self.questions_data else 0

    @property
    def is_ready(self):
        return self.status == self.READY


class QuizSession(models.Model):
    WORD = 'word'
    TOPIC = 'topic'
    KIND_CHOICES = [(WORD, _('Kelime')), (TOPIC, _('Konu'))]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_sessions',
    )
    # Puan bu çiftin kursuna yazılıyor (bkz. apps/accounts/signals.py):
    # Almanca quizinin puanı İngilizce seviyesini yükseltmemeli.
    target_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, default='en',
        db_index=True, verbose_name=_('Öğrenilen dil'),
    )
    native_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, default='tr',
        verbose_name=_('Anlatım dili'),
    )
    template = models.ForeignKey(
        QuizTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quiz_sessions',
    )
    total_questions = models.PositiveIntegerField(default=50)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        label = self.topic.name if self.topic else str(_('Kelime'))
        return (f'[{self.target_language}] {label} '
                f'({self.correct_count}/{self.total_questions})')

    @property
    def answered_count(self):
        return self.correct_count + self.wrong_count

    @property
    def is_finished(self):
        return self.finished_at is not None

    @property
    def progress_percent(self):
        if self.total_questions == 0:
            return 0
        return round(100 * self.answered_count / self.total_questions)

    @property
    def score_percent(self):
        if self.answered_count == 0:
            return 0
        return round(100 * self.correct_count / self.answered_count)


class QuizQuestion(models.Model):
    # Dil ÇİFTİ değil, YÖN kodlanıyor. `translate_en_tr` gibi çift bazlı
    # isimlendirme 4 hedef × 3 ana dil = 12 çiftte 24 enum değerine patlıyordu;
    # yön + oturumun `target_language`/`native_language` alanları birlikte
    # anlamı tam belirlediği için sabit 4 değer yetiyor.
    #
    # max_length=20 sınırın dibinde: iki değer de 19 karakter. Daha uzun bir
    # tip adı eklenirse AlterField gerekir.
    TRANSLATE_TO_NATIVE = 'translate_to_native'   # hedef dilde sor, ana dilde cevapla
    TRANSLATE_TO_TARGET = 'translate_to_target'   # ana dilde sor, hedef dilde cevapla
    FILL_BLANK = 'fill_blank'
    MULTIPLE_CHOICE = 'multiple_choice'
    TYPE_CHOICES = [
        (TRANSLATE_TO_NATIVE, _('Hedef dilden çeviri')),
        (TRANSLATE_TO_TARGET, _('Hedef dile çeviri')),
        (FILL_BLANK, _('Boşluk doldurma')),
        (MULTIPLE_CHOICE, _('Çoktan seçmeli')),
    ]

    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveIntegerField()
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    prompt = models.TextField()
    correct_answer = models.CharField(max_length=400)
    choices = models.JSONField(null=True, blank=True)
    word = models.ForeignKey(
        'vocabulary.Word',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quiz_questions',
    )
    user_answer = models.CharField(max_length=400, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['session', 'order'], name='unique_session_order'),
        ]

    def __str__(self):
        return f'#{self.order}: {self.prompt[:40]}'
