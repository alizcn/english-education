import logging
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.services import current_pair
from apps.topics.models import Topic
from apps.vocabulary.models import Word
from . import services as quiz_services
from . import tasks
from .answers import check_answer
from .models import QuizSession, QuizQuestion, QuizTemplate
from .normalization import normalize_item

logger = logging.getLogger(__name__)


MIN_WORDS_FOR_QUIZ = 10


# Cevap karşılaştırma `answers.py`ye taşındı: request'ten bağımsız ve birim
# test edilebilir olması gerekiyordu (eskiden hiç testi yoktu) ve Türkçe harf
# whitelist'i Fransızca/Almanca'da yanlış-negatif üretiyordu.


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
        t.is_seed = t.user_id is None
    return templates


@login_required
def word_picker(request):
    pair = current_pair(request)
    total_words = Word.objects.filter(
        user=request.user, target_language=pair.target_code,
    ).count()
    if total_words < MIN_WORDS_FOR_QUIZ:
        messages.error(
            request,
            _('Kelime quizi için en az %(min)d kelime gerekli. Şu an: %(total)d.')
            % {'min': MIN_WORDS_FOR_QUIZ, 'total': total_words}
        )
        return redirect('vocabulary:list')

    templates = list(QuizTemplate.objects.filter(
        user=request.user, kind=QuizTemplate.WORD,
        target_language=pair.target_code, native_language=pair.native_code,
    ))
    _annotate_completion(request.user, templates)

    return render(request, 'quizzes/picker.html', {
        'templates': templates,
        'title': _('Kelime Quizleri'),
        'subtitle': _('Henüz AI quizin yoksa "Yeni Quiz Oluştur"a bas.'),
        'topic': None,
        'can_generate': True,
        'generate_url': 'quizzes:generate_word',
        'pair': pair,
    })


@login_required
def topic_picker(request, slug):
    pair = current_pair(request)
    topic = get_object_or_404(Topic, slug=slug, language=pair.target_code)
    templates = list(
        QuizTemplate.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            kind=QuizTemplate.TOPIC,
            topic=topic,
            native_language=pair.native_code,
        ).order_by('user_id', 'created_at')
    )
    _annotate_completion(request.user, templates)

    return render(request, 'quizzes/picker.html', {
        'templates': templates,
        'title': _('%(name)s Quizleri') % {'name': topic.name},
        'subtitle': _('Varsayılan quiz her zaman burada. Bitirdikten sonra AI ile yenisini üretebilirsin.'),
        'topic': topic,
        'can_generate': True,
        'generate_url': 'quizzes:generate_topic',
        'pair': pair,
    })


def _create_session_for_template(user, template):
    raw_items = template.questions_data or []
    items = [normalize_item(it) for it in raw_items if isinstance(it, dict)]
    items = [
        it for it in items
        if (it.get('prompt') or '').strip() and (it.get('correct_answer') or '').strip()
        and (it.get('question_type') != 'multiple_choice' or (it.get('choices') and len(it['choices']) >= 2))
    ]
    if not items:
        return None

    with transaction.atomic():
        session = QuizSession.objects.create(
            user=user,
            template=template,
            kind=template.kind,
            topic=template.topic,
            target_language=template.target_language,
            native_language=template.native_language,
            total_questions=len(items),
        )
        words_by_term = {}
        if template.kind == QuizTemplate.WORD:
            words_by_term = {
                w.term.lower(): w
                for w in Word.objects.filter(
                    user=user, target_language=template.target_language,
                )
            }
        for i, it in enumerate(items):
            word = None
            if template.kind == QuizTemplate.WORD:
                # `english_word` eski sözleşme; `term` yenisi. İkisini de
                # okuyoruz çünkü repoda kayıtlı seed JSON'ları ve kullanıcıların
                # halihazırda üretilmiş şablonları eski anahtarı taşıyor.
                term = (it.get('term') or it.get('english_word') or '').strip().lower()
                word = words_by_term.get(term)
            QuizQuestion.objects.create(
                session=session,
                order=i,
                question_type=it.get('question_type') or QuizQuestion.TRANSLATE_TO_NATIVE,
                prompt=it.get('prompt') or '',
                correct_answer=it.get('correct_answer') or '',
                choices=it.get('choices'),
                word=word,
            )
    return session


def _has_pending(user, kind, topic=None, *, target_language) -> bool:
    return QuizTemplate.objects.filter(
        user=user, kind=kind, topic=topic,
        target_language=target_language, status=QuizTemplate.PENDING,
    ).exists()


