from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.vocabulary.models import Word
from apps.topics.models import Topic, TopicCompletion
from apps.quizzes.models import QuizSession
from apps.wordbank.models import BankWord, BankProgress


@login_required
def home(request):
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
    })
