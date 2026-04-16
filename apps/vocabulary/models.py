from django.conf import settings
from django.db import models


class Word(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='words',
    )
    english = models.CharField(max_length=120)
    turkish = models.CharField(max_length=200)
    example_en = models.CharField(max_length=400, blank=True)
    example_tr = models.CharField(max_length=400, blank=True)
    part_of_speech = models.CharField(max_length=30, blank=True)
    source = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    times_asked = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'english'], name='unique_user_english'),
        ]

    def __str__(self):
        return f'{self.english} — {self.turkish}'

    @property
    def accuracy(self):
        if self.times_asked == 0:
            return None
        return round(100 * self.times_correct / self.times_asked)
