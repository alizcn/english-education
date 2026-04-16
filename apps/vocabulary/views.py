import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from services import ai
from . import services as vocab_services
from .models import Word


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
def bulk_add(request):
    if request.method == 'POST':
        raw = request.POST.get('words', '')
        source = request.POST.get('source', '').strip()
        words = _parse_input(raw)

        if not words:
            messages.error(request, 'Hiç kelime girmedin.')
            return redirect('vocabulary:bulk_add')

        try:
            items = ai.translate_words(words)
        except Exception as e:
            messages.error(request, f'AI çeviri hatası: {e}')
            return render(request, 'vocabulary/add.html', {'raw': raw, 'source': source})

        created = 0
        skipped = 0
        for it in items:
            eng = (it.get('english') or '').strip().lower()
            if not eng:
                continue
            obj, was_created = Word.objects.get_or_create(
                user=request.user,
                english=eng,
                defaults={
                    'turkish': (it.get('turkish') or '').strip(),
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

        messages.success(
            request,
            f'{created} kelime eklendi.' + (f' ({skipped} tanesi zaten vardı.)' if skipped else '')
        )
        return redirect('vocabulary:list')

    return render(request, 'vocabulary/add.html', {'raw': '', 'source': ''})


@login_required
def word_edit(request, pk):
    word = get_object_or_404(Word, pk=pk, user=request.user)
    if request.method == 'POST':
        word.english = request.POST.get('english', word.english).strip().lower()
        word.turkish = request.POST.get('turkish', '').strip()
        word.example_en = request.POST.get('example_en', '').strip()
        word.example_tr = request.POST.get('example_tr', '').strip()
        word.part_of_speech = request.POST.get('part_of_speech', '').strip()[:30]
        word.source = request.POST.get('source', '').strip()[:80]
        word.save()
        messages.success(request, 'Kaydedildi.')
        return redirect('vocabulary:list')
    return render(request, 'vocabulary/edit.html', {'word': word})


@login_required
@require_POST
def word_delete(request, pk):
    word = get_object_or_404(Word, pk=pk, user=request.user)
    word.delete()
    messages.success(request, 'Silindi.')
    return redirect('vocabulary:list')


@login_required
def word_quiz(request):
    stats = vocab_services.personal_stats(request.user)
    if stats['total'] < vocab_services.MIN_WORDS_FOR_QUIZ:
        messages.error(
            request,
            f'Quiz için en az {vocab_services.MIN_WORDS_FOR_QUIZ} kelime gerekli. Şu an: {stats["total"]}.'
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

    is_correct = (selected == word.turkish)
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
    messages.success(request, 'Quiz ilerlemen sıfırlandı.')
    return redirect('vocabulary:list')
