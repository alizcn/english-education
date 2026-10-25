"""Kurs seçici: kurs listesi, kurs ekleme/değiştirme, anlatım dili."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.models import UserCourse
from apps.accounts.services import activate, default_native_for, ensure_active_course
from services import languages


@login_required
def course_list(request):
    courses = list(UserCourse.objects.filter(user=request.user))
    taken = {c.target_language for c in courses}
    available = [
        spec for spec in languages.LEARNABLE_LANGUAGES
        if spec.code not in taken
    ]
    return render(request, 'learn/courses.html', {
        'courses': courses,
        'available': available,
        'native_options': languages.UI_LANGUAGES,
    })


@login_required
@require_POST
def switch_course(request):
    course = get_object_or_404(
        UserCourse, pk=request.POST.get('course_id'), user=request.user,
    )
    activate(course)
    messages.success(
        request,
        _('%(language)s kursuna geçtin.') % {
            'language': languages.display_name(
                course.target_language,
                in_language=request.LANGUAGE_CODE if hasattr(request, 'LANGUAGE_CODE') else 'tr',
                case='dat',
            ),
        },
    )
    return redirect('dashboard:home')


@login_required
@require_POST
def add_course(request):
    target = (request.POST.get('target_language') or '').strip()
    native = (request.POST.get('native_language') or '').strip()

    if target not in languages.LEARNABLE_CODES:
        messages.error(request, _('Bu dil henüz öğrenilebilir değil.'))
        return redirect('learn:courses')

    if native == target or native not in languages.UI_CODES:
        native = default_native_for(target)

    ensure_active_course(request.user, target=target, native=native)
    messages.success(request, _('Kurs eklendi.'))
    return redirect('dashboard:home')


@login_required
@require_POST
def set_native_language(request):
    """Aktif kursun anlatım dilini değiştirir.

    Arayüz dilinden AYRI: kullanıcı arayüzü İngilizceye çevirdiğinde dersin
    ortasında Türkçe anlatımını kaybetmemeli, ama anlatım dilini bilinçli
    olarak değiştirmek isteyebilir.
    """
    course = get_object_or_404(
        UserCourse, pk=request.POST.get('course_id'), user=request.user,
    )
    native = (request.POST.get('native_language') or '').strip()

    if native not in languages.UI_CODES:
        messages.error(request, _('Bu dil henüz yayında değil.'))
    elif native == course.target_language:
        messages.error(request, _('Anlatım dili, öğrenilen dille aynı olamaz.'))
    else:
        course.native_language = native
        course.save(update_fields=['native_language', 'updated_at'])
        messages.success(request, _('Anlatım dili güncellendi.'))
    return redirect('learn:courses')
