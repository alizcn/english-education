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

from apps.accounts.services import current_pair
from services import claude_client as claude
from . import services as vocab_services
from .models import Word

logger = logging.getLogger(__name__)


@login_required
def word_list(request):
    pair = current_pair(request)
    q = request.GET.get('q', '').strip()
    words = vocab_services.user_words(request.user, pair.target_code)
    if q:
        words = words.filter(Q(term__icontains=q) | Q(meaning__icontains=q))
    stats = vocab_services.personal_stats(request.user, pair.target_code)
    return render(request, 'vocabulary/list.html', {
        'words': words, 'q': q, 'stats': stats, 'pair': pair,
    })


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

        pair = current_pair(request)
        try:
            items = claude.generate_lexicon_entries(words, pair=pair)
        except claude.ClaudeClientError as e:
            messages.error(request, str(e))
            return render(request, 'vocabulary/add.html', {'raw': raw, 'source': source})
        except Exception:
            logger.exception('bulk_add: unexpected AI failure')
            messages.error(request, _('AI çeviri sırasında beklenmedik bir hata oluştu.'))
            return render(request, 'vocabulary/add.html', {'raw': raw, 'source': source})

        with transaction.atomic():
            created = 0
            skipped = 0
            dropped = 0
            for it in items:
                term = (it.get('term') or '').strip().lower()
                meaning = (it.get('meaning') or '').strip()
                if not term or not meaning:
                    dropped += 1
                    continue
                obj, was_created = Word.objects.get_or_create(
                    user=request.user,
                    target_language=pair.target_code,
                    term=term,
                    defaults={
                        'native_language': pair.native_code,
                        'meaning': meaning,
                        'example': (it.get('example') or '').strip(),
                        'example_translation': (it.get('example_translation') or '').strip(),
                        'part_of_speech': (it.get('part_of_speech') or '').strip()[:30],
                        'source': source[:80],
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

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
        new_term = request.POST.get('term', word.term).strip().lower()
        new_meaning = request.POST.get('meaning', '').strip()
        if not new_term or not new_meaning:
            messages.error(request, _('Terim ve anlam alanları boş olamaz.'))
            return render(request, 'vocabulary/edit.html', {'word': word})
        if new_term != word.term and Word.objects.filter(
            user=request.user, target_language=word.target_language, term=new_term,
        ).exclude(pk=word.pk).exists():
            messages.error(request, _('Bu kelime zaten kayıtlı.'))
            return render(request, 'vocabulary/edit.html', {'word': word})
        word.term = new_term
        word.meaning = new_meaning
        word.example = request.POST.get('example', '').strip()
        word.example_translation = request.POST.get('example_translation', '').strip()
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
    pair = current_pair(request)
    stats = vocab_services.personal_stats(request.user, pair.target_code)
    if stats['total'] < vocab_services.MIN_WORDS_FOR_QUIZ:
        messages.error(
            request,
            _('Quiz için en az %(min)d kelime gerekli. Şu an: %(total)d.')
            % {'min': vocab_services.MIN_WORDS_FOR_QUIZ, 'total': stats['total']}
        )
        return redirect('vocabulary:list')

    word, is_retry = vocab_services.pick_next(request.user, pair.target_code)

    if word is None:
        return render(request, 'vocabulary/quiz_complete.html', {'stats': stats})

    options = vocab_services.build_question(word, request.user)
    return render(request, 'vocabulary/quiz.html', {
        'word': word,
        'options': options,
        'is_retry': is_retry,
        'stats': stats,
        'pair': pair,
    })


@login_required
@require_POST
def word_quiz_answer(request):
    pair = current_pair(request)
    word_id = request.POST.get('word_id')
    selected = request.POST.get('answer', '').strip()
    word = get_object_or_404(Word, pk=word_id, user=request.user)

    is_correct = (selected == (word.meaning or '').strip())
    vocab_services.record_answer(word, is_correct)
    stats = vocab_services.personal_stats(request.user, pair.target_code)

    return render(request, 'vocabulary/quiz_feedback.html', {
        'word': word,
        'selected': selected,
        'is_correct': is_correct,
        'stats': stats,
    })


@login_required
@require_POST
def word_quiz_reset(request):
    pair = current_pair(request)
    Word.objects.filter(
        user=request.user, target_language=pair.target_code,
    ).update(mastered=False, times_asked=0, times_correct=0)
    messages.success(request, _('Quiz ilerlemen sıfırlandı.'))
    return redirect('vocabulary:list')
