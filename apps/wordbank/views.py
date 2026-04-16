from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from . import services
from .models import BankWord, BankProgress


LEVEL_LABELS = {
    'A1': _('Başlangıç'),
    'A2': _('Temel Üstü'),
    'B1': _('Orta'),
    'B2': _('Orta Üstü'),
    'C1': _('İleri'),
    'C2': _('Uzman'),
}


def _valid_level(level):
    return level in dict(BankWord.LEVELS)


@login_required
def levels(request):
    rows = []
    for code, _label in BankWord.LEVELS:
        stats = services.level_stats(request.user, code)
        stats['label'] = LEVEL_LABELS.get(code, code)
        rows.append(stats)
    return render(request, 'wordbank/levels.html', {'levels': rows})


@login_required
def quiz(request, level):
    if not _valid_level(level):
        return redirect('wordbank:levels')

    stats = services.level_stats(request.user, level)
    if stats['total'] == 0:
        messages.error(request, gettext('%(level)s seviyesi yüklü değil.') % {'level': level})
        return redirect('wordbank:levels')

    word, is_retry = services.pick_next(request.user, level)

    if word is None:
        return render(request, 'wordbank/complete.html', {
            'level': level,
            'label': LEVEL_LABELS.get(level, level),
            'stats': stats,
        })

    options = services.build_question(word)
    return render(request, 'wordbank/quiz.html', {
        'level': level,
        'label': LEVEL_LABELS.get(level, level),
        'word': word,
        'options': options,
        'is_retry': is_retry,
        'stats': stats,
        'current_num': stats['mastered'] + 1,
    })


@login_required
@require_POST
def answer(request, level):
    if not _valid_level(level):
        return redirect('wordbank:levels')

    word_id = request.POST.get('word_id')
    selected = request.POST.get('answer', '').strip()
    word = get_object_or_404(BankWord, pk=word_id, level=level)

    is_correct = (selected == word.turkish)
    services.record_answer(request.user, word, is_correct)

    stats = services.level_stats(request.user, level)

    return render(request, 'wordbank/feedback.html', {
        'level': level,
        'label': LEVEL_LABELS.get(level, level),
        'word': word,
        'selected': selected,
        'is_correct': is_correct,
        'stats': stats,
    })


@login_required
@require_POST
def reset(request, level):
    if not _valid_level(level):
        return redirect('wordbank:levels')
    BankProgress.objects.filter(user=request.user, word__level=level).delete()
    messages.success(request, gettext('%(level)s ilerlemen sıfırlandı.') % {'level': level})
    return redirect('wordbank:levels')
