import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from services import ai
from services.sanitize import SanitizationError, clean_cv_text, clean_job_title
from .models import InterviewSession, JOB_CATEGORIES
from .utils import extract_cv_text

logger = logging.getLogger(__name__)

try:
    import magic as _magic
except ImportError:  # libmagic / python-magic kurulu değil — ext+size fallback
    _magic = None


POSITION_KEYS = [
    'backend_dev', 'frontend_dev', 'python_fullstack', 'dotnet_fullstack',
    'java_fullstack', 'nodejs_fullstack', 'react_dev', 'angular_dev',
    'vue_dev', 'go_dev', 'rust_dev', 'php_dev', 'ios_dev', 'android_dev', 'flutter_dev',
]

_cat_dict = dict(JOB_CATEGORIES)

_ALLOWED_CV_MIME = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/zip',  # DOCX'in bazı magic imzaları zip döndürür
    'text/plain',
}
_ALLOWED_CV_EXT = ('.pdf', '.docx', '.txt')
_MAX_CV_SIZE = 5 * 1024 * 1024  # 5 MB


def _validate_cv_file(cv_file):
    if cv_file.size > _MAX_CV_SIZE:
        raise ValueError(_("CV dosyası 5 MB'dan büyük olamaz."))
    name = (cv_file.name or '').lower()
    if not name.endswith(_ALLOWED_CV_EXT):
        raise ValueError(_('Desteklenen formatlar: PDF, DOCX, TXT.'))
    if _magic is not None:
        head = cv_file.read(2048)
        cv_file.seek(0)
        try:
            mime = _magic.from_buffer(head, mime=True)
        except Exception:
            logger.warning('python-magic sniff failed, falling back to extension check')
            return
        if mime not in _ALLOWED_CV_MIME:
            raise ValueError(_('Dosya içeriği desteklenen bir formatla eşleşmiyor.'))


@login_required
def interview_list(request):
    sessions = InterviewSession.objects.filter(user=request.user)
    positions = [(k, _cat_dict[k]) for k in POSITION_KEYS if k in _cat_dict]
    fields = [(k, v) for k, v in JOB_CATEGORIES if k not in POSITION_KEYS and k != 'custom']
    return render(request, 'interviews/list.html', {
        'sessions': sessions,
        'positions': positions,
        'fields': fields,
    })


@login_required
@require_POST
@ratelimit(key='user', rate='10/h', method='POST', block=False)
def interview_create(request):
    if getattr(request, 'limited', False):
        messages.error(request, _('Saatlik mülakat üretim hakkını doldurdun. Biraz sonra tekrar dene.'))
        return redirect('interviews:list')

    job_category = request.POST.get('job_category', '').strip()
    custom_title = request.POST.get('custom_title', '').strip()

    if job_category == 'custom' and not custom_title:
        messages.error(request, _('Lütfen bir iş başlığı girin.'))
        return redirect('interviews:list')

    if job_category == 'custom':
        try:
            title_for_ai = clean_job_title(custom_title)
        except SanitizationError as e:
            messages.error(request, str(e))
            return redirect('interviews:list')
    else:
        title_for_ai = dict(JOB_CATEGORIES).get(job_category, job_category)

    try:
        items = ai.generate_interview_questions(str(title_for_ai), n=25)
    except ai.AIServiceError as e:
        messages.error(request, str(e))
        return redirect('interviews:list')
    except Exception:
        logger.exception('interview_create: unexpected AI failure')
        messages.error(request, _('Sorular üretilirken beklenmedik bir hata oluştu.'))
        return redirect('interviews:list')

    if not items:
        messages.error(request, _('Sorular üretilemedi. Tekrar deneyin.'))
        return redirect('interviews:list')

    source = InterviewSession.CUSTOM if job_category == 'custom' else InterviewSession.CATEGORY
    session = InterviewSession.objects.create(
        user=request.user,
        source=source,
        job_category=job_category if job_category in _cat_dict else 'custom',
        custom_title=custom_title if job_category == 'custom' else '',
        questions_data=items,
    )

    messages.success(
        request,
        _('%(count)d mülakat sorusu oluşturuldu.') % {'count': len(items)}
    )
    return redirect('interviews:detail', pk=session.pk)


@login_required
@require_POST
@ratelimit(key='user', rate='10/h', method='POST', block=False)
def interview_create_cv(request):
    if getattr(request, 'limited', False):
        messages.error(request, _('Saatlik mülakat üretim hakkını doldurdun. Biraz sonra tekrar dene.'))
        return redirect('interviews:list')

    cv_file = request.FILES.get('cv_file')
    if not cv_file:
        messages.error(request, _('Lütfen bir CV dosyası yükleyin.'))
        return redirect('interviews:list')

    try:
        _validate_cv_file(cv_file)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('interviews:list')

    try:
        raw_cv_text = extract_cv_text(cv_file)
    except Exception:
        logger.exception('cv extract failed')
        messages.error(request, _('CV dosyası okunamadı.'))
        return redirect('interviews:list')

    cv_text = clean_cv_text(raw_cv_text)
    if not cv_text or len(cv_text) < 50:
        messages.error(request, _('CV içeriği çok kısa veya okunamadı.'))
        return redirect('interviews:list')

    try:
        items = ai.generate_interview_from_cv(cv_text, n=25)
    except ai.AIServiceError as e:
        messages.error(request, str(e))
        return redirect('interviews:list')
    except Exception:
        logger.exception('interview_create_cv: unexpected AI failure')
        messages.error(request, _('Sorular üretilirken beklenmedik bir hata oluştu.'))
        return redirect('interviews:list')

    if not items:
        messages.error(request, _('Sorular üretilemedi. Tekrar deneyin.'))
        return redirect('interviews:list')

    session = InterviewSession.objects.create(
        user=request.user,
        source=InterviewSession.CV,
        job_category='custom',
        cv_filename=cv_file.name,
        questions_data=items,
    )

    messages.success(
        request,
        _('CV analiz edildi. %(count)d mülakat sorusu oluşturuldu.') % {'count': len(items)}
    )
    return redirect('interviews:detail', pk=session.pk)


@login_required
def interview_detail(request, pk):
    session = get_object_or_404(InterviewSession, pk=pk, user=request.user)
    return render(request, 'interviews/detail.html', {'session': session})


@login_required
@require_POST
def interview_delete(request, pk):
    session = get_object_or_404(InterviewSession, pk=pk, user=request.user)
    session.delete()
    messages.success(request, _('Mülakat silindi.'))
    return redirect('interviews:list')
