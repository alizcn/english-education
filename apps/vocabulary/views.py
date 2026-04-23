import logging
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils.translation import gettext as _
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.subscriptions import access as sub_access
from services import ai
from . import services as vocab_services
from .models import Word

logger = logging.getLogger(__name__)


def _user_words(user):
    return Word.objects.filter(user=user)


@login_required
def word_list(request):
    q = request.GET.get('q', '').strip()
    words = _user_words(request.user)
    if q:
        words = words.filter(Q(english__icontains=q) | Q(turkish__icontains=q))
    stats = vocab_services.personal_stats(request.user)
    return render(request, 'vocabulary/list.html', {'words': words, 'q': q, 'stats': stats})


def _parse_input(raw: str) -> list[str]:
    parts = re.split(r'[,\n;]+', raw)
    seen = set()
    out = []
    for p in parts:
        w = p.strip()
        if w and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out


@login_required
@ratelimit(key='user', rate='10/h', method='POST', block=False)
def bulk_add(request):
    if request.method == 'POST':
        if getattr(request, 'limited', False):
            messages.error(request, _('Saatlik çeviri hakkını doldurdun. Biraz sonra tekrar dene.'))
            return redirect('vocabulary:list')

        raw = request.POST.get('words', '')
        source = request.POST.get('source', '').strip()
        words = _parse_input(raw)

        if not words:
            messages.error(request, _('Hiç kelime girmedin.'))
            return redirect('vocabulary:bulk_add')

        try:
            items = ai.translate_words(words)
        except ai.AIServiceError as e:
            messages.error(request, str(e))
            return render(request, 'vocabulary/add.html', {'raw': raw, 'source': source})
        except Exception:
            logger.exception('bulk_add: unexpected AI failure')
            messages.error(request, _('AI çeviri sırasında beklenmedik bir hata oluştu.'))
            return render(request, 'vocabulary/add.html', {'raw': raw, 'source': source})

        with transaction.atomic():
            state = sub_access.get_state(request.user)
            if not sub_access.can_use_bulk_translate(state):
                messages.error(request, _('Toplu AI çeviri deneme hakkın doldu. Devam etmek için bir paket seç.'))
                return redirect('subscriptions:plans')

            created = 0
            skipped = 0
            dropped = 0
            for it in items:
                eng = (it.get('english') or '').strip().lower()
                tr = (it.get('turkish') or '').strip()
                if not eng or not tr:
                    dropped += 1
                    continue
                obj, was_created = Word.objects.get_or_create(
                    user=request.user,
                    english=eng,
                    defaults={
                        'turkish': tr,
                        'example_en': (it.get('example_en') or '').strip(),
                        'example_tr': (it.get('example_tr') or '').strip(),
                        'part_of_speech': (it.get('part_of_speech') or '').strip()[:30],
                        'source': source[:80],
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            sub_access.record_bulk_translate_use(state)

        msg = _('%(count)d kelime eklendi.') % {'count': created}
        if skipped:
            msg += ' ' + _('(%(count)d tanesi zaten vardı.)') % {'count': skipped}
        if dropped:
            msg += ' ' + _('(%(count)d tanesi eksik çeviriyle geldi, atlandı.)') % {'count': dropped}
        messages.success(request, msg)
        return redirect('vocabulary:list')

    return render(request, 'vocabulary/add.html', {'raw': '', 'source': ''})


@login_required
def word_edit(request, pk):
    word = get_object_or_404(Word, pk=pk, user=request.user)
    if request.method == 'POST':
        new_english = request.POST.get('english', word.english).strip().lower()
        new_turkish = request.POST.get('turkish', '').strip()
        if not new_english or not new_turkish:
            messages.error(request, _('İngilizce ve Türkçe alanları boş olamaz.'))
            return render(request, 'vocabulary/edit.html', {'word': word})
        if new_english != word.english and Word.objects.filter(
            user=request.user, english=new_english,
        ).exclude(pk=word.pk).exists():
            messages.error(request, _('Bu kelime zaten kayıtlı.'))
            return render(request, 'vocabulary/edit.html', {'word': word})
        word.english = new_english
        word.turkish = new_turkish
        word.example_en = request.POST.get('example_en', '').strip()
        word.example_tr = request.POST.get('example_tr', '').strip()
        word.part_of_speech = request.POST.get('part_of_speech', '').strip()[:30]
        word.source = request.POST.get('source', '').strip()[:80]
        word.save()
        messages.success(request, _('Kaydedildi.'))
        return redirect('vocabulary:list')
    return render(request, 'vocabulary/edit.html', {'word': word})


@login_required
@require_POST
def word_delete(request, pk):
    word = get_object_or_404(Word, pk=pk, user=request.user)
    word.delete()
    messages.success(request, _('Silindi.'))
    return redirect('vocabulary:list')


@login_required
def word_quiz(request):
    stats = vocab_services.personal_stats(request.user)
    if stats['total'] < vocab_services.MIN_WORDS_FOR_QUIZ:
        messages.error(
            request,
            _('Quiz için en az %(min)d kelime gerekli. Şu an: %(total)d.')
            % {'min': vocab_services.MIN_WORDS_FOR_QUIZ, 'total': stats['total']}
        )
        return redirect('vocabulary:list')

    word, is_retry = vocab_services.pick_next(request.user)

    if word is None:
        return render(request, 'vocabulary/quiz_complete.html', {'stats': stats})

    options = vocab_services.build_question(word, request.user)
    return render(request, 'vocabulary/quiz.html', {
        'word': word,
        'options': options,
        'is_retry': is_retry,
        'stats': stats,
    })


@login_required
@require_POST
def word_quiz_answer(request):
    word_id = request.POST.get('word_id')
    selected = request.POST.get('answer', '').strip()
    word = get_object_or_404(Word, pk=word_id, user=request.user)

    is_correct = (selected == (word.turkish or '').strip())
    vocab_services.record_answer(word, is_correct)
    stats = vocab_services.personal_stats(request.user)

    return render(request, 'vocabulary/quiz_feedback.html', {
        'word': word,
        'selected': selected,
        'is_correct': is_correct,
        'stats': stats,
    })


@login_required
@require_POST
def word_quiz_reset(request):
    Word.objects.filter(user=request.user).update(mastered=False, times_asked=0, times_correct=0)
    messages.success(request, _('Quiz ilerlemen sıfırlandı.'))
    return redirect('vocabulary:list')
