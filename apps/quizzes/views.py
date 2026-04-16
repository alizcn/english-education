import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.topics.models import Topic
from apps.vocabulary.models import Word
from . import services as quiz_services
from .models import QuizSession, QuizQuestion, QuizTemplate
from .normalization import normalize_item


MIN_WORDS_FOR_QUIZ = 10


def _normalize(s: str) -> str:
    s = (s or '').strip().lower()
    s = re.sub(r"[^\w\sğüşıöçİĞÜŞÖÇ'-]", '', s, flags=re.UNICODE)
    s = re.sub(r'\s+', ' ', s)
    return s


def _is_answer_correct(user: str, correct: str) -> bool:
    if not user:
        return False
    u = _normalize(user)
    c = _normalize(correct)
    if u == c:
        return True
    alternatives = [_normalize(a) for a in re.split(r'\s*/\s*', correct)]
    return u in alternatives


def _annotate_completion(user, templates):
    finished_ids = set(
        QuizSession.objects.filter(
            user=user, template__in=templates, finished_at__isnull=False,
        ).values_list('template_id', flat=True)
    )
    last_sessions = {}
    for s in QuizSession.objects.filter(
        user=user, template__in=templates, finished_at__isnull=False,
    ).order_by('-finished_at'):
        if s.template_id not in last_sessions:
            last_sessions[s.template_id] = s
    for t in templates:
        t.is_completed = t.id in finished_ids
        t.last_session = last_sessions.get(t.id)
    return templates


@login_required
def word_picker(request):
    total_words = Word.objects.filter(user=request.user).count()
    if total_words < MIN_WORDS_FOR_QUIZ:
        messages.error(
            request,
            _('Kelime quizi için en az %(min)d kelime gerekli. Şu an: %(total)d.')
            % {'min': MIN_WORDS_FOR_QUIZ, 'total': total_words}
        )
        return redirect('vocabulary:list')

    try:
        quiz_services.ensure_at_least_one(request.user, QuizTemplate.WORD)
    except Exception as e:
        messages.error(request, _('AI hata: %(error)s') % {'error': e})

    templates = list(QuizTemplate.objects.filter(user=request.user, kind=QuizTemplate.WORD))
    _annotate_completion(request.user, templates)

    return render(request, 'quizzes/picker.html', {
        'templates': templates,
        'title': _('Kelime Quizleri'),
        'subtitle': _('Havuzdaki quizlerden birini seç. Hepsini çözdüğünde AI yenisini ekler.'),
        'pool_target': quiz_services.POOL_TARGET,
        'topic': None,
    })


@login_required
def topic_picker(request, slug):
    topic = get_object_or_404(Topic, slug=slug)
    try:
        quiz_services.ensure_at_least_one(request.user, QuizTemplate.TOPIC, topic=topic)
    except Exception as e:
        messages.error(request, _('AI hata: %(error)s') % {'error': e})

    templates = list(
        QuizTemplate.objects.filter(user=request.user, kind=QuizTemplate.TOPIC, topic=topic)
    )
    _annotate_completion(request.user, templates)

    return render(request, 'quizzes/picker.html', {
        'templates': templates,
        'title': _('%(name)s Quizleri') % {'name': topic.name},
        'subtitle': _('Bu konuya özel hazır quizlerden birini seç.'),
        'pool_target': quiz_services.POOL_TARGET,
        'topic': topic,
    })


@login_required
@require_POST
def start_template(request, template_id):
    template = get_object_or_404(QuizTemplate, pk=template_id, user=request.user)
    raw_items = template.questions_data or []
    items = [normalize_item(it) for it in raw_items if isinstance(it, dict)]
    items = [
        it for it in items
        if (it.get('prompt') or '').strip() and (it.get('correct_answer') or '').strip()
        and (it.get('question_type') != 'multiple_choice' or (it.get('choices') and len(it['choices']) >= 2))
    ]
    if not items:
        messages.error(request, _('Bu quiz şablonu boş.'))
        return redirect('quizzes:word_picker')

    with transaction.atomic():
        session = QuizSession.objects.create(
            user=request.user,
            template=template,
            kind=template.kind,
            topic=template.topic,
            total_questions=len(items),
        )
        words_by_en = {}
        if template.kind == QuizTemplate.WORD:
            words_by_en = {
                w.english.lower(): w for w in Word.objects.filter(user=request.user)
            }
        for i, it in enumerate(items):
            word = None
            if template.kind == QuizTemplate.WORD:
                en = (it.get('english_word') or '').strip().lower()
                word = words_by_en.get(en)
            QuizQuestion.objects.create(
                session=session,
                order=i,
                question_type=it.get('question_type') or QuizQuestion.TRANSLATE_EN_TR,
                prompt=it.get('prompt') or '',
                correct_answer=it.get('correct_answer') or '',
                choices=it.get('choices'),
                word=word,
            )
    return redirect('quizzes:run', pk=session.pk)


@login_required
def run_quiz(request, pk):
    session = get_object_or_404(QuizSession, pk=pk, user=request.user)
    if session.is_finished:
        return redirect('quizzes:result', pk=pk)

    next_q = session.questions.filter(is_correct__isnull=True).order_by('order').first()
    if not next_q:
        session.finished_at = timezone.now()
        session.save(update_fields=['finished_at'])
        return redirect('quizzes:result', pk=pk)

    return render(request, 'quizzes/run.html', {
        'session': session,
        'question': next_q,
        'current_num': session.answered_count + 1,
    })


@login_required
@require_POST
def submit_answer(request, pk):
    session = get_object_or_404(QuizSession, pk=pk, user=request.user)
    question_id = request.POST.get('question_id')
    question = get_object_or_404(QuizQuestion, pk=question_id, session=session)

    if question.is_correct is not None:
        return redirect('quizzes:run', pk=pk)

    user_answer = request.POST.get('answer', '').strip()
    correct = _is_answer_correct(user_answer, question.correct_answer)

    question.user_answer = user_answer
    question.is_correct = correct
    question.answered_at = timezone.now()
    question.save()

    if correct:
        session.correct_count += 1
    else:
        session.wrong_count += 1
    session.save(update_fields=['correct_count', 'wrong_count'])

    if question.word_id:
        updates = {'times_asked': F('times_asked') + 1}
        if correct:
            updates['times_correct'] = F('times_correct') + 1
        Word.objects.filter(pk=question.word_id).update(**updates)

    return render(request, 'quizzes/feedback.html', {
        'session': session,
        'question': question,
        'correct': correct,
    })


@login_required
def result(request, pk):
    session = get_object_or_404(QuizSession, pk=pk, user=request.user)
    just_finished = False
    if not session.is_finished:
        session.finished_at = timezone.now()
        session.save(update_fields=['finished_at'])
        just_finished = True

    if just_finished:
        try:
            quiz_services.replenish_if_needed(
                request.user, session.kind, topic=session.topic,
            )
        except Exception:
            pass

    wrong_questions = session.questions.filter(is_correct=False).order_by('order')
    return render(request, 'quizzes/result.html', {
        'session': session,
        'wrong_questions': wrong_questions,
    })
