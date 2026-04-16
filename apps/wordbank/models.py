from django.conf import settings
from django.db import models


class BankWord(models.Model):
    LEVELS = [('A1', 'A1'), ('A2', 'A2'), ('B1', 'B1'), ('B2', 'B2'), ('C1', 'C1'), ('C2', 'C2')]

    level = models.CharField(max_length=2, choices=LEVELS, db_index=True)
    rank = models.PositiveIntegerField()
    english = models.CharField(max_length=120)
    part_of_speech = models.CharField(max_length=40, blank=True)
    turkish = models.CharField(max_length=400)
    example_en = models.CharField(max_length=500, blank=True)
    example_tr = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['level', 'rank']
        constraints = [
            models.UniqueConstraint(
                fields=['level', 'english', 'part_of_speech'],
                name='unique_bank_word',
            ),
        ]

    def __str__(self):
        return f'{self.level}:{self.english} ({self.part_of_speech})'


class BankProgress(models.Model):
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
