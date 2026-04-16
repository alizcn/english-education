from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Topic, TopicCompletion


@login_required
def topic_list(request):
    topics = list(Topic.objects.all())
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
    })


@login_required
def topic_detail(request, slug):
    topic = get_object_or_404(Topic, slug=slug)
    is_completed = TopicCompletion.objects.filter(user=request.user, topic=topic).exists()
    examples = topic.examples.all()
    positives = [e for e in examples if e.kind == 'positive']
    negatives = [e for e in examples if e.kind == 'negative']
    questions = [e for e in examples if e.kind == 'question']
    return render(request, 'topics/detail.html', {
        'topic': topic,
        'is_completed': is_completed,
        'positives': positives,
        'negatives': negatives,
        'questions': questions,
    })


@login_required
@require_POST
def toggle_done(request, slug):
    topic = get_object_or_404(Topic, slug=slug)
    tc = TopicCompletion.objects.filter(user=request.user, topic=topic).first()
    if tc:
        tc.delete()
        messages.success(request, f'"{topic.name}" tekrar aktif.')
    else:
        TopicCompletion.objects.create(user=request.user, topic=topic)
        messages.success(request, f'"{topic.name}" bitti olarak işaretlendi.')
    return redirect('topics:detail', slug=topic.slug)
