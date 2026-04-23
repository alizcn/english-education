from django.conf import settings
from django.db import models


class UserConsent(models.Model):
    KVKK = 'kvkk'
    KIND_CHOICES = [(KVKK, 'KVKK')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consents',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KVKK)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True, default='')

    class Meta:
        indexes = [models.Index(fields=['user', 'kind'])]

    def __str__(self):
        return f'{self.user} / {self.kind} @ {self.accepted_at:%Y-%m-%d}'


class UserLevel(models.Model):
    LEVELS = [(l, l) for l in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='level',
    )
    current_level = models.CharField(max_length=2, choices=LEVELS, default='A1')
    score = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    _THRESHOLDS = [
        (750, 'C2'),
        (500, 'C1'),
        (300, 'B2'),
        (150, 'B1'),
        (50, 'A2'),
        (0, 'A1'),
    ]

    def advance(self, delta: int):
        self.score = max(0, self.score + delta)
        for t, lvl in self._THRESHOLDS:
            if self.score >= t:
                self.current_level = lvl
                break
        self.save(update_fields=['score', 'current_level', 'updated_at'])

    def __str__(self):
        return f'{self.user} - {self.current_level} ({self.score} pts)'
