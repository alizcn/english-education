"""Input sanitization helpers for AI-bound user content.

AI servislerine gönderilen kullanıcı metinleri bu modülden geçirilir.
Prompt injection veya kontrol karakteri enjeksiyonu riskini düşürmek amaçlı.
"""
import re

from django.utils.translation import gettext as _

_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
# Tek satırlık iş başlığı: newline/tab yasak; sadece yazdırılabilir işlem karakterleri.
_JOB_TITLE_RE = re.compile(r"^[\w \-,./()&+#]{1,120}$", re.UNICODE)
_BANNED_PATTERNS = re.compile(
    r'(ignore\s+(all\s+)?previous|system\s*prompt|you\s+are\s+now|disregard\s+instructions)',
    re.IGNORECASE,
)


class SanitizationError(ValueError):
    """Kullanıcı girdisi kabul edilebilir biçimde değil."""


def clean_job_title(raw: str) -> str:
    s = (raw or '').strip()
    if not s:
        raise SanitizationError(_('Pozisyon adı boş olamaz.'))
    if '\n' in s or '\r' in s or '\t' in s:
        raise SanitizationError(_('Pozisyon adı tek satırda olmalı.'))
    if not _JOB_TITLE_RE.match(s):
        raise SanitizationError(_(
            'Geçersiz pozisyon adı. Sadece harf, rakam ve temel noktalama (.,-/()&+#) kullan.'
        ))
    if _BANNED_PATTERNS.search(s):
        raise SanitizationError(_('Pozisyon adı geçersiz ifadeler içeriyor.'))
    return s


def clean_cv_text(raw: str, max_chars: int = 4000) -> str:
    s = _CONTROL_CHARS.sub(' ', raw or '')
    s = re.sub(r'\s{3,}', '  ', s).strip()
    return s[:max_chars]