@login_required
@require_POST
def generate_topic_quiz_view(request, slug):
    """Üretimi kuyruğa atıp hemen döner — eskiden burada ~100s bloke oluyorduk."""
    pair = current_pair(request)
    topic = get_object_or_404(Topic, slug=slug, language=pair.target_code)
    if _has_pending(request.user, QuizTemplate.TOPIC, topic=topic,
                    target_language=pair.target_code):
        messages.info(request, _('Zaten hazırlanan bir quiz var, birazdan görünecek.'))
        return redirect('quizzes:topic_picker', slug=slug)

    tmpl = QuizTemplate.objects.create(
        user=request.user,
        kind=QuizTemplate.TOPIC,
        topic=topic,
        target_language=pair.target_code,
        native_language=pair.native_code,
        name=quiz_services.next_template_name(
            request.user, QuizTemplate.TOPIC, topic=topic,
            target_language=pair.target_code,
        ),
        status=QuizTemplate.PENDING,
    )
    tasks.generate_topic_template.delay(
        tmpl.pk, topic.pk, pair.target_code, pair.native_code,
    )
    messages.success(request, _('Quiz hazırlanıyor. Sorular hazırlandıkça burada görünecek.'))
    return redirect('quizzes:topic_picker', slug=slug)


@login_required
@require_POST
def generate_word_quiz(request):
    pair = current_pair(request)
    total_words = Word.objects.filter(
        user=request.user, target_language=pair.target_code,
    ).count()
    if total_words < MIN_WORDS_FOR_QUIZ:
        messages.error(
            request,
            _('Kelime quizi için en az %(min)d kelime gerekli. Şu an: %(total)d.')
            % {'min': MIN_WORDS_FOR_QUIZ, 'total': total_words}
        )
        return redirect('vocabulary:list')
    if _has_pending(request.user, QuizTemplate.WORD, target_language=pair.target_code):
        messages.info(request, _('Zaten hazırlanan bir quiz var, birazdan görünecek.'))
        return redirect('quizzes:word_picker')

    tmpl = QuizTemplate.objects.create(
        user=request.user,
        kind=QuizTemplate.WORD,
        target_language=pair.target_code,
        native_language=pair.native_code,
        name=quiz_services.next_template_name(
            request.user, QuizTemplate.WORD, target_language=pair.target_code,
        ),
        status=QuizTemplate.PENDING,
    )
    tasks.generate_word_template.delay(
        tmpl.pk, request.user.pk, pair.target_code, pair.native_code,
    )
    messages.success(request, _('Quiz hazırlanıyor. Sorular hazırlandıkça burada görünecek.'))
    return redirect('quizzes:word_picker')


@login_required
def template_status(request, template_id):
    """Picker sayfası hazırlanan quizi buradan yokluyor."""
    template = get_object_or_404(QuizTemplate, pk=template_id, user=request.user)
    return JsonResponse({
        'status': template.status,
        'ready_count': template.question_count,
        'total': tasks.QUESTION_TARGET,
    })


@login_required
@require_POST
def start_template(request, template_id):
    template = get_object_or_404(
        QuizTemplate.objects.filter(Q(user=request.user) | Q(user__isnull=True)),
        pk=template_id,
    )
    fallback = (
        redirect('quizzes:topic_picker', slug=template.topic.slug)
        if template.topic_id else redirect('quizzes:word_picker')
    )
    if not template.is_ready:
        # Yarım şablonla oturum açmak kullanıcıya eksik quiz verir.
        messages.error(request, _('Bu quiz henüz hazır değil.'))
        return fallback
    session = _create_session_for_template(request.user, template)
    if not session:
        messages.error(request, _('Bu quiz şablonu boş.'))
        return fallback
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
    verdict = check_answer(user_answer, question.correct_answer)
    correct = verdict.is_correct

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
        # Aksan/diakritik eksikse cevap doğru sayılıyor ama ipucu gösteriliyor:
        # Fransızca ve Almanca'da bu gerçek bir öğrenme sinyali.
        'diacritics_hint': verdict.diacritics_only,
    })


@login_required
def result(request, pk):
    session = get_object_or_404(QuizSession, pk=pk, user=request.user)
    if not session.is_finished:
        session.finished_at = timezone.now()
        session.save(update_fields=['finished_at'])

    wrong_questions = session.questions.filter(is_correct=False).order_by('order')

    if session.kind == QuizTemplate.TOPIC and session.topic:
        generate_url = ('quizzes:generate_topic', {'slug': session.topic.slug})
    else:
        generate_url = ('quizzes:generate_word', {})

    return render(request, 'quizzes/result.html', {
        'session': session,
        'wrong_questions': wrong_questions,
        'generate_url_name': generate_url[0],
        'generate_url_kwargs': generate_url[1],
    })
