from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.accounts.services import current_pair

from . import services
from .models import BankProgress, BankWord, BankWordTranslation

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
    pair = current_pair(request)
    rows = []
    for code, _label in BankWord.LEVELS:
        stats = services.level_stats(
            request.user, code,
            target_language=pair.target_code, native_language=pair.native_code,
        )
        stats['label'] = LEVEL_LABELS.get(code, code)
        rows.append(stats)
    return render(request, 'wordbank/levels.html', {'levels': rows, 'pair': pair})


@login_required
def quiz(request, level):
    if not _valid_level(level):
        return redirect('wordbank:levels')

    pair = current_pair(request)
    stats = services.level_stats(
        request.user, level,
        target_language=pair.target_code, native_language=pair.native_code,
    )
    if stats['total'] == 0:
        messages.error(request, gettext('%(level)s seviyesi yüklü değil.') % {'level': level})
        return redirect('wordbank:levels')

    word, is_retry = services.pick_next(
        request.user, level,
        target_language=pair.target_code, native_language=pair.native_code,
    )

    if word is None:
        return render(request, 'wordbank/complete.html', {
            'level': level,
            'label': LEVEL_LABELS.get(level, level),
            'stats': stats,
        })

    correct, options = services.build_question(word, native_language=pair.native_code)
    if correct is None:
        # Çevirisi olmayan kelime sorguda süzülüyor; yine de buraya düşersek
        # kullanıcıyı boş ekranda bırakmayalım.
        messages.error(request, gettext('Bu kelimenin çevirisi eksik, atlandı.'))
        return redirect('wordbank:levels')

    return render(request, 'wordbank/quiz.html', {
        'level': level,
        'label': LEVEL_LABELS.get(level, level),
        'word': word,
        'options': options,
        'is_retry': is_retry,
        'stats': stats,
        'current_num': stats['mastered'] + 1,
        'pair': pair,
    })


@login_required
@require_POST
def answer(request, level):
    if not _valid_level(level):
        return redirect('wordbank:levels')

    pair = current_pair(request)
    word = get_object_or_404(
        BankWord, pk=request.POST.get('word_id'),
        level=level, language=pair.target_code,
    )
    correct = word.translation_for(pair.native_code)

    # Cevap KİMLİK ile karşılaştırılıyor, metinle değil. Eskiden seçilen metin
    # `word.turkish` ile karşılaştırılıyordu; aynı anlama gelen iki çeviri
    # ("kitap" / "kitap") şıkları sessizce teke indiriyor ve doğru cevabı
    # belirsizleştiriyordu.
    selected_id = (request.POST.get('translation_id') or '').strip()
    is_correct = bool(correct) and selected_id == str(correct.pk)

    selected = None
    if selected_id.isdigit():
        selected = BankWordTranslation.objects.filter(pk=int(selected_id)).first()

    services.record_answer(request.user, word, is_correct)

    stats = services.level_stats(
        request.user, level,
        target_language=pair.target_code, native_language=pair.native_code,
    )

    return render(request, 'wordbank/feedback.html', {
        'level': level,
        'label': LEVEL_LABELS.get(level, level),
        'word': word,
        'correct': correct,
        'selected': selected,
        'is_correct': is_correct,
        'stats': stats,
        'pair': pair,
    })


@login_required
@require_POST
def reset(request, level):
    if not _valid_level(level):
        return redirect('wordbank:levels')
    pair = current_pair(request)
    BankProgress.objects.filter(
        user=request.user, word__language=pair.target_code, word__level=level,
    ).delete()
    messages.success(request, gettext('%(level)s ilerlemen sıfırlandı.') % {'level': level})
    return redirect('wordbank:levels')
