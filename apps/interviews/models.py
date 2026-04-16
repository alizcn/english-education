from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


JOB_CATEGORIES = [
    # Pozisyon bazlı
    ('backend_dev', _('Backend Developer')),
    ('frontend_dev', _('Frontend Developer')),
    ('python_fullstack', _('Python Full Stack Developer')),
    ('dotnet_fullstack', _('.NET Full Stack Developer')),
    ('java_fullstack', _('Java Full Stack Developer')),
    ('nodejs_fullstack', _('Node.js Full Stack Developer')),
    ('react_dev', _('React Developer')),
    ('angular_dev', _('Angular Developer')),
    ('vue_dev', _('Vue.js Developer')),
    ('go_dev', _('Go (Golang) Developer')),
    ('rust_dev', _('Rust Developer')),
    ('php_dev', _('PHP / Laravel Developer')),
    ('ios_dev', _('iOS Developer (Swift)')),
    ('android_dev', _('Android Developer (Kotlin)')),
    ('flutter_dev', _('Flutter / Dart Developer')),
    # Alan bazlı
    ('software_dev', _('Yazılım Geliştirme (Genel)')),
    ('devops', _('DevOps / SRE')),
    ('cloud', _('Bulut Bilişim (AWS/Azure/GCP)')),
    ('cyber_security', _('Siber Güvenlik')),
    ('ai_ml', _('Yapay Zeka / Makine Öğrenmesi')),
    ('data_science', _('Veri Bilimi / Veri Mühendisliği')),
    ('database_admin', _('Veri Tabanı Yönetimi (DBA)')),
    ('network_systems', _('Ağ Sistemleri')),
    ('info_systems', _('Bilişim Sistemleri')),
    ('computer_mgmt', _('Bilgisayar Yönetimi')),
    ('project_mgmt', _('Proje Yönetimi / Scrum Master')),
    ('qa_test', _('QA / Test Mühendisliği')),
    ('mobile_dev', _('Mobil Uygulama Geliştirme (Genel)')),
    ('web_dev', _('Web Geliştirme (Genel)')),
    ('embedded', _('Gömülü Sistemler')),
    ('game_dev', _('Oyun Geliştirme')),
    ('custom', _('Özel (kendi yazdığın)')),
]


class InterviewSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interview_sessions',
    )
    CATEGORY = 'category'
    CUSTOM = 'custom'
    CV = 'cv'
    SOURCE_CHOICES = [
        (CATEGORY, _('Kategori')),
        (CUSTOM, _('Özel başlık')),
        (CV, _('CV yükleme')),
    ]

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=CATEGORY)
    job_category = models.CharField(max_length=30, choices=JOB_CATEGORIES, default='custom')
    custom_title = models.CharField(max_length=200, blank=True)
    cv_filename = models.CharField(max_length=200, blank=True)
    questions_data = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        if self.source == self.CV and self.cv_filename:
            return f'CV: {self.cv_filename}'
        if self.source == self.CUSTOM and self.custom_title:
            return self.custom_title
        return dict(JOB_CATEGORIES).get(self.job_category, self.job_category)

    @property
    def question_count(self):
        return len(self.questions_data) if self.questions_data else 0
