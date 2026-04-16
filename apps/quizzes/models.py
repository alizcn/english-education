from django.conf import settings
from django.db import models


class QuizTemplate(models.Model):
    WORD = 'word'
    TOPIC = 'topic'
    KIND_CHOICES = [(WORD, 'Kelime'), (TOPIC, 'Konu')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_templates',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='quiz_templates',
    )
    name = models.CharField(max_length=40)
    questions_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.name} [{self.kind}]'


class QuizSession(models.Model):
    WORD = 'word'
    TOPIC = 'topic'
    KIND_CHOICES = [(WORD, 'Kelime'), (TOPIC, 'Konu')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_sessions',
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
        label = self.topic.name if self.topic else 'Kelime'
        return f'{label} ({self.correct_count}/{self.total_questions})'

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
    TRANSLATE_EN_TR = 'translate_en_tr'
    TRANSLATE_TR_EN = 'translate_tr_en'
    FILL_BLANK = 'fill_blank'
    MULTIPLE_CHOICE = 'multiple_choice'
    TYPE_CHOICES = [
        (TRANSLATE_EN_TR, 'Çeviri EN→TR'),
        (TRANSLATE_TR_EN, 'Çeviri TR→EN'),
        (FILL_BLANK, 'Boşluk doldurma'),
        (MULTIPLE_CHOICE, 'Çoktan seçmeli'),
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
