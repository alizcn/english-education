from pathlib import Path
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-me-if-you-like')
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'


def _split_csv(value):
    return [item.strip() for item in value.split(',') if item.strip()]


def _host_from_url(url_value):
    if not url_value:
        return ''
    url_value = url_value.strip().rstrip('/')
    if '://' in url_value:
        url_value = url_value.split('://', 1)[1]
    host = url_value.split('/', 1)[0]
    return host.split(':', 1)[0]


SITE_URL = os.getenv('SITE_URL', 'https://levelenai.com').rstrip('/')


def get_allowed_hosts():
    hosts = set(_split_csv(os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')))
    site_host = _host_from_url(SITE_URL)
    if site_host:
        hosts.add(site_host)
    return sorted(hosts)


def get_csrf_trusted_origins():
    origins = set(_split_csv(os.getenv('CSRF_TRUSTED_ORIGINS', '')))
    site_url = os.getenv('SITE_URL', '').strip()
    if site_url:
        origins.add(site_url.rstrip('/'))
    for host in ('http://localhost:8000', 'http://127.0.0.1:8000', 'http://localhost:8070', 'http://127.0.0.1:8070'):
        origins.add(host)
    return sorted(origins)


ALLOWED_HOSTS = get_allowed_hosts()
CSRF_TRUSTED_ORIGINS = get_csrf_trusted_origins()

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@levelenai.com')

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------- Claude
# cli = Claude Code CLI subprocess'i, kimlik ~/.claude oturumundan (Pro/Max
# aboneliği) gelir; API key gerekmez. api = ANTHROPIC_API_KEY ile token başına
# faturalanan resmî SDK.
CLAUDE_AUTH_MODE = os.getenv('CLAUDE_AUTH_MODE', 'cli')
# Boşsa SDK claude binary'sini PATH'te arar.
CLAUDE_CLI_PATH = os.getenv('CLAUDE_CLI_PATH', '')
# Subprocess başına duvar saati sınırı — asılı kalan bir CLI gunicorn worker'ını
# meşgul etmesin. 25 soruluk mülakat üretimi ölçümde ~480s sürüyor; sınır ona göre.
# Gunicorn --timeout değeri bunun üstünde kalmalı (bkz. Dockerfile).
CLAUDE_CLI_TIMEOUT = int(os.getenv('CLAUDE_CLI_TIMEOUT', '600'))
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5')
# Quiz/çeviri/mülakat üretimi uzun JSON döndürüyor ve düşünme blokları da bu
# bütçeden harcanıyor; sınır bu yüzden geniş.
CLAUDE_MAX_TOKENS = int(os.getenv('CLAUDE_MAX_TOKENS', '16000'))
CLAUDE_CHAT_MAX_TOKENS = int(os.getenv('CLAUDE_CHAT_MAX_TOKENS', '4000'))
# low | medium | high | xhigh | max. Boş = parametre hiç gönderilmez.
# DİKKAT: Haiku 4.5 effort parametresini kabul etmiyor, gönderilirse hata döner.
# Bu yüzden varsayılan boş. Opus/Sonnet'e geçersen doldurabilirsin.
CLAUDE_REASONING_EFFORT = os.getenv('CLAUDE_REASONING_EFFORT', '')
# adaptive | disabled. Boş = parametre hiç gönderilmez, model düşünmeden yanıtlar.
# DİKKAT: adaptive/disabled yalnızca Opus 4.6+ ve Sonnet 4.6+ için geçerli.
# Haiku 4.5'te düşünmeyi kapatmanın yolu parametreyi hiç göndermemek.
CLAUDE_THINKING = os.getenv('CLAUDE_THINKING', '')
CLAUDE_MAX_RETRIES = int(os.getenv('CLAUDE_MAX_RETRIES', '3'))
# Uzun üretimler paralel parçalara bölünüyor (bkz. services/claude_client.parallel_map).
# Bu tavan BELLEKLE sınırlı: cli modunda her parça ayrı bir Claude Code subprocess'i ve
# ölçümde her biri ~220-400 MB RSS. Celery worker concurrency'siyle ÇARPILIR — ikisini
# birlikte büyütmek OOM'a, oradan da acks_late yüzünden sonsuz yeniden teslim döngüsüne
# götürür. Ölçüm ayrıca 5'ten fazla parçanın hız kazandırmadığını gösteriyor.
CLAUDE_MAX_PARALLEL = int(os.getenv('CLAUDE_MAX_PARALLEL', '5'))

# ---------------------------------------------------------------- SEO
# Canonical/OG/sitemap URL'leri bu köke göre kurulur. Şema mutlaka https
# olmalı; aksi halde canonical ile gerçek URL çakışır.
SITE_NAME = 'LevelEnAI'
SEO_DEFAULT_IMAGE = 'og/levelenai-og.png'
SEO_TWITTER_HANDLE = os.getenv('SEO_TWITTER_HANDLE', '')
# Search Console / Analytics doğrulaması — boşsa etiket hiç basılmaz.
GOOGLE_SITE_VERIFICATION = os.getenv('GOOGLE_SITE_VERIFICATION', '')
GA_MEASUREMENT_ID = os.getenv('GA_MEASUREMENT_ID', '')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django_celery_beat',
    'apps.accounts',
    'apps.dashboard',
    'apps.vocabulary',
    'apps.topics',
    'apps.quizzes',
    'apps.chat',
    'apps.wordbank',
    'apps.interviews',
    'apps.seo',
    'apps.superadmin',
]

CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
# acks_late'li görevler için: worker ölürse mesaj bu süre sonunda yeniden teslim
# edilir. Görevlerin hard time_limit'inden (720s) büyük olmalı — küçük olursa
# hâlâ çalışan bir görev ikinci kez teslim edilip aynı iş iki kez yapılır.
CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 900}
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.seo.context_processors.seo',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DB_PATH', str(BASE_DIR / 'db.sqlite3')),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'
CELERY_TIMEZONE = TIME_ZONE
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('tr', _('Türkçe')),
    ('en', _('English')),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'app.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO'},
        'apps': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'services': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
    },
}
