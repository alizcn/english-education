from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from services import languages


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


LEVELS = [(level, level) for level in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')]

#: Puandan seviyeye eşik merdiveni. Yüksekten alçağa taranır.
THRESHOLDS = [
    (750, 'C2'),
    (500, 'C1'),
    (300, 'B2'),
    (150, 'B1'),
    (50, 'A2'),
    (0, 'A1'),
]


# `UserLevel` BURADAN SİLİNDİ (`accounts/0007`). Kullanıcı başına tek seviye
# tutan OneToOne modeldi, yani bir kullanıcı birden çok dil öğrenemiyordu.
# Veri `accounts/0006` ile `UserCourse`a taşındı; model bir faz boyunca
# okunmadan kodda bırakıldı ki geri alma veri yüklemesi gerektirmesin. O
# pencere kapandı.


class UserCourse(models.Model):
    """Kullanıcının bir dili öğrenme kaydı: seviye, puan ve dil çifti.

    `UserLevel`in OneToOne kısıtı yerine `(user, target_language)` tekilliği:
    bir kullanıcı aynı anda Almanca ve İngilizce öğrenebiliyor, her biri kendi
    seviyesini ve puanını taşıyor.

    `native_language` BİLİNÇLİ olarak burada, arayüz dilinde değil: kullanıcı
    arayüzü İngilizceye çevirdiğinde dersin ortasında Türkçe anlatımını
    kaybetmemeli. Kurs açılırken aktif arayüz dilinden ilk değer alıyor.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses',
    )
    target_language = models.CharField(
        max_length=5,
        choices=languages.LANGUAGE_CHOICES,
        verbose_name=_('Öğrenilen dil'),
    )
    native_language = models.CharField(
        max_length=5,
        choices=languages.LANGUAGE_CHOICES,
        verbose_name=_('Anlatım dili'),
    )
    current_level = models.CharField(max_length=2, choices=LEVELS, default='A1')
    score = models.IntegerField(default=0)
    is_active = models.BooleanField(
        default=False,
        help_text=_('Kullanıcının üzerinde çalıştığı kurs.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    _THRESHOLDS = THRESHOLDS

    class Meta:
        ordering = ['-is_active', 'target_language']
        verbose_name = _('Kurs')
        verbose_name_plural = _('Kurslar')
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'target_language'], name='unique_user_course',
            ),
            # Kısmi tekillik: kullanıcı başına en fazla bir aktif kurs.
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_active=True),
                name='one_active_course',
            ),
        ]

    def __str__(self):
        return (f'{self.user} · {self.target_language}'
                f'<-{self.native_language} · {self.current_level} ({self.score}p)')

    def clean(self):
        if self.target_language == self.native_language:
            raise ValidationError({
                'native_language': _('Anlatım dili, öğrenilen dille aynı olamaz.'),
            })
        # Alan `choices`ı tam dil listesi (migration churn'ünü önlemek için);
        # "şu an öğrenilebilir mi" kontrolü burada.
        if self.target_language not in languages.LEARNABLE_CODES:
            raise ValidationError({
                'target_language': _('Bu dil henüz öğrenilebilir değil.'),
            })
        if self.native_language not in languages.UI_CODES:
            raise ValidationError({
                'native_language': _('Bu dil henüz yayında değil.'),
            })

    @property
    def pair(self):
        """AI çağrılarına ve içerik sorgularına giden (hedef, ana dil) çifti."""
        return languages.pair(self.target_language, self.native_language)

    def advance(self, delta: int):
        self.score = max(0, self.score + delta)
        for threshold, level in self._THRESHOLDS:
            if self.score >= threshold:
                self.current_level = level
                break
        self.save(update_fields=['score', 'current_level', 'updated_at'])
