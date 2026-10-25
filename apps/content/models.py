"""İçerik üretiminin defteri.

Üretim uzun ve kırılgan: ~62 bin anlam birimi, ~4.400 Claude çağrısı, CLI
oturum limiti yüzünden günlere yayılıyor. Bu yüzden her parça bir satır olarak
kaydediliyor ve komut kaldığı yerden devam ediyor.

Niçin veritabanı, dosya değil:

* `--resume` tek satır: `filter(status__in=['pending', 'failed'])`.
* Benzersizlik kısıtı "tam bir kez" garantisini bedelsiz veriyor; dosyada
  bunu kurmak kilit yönetimi demek.
* Paralel parçalar aynı anda yazıyor — dosya kilidiyle uğraşmak gerekmiyor.
* Superadmin üzerinden ilerleme ekranı bedelsiz geliyor.

Nihai GÖZDEN GEÇİRİLEBİLİR artefakt yine repo dosyası: `export_content`
komutu bu defteri deterministik JSON'a döküyor. İki adım bilinçli —
üretim yavaş ve kırılgan, dışa aktarma hızlı ve git-diff dostu.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from services import languages


class GenerationBatch(models.Model):
    """Tek bir üretim parçası: girdi, çıktı ve durumu."""

    WORDBANK = 'wordbank'
    TOPIC_EXPLANATION = 'topic_explanation'
    TOPIC_EXAMPLES = 'topic_examples'
    TOPIC_NAMES = 'topic_names'
    QUIZ_SEED = 'quiz_seed'
    WORDLIST_CURATION = 'wordlist_curation'
    KIND_CHOICES = [
        (WORDBANK, _('Kelime hazinesi')),
        (TOPIC_EXPLANATION, _('Konu anlatımı')),
        (TOPIC_EXAMPLES, _('Konu örnekleri')),
        (TOPIC_NAMES, _('Konu adları')),
        (QUIZ_SEED, _('Seed quiz')),
        (WORDLIST_CURATION, _('Kelime listesi ayıklama')),
    ]

    PENDING = 'pending'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (PENDING, _('Bekliyor')),
        (RUNNING, _('Çalışıyor')),
        (DONE, _('Bitti')),
        (FAILED, _('Başarısız')),
    ]

    MAX_ATTEMPTS = 3

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    target_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, db_index=True,
    )
    #: Boş = ana dilden bağımsız (mono) içerik: hedef dildeki örnek cümle,
    #: `fill_blank`/`multiple_choice` soruları, konu adları.
    native_language = models.CharField(
        max_length=5, choices=languages.LANGUAGE_CHOICES, blank=True, default='',
    )
    level = models.CharField(max_length=2, blank=True, default='')
    topic_slug = models.SlugField(blank=True, default='')
    chunk_index = models.PositiveIntegerField()
    batch_size = models.PositiveIntegerField()

    input_payload = models.JSONField(default=dict)
    output = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default='')
    model_used = models.CharField(max_length=60, blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['kind', 'target_language', 'native_language', 'level',
                    'topic_slug', 'chunk_index']
        verbose_name = _('Üretim parçası')
        verbose_name_plural = _('Üretim parçaları')
        constraints = [
            # "Tam bir kez" garantisi. Parça anahtarı deterministik olduğu için
            # komut yeniden koşulduğunda aynı parçaya denk geliyor.
            models.UniqueConstraint(
                fields=['kind', 'target_language', 'native_language', 'level',
                        'topic_slug', 'chunk_index'],
                name='unique_generation_batch',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'kind'], name='genbatch_status_kind'),
        ]

    def __str__(self):
        scope = '/'.join(p for p in (self.target_language, self.native_language,
                                     self.level, self.topic_slug) if p)
        return f'{self.kind} {scope} #{self.chunk_index} [{self.status}]'

    @property
    def is_exhausted(self):
        """Deneme hakkı bitti mi? Oturum limiti denemeyi artırmıyor."""
        return self.attempts >= self.MAX_ATTEMPTS


class ContentFingerprint(models.Model):
    """Seed komutlarının kaynak dosya parmak izi.

    Container açılışı eskiden her seferinde üç seeder'ı koşuyordu; dört dile
    çıkınca bu dakikalara ulaşıyor. Entrypoint bu tabloyu okuyup kaynak
    değişmemişse adımı atlıyor.
    """

    name = models.CharField(max_length=60, unique=True)
    digest = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}: {self.digest[:12]}'
