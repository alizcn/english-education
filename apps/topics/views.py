from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.services import current_pair

from .models import Topic, TopicCompletion


@login_required
def topic_list(request):
    pair = current_pair(request)
    topics = list(Topic.objects.filter(language=pair.target_code))
    total = len(topics)
    completed_ids = set(
        TopicCompletion.objects.filter(user=request.user).values_list('topic_id', flat=True)
    )
    for t in topics:
        t.is_completed_for_user = t.id in completed_ids
    done = sum(1 for t in topics if t.is_completed_for_user)
    return render(request, 'topics/list.html', {
        'topics': topics,
        'total': total,
        'done': done,
        'percent': round(100 * done / total) if total else 0,
        'pair': pair,
    })


@login_required
def topic_detail(request, slug):
    pair = current_pair(request)
    topic = get_object_or_404(Topic, slug=slug, language=pair.target_code)
    is_completed = TopicCompletion.objects.filter(user=request.user, topic=topic).exists()
    examples = topic.examples.all()
    # Anlatım dili kursun ANA DİLİ, arayüz dili değil: kullanıcı arayüzü
    # çevirdiğinde dersin ortasında anlatımını kaybetmemeli.
    explanation, explanation_lang = topic.explanation_for(pair.native_code)
    return render(request, 'topics/detail.html', {
        'topic': topic,
        'explanation': explanation,
        'explanation_lang': explanation_lang,
        'sections': topic.explanation_sections(pair.native_code),
        'is_completed': is_completed,
        'positives': [e for e in examples if e.kind == 'positive'],
        'negatives': [e for e in examples if e.kind == 'negative'],
        'questions': [e for e in examples if e.kind == 'question'],
        'pair': pair,
    })


@login_required
@require_POST
def toggle_done(request, slug):
    pair = current_pair(request)
    topic = get_object_or_404(Topic, slug=slug, language=pair.target_code)
    tc = TopicCompletion.objects.filter(user=request.user, topic=topic).first()
    if tc:
        tc.delete()
        messages.success(request, _('"%(name)s" tekrar aktif.') % {'name': topic.name})
    else:
        TopicCompletion.objects.create(user=request.user, topic=topic)
        messages.success(request, _('"%(name)s" bitti olarak işaretlendi.') % {'name': topic.name})
    return redirect('topics:detail', slug=topic.slug)
