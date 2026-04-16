import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.vocabulary.models import Word
from apps.topics.models import Topic, TopicCompletion
from apps.quizzes.models import QuizSession
from apps.wordbank.models import BankWord, BankProgress


def _weekly_chart_data(user):
    today = timezone.now().date()
    start = today - timedelta(days=6)
    day_labels = []
    day_names = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
    for i in range(7):
        d = start + timedelta(days=i)
        day_labels.append(day_names[d.weekday()])

    bank_qs = (
        BankProgress.objects.filter(
            user=user, mastered=True,
            last_answered_at__date__gte=start,
        )
        .annotate(day=TruncDate('last_answered_at'))
        .values('day')
        .annotate(count=Count('id'))
    )
    bank_by_day = {r['day']: r['count'] for r in bank_qs}

    personal_qs = (
        Word.objects.filter(
            user=user, mastered=True,
        )
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
    )
    personal_by_day = {r['day']: r['count'] for r in personal_qs}

    bank_data = []
    personal_data = []
    for i in range(7):
        d = start + timedelta(days=i)
        bank_data.append(bank_by_day.get(d, 0))
        personal_data.append(personal_by_day.get(d, 0))

    return {
        'labels': json.dumps(day_labels),
        'bank_data': json.dumps(bank_data),
        'personal_data': json.dumps(personal_data),
        'has_data': any(v > 0 for v in bank_data + personal_data),
    }


def home(request):
    if not request.user.is_authenticated:
        return render(request, 'dashboard/landing.html')
    return _dashboard(request)


def _dashboard(request):
    user = request.user
    total_words = Word.objects.filter(user=user).count()

    topics = list(Topic.objects.all())
    total_topics = len(topics)
    completed_ids = set(
        TopicCompletion.objects.filter(user=user).values_list('topic_id', flat=True)
    )
    done_topics = sum(1 for t in topics if t.id in completed_ids)
    for t in topics:
        t.is_completed_for_user = t.id in completed_ids
    pending_topics = [t for t in topics if not t.is_completed_for_user][:5]

    recent_quizzes = QuizSession.objects.filter(
        user=user, finished_at__isnull=False
    ).order_by('-finished_at')[:5]

    bank_levels = []
    bank_total = BankWord.objects.count()
    bank_mastered_total = BankProgress.objects.filter(user=user, mastered=True).count()
    for code, _ in BankWord.LEVELS:
        total = BankWord.objects.filter(level=code).count()
        mastered = BankProgress.objects.filter(
            user=user, word__level=code, mastered=True,
        ).count()
        bank_levels.append({
            'code': code,
            'total': total,
            'mastered': mastered,
        })
    bank_percent = round(100 * bank_mastered_total / bank_total) if bank_total else 0

    chart = _weekly_chart_data(user)

    return render(request, 'dashboard/home.html', {
        'total_words': total_words,
        'total_topics': total_topics,
        'done_topics': done_topics,
        'topic_percent': round(100 * done_topics / total_topics) if total_topics else 0,
        'pending_topics': pending_topics,
        'recent_quizzes': recent_quizzes,
        'bank_total': bank_total,
        'bank_mastered': bank_mastered_total,
        'bank_percent': bank_percent,
        'bank_levels': bank_levels,
        'chart': chart,
    })
