"""Halka açık (login gerektirmeyen) içerik sayfaları + robots.txt.

Uygulamanın kendi `/topics/`, `/wordbank/` akışları interaktif ve login'e
bağlı kalır; buradaki sayfalar aynı içeriğin arama motorlarına açık,
okunabilir sürümüdür. Böylece indekslenebilir yüzey büyür, ürün akışı
değişmez.
"""
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import get_language, gettext_lazy as _

from apps.interviews.models import JOB_CATEGORIES
from apps.topics.models import Topic
from apps.wordbank.models import BankWord

WORDS_PER_PAGE = 100

LEVEL_BLURBS = {
    'A1': _('Başlangıç seviyesi. Günlük hayatın en sık geçen temel kelimeleri.'),
    'A2': _('Temel seviye. Basit konuşmaları ve kısa metinleri anlamak için gereken kelimeler.'),
    'B1': _('Orta seviye. İş ve okul hayatında sık kullanılan kelimeler.'),
    'B2': _('Orta-üst seviye. Soyut konuları ve teknik metinleri takip etmeni sağlayan kelimeler.'),
    'C1': _('İleri seviye. Akademik ve profesyonel bağlamlarda geçen kelimeler.'),
    'C2': _('Usta seviye. Deyimsel, akademik ve nadir kullanılan kelimeler.'),
}


def _level_stats():
    counts = {
        row['level']: row['c']
        for row in BankWord.objects.values('level').annotate(c=Count('id'))
    }
    return [
        {
            'code': code,
            'total': counts.get(code, 0),
            'blurb': LEVEL_BLURBS.get(code, ''),
        }
        for code, _label in BankWord.LEVELS
        if counts.get(code)
    ]


# ------------------------------------------------------------------ gramer

def grammar_index(request):
    topics = list(Topic.objects.all().order_by('order', 'name'))
    return render(request, 'seo/grammar_index.html', {
        'topics': topics,
        'total': len(topics),
    })


def grammar_detail(request, slug):
    topic = get_object_or_404(Topic, slug=slug)
    examples = list(topic.examples.all())
    ordered = list(Topic.objects.all().order_by('order', 'name'))
    idx = next((i for i, t in enumerate(ordered) if t.pk == topic.pk), 0)
    explanation, explanation_lang = topic.explanation_for(get_language())
    return render(request, 'seo/grammar_detail.html', {
        'topic': topic,
        'explanation': explanation,
        'explanation_lang': explanation_lang,
        'positives': [e for e in examples if e.kind == 'positive'],
        'negatives': [e for e in examples if e.kind == 'negative'],
        'questions': [e for e in examples if e.kind == 'question'],
        'example_count': len(examples),
        'prev_topic': ordered[idx - 1] if idx > 0 else None,
        'next_topic': ordered[idx + 1] if idx + 1 < len(ordered) else None,
        'siblings': [t for t in ordered if t.pk != topic.pk][:12],
    })


# ---------------------------------------------------------------- kelimeler

def words_index(request):
    levels = _level_stats()
    return render(request, 'seo/words_index.html', {
        'levels': levels,
        'total': sum(item['total'] for item in levels),
    })


def words_level(request, level):
    code = level.upper()
    valid = {c for c, _ in BankWord.LEVELS}
    if code not in valid:
        raise Http404('bilinmeyen seviye')

    qs = BankWord.objects.filter(level=code).order_by('rank', 'english')
    paginator = Paginator(qs, WORDS_PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'seo/words_level.html', {
        'level': code,
        'blurb': LEVEL_BLURBS.get(code, ''),
        'page_obj': page,
        'paginator': paginator,
        'total': paginator.count,
        # Sıra numarası listede kesintisiz aksın: DB'deki rank alanı seyrek.
        'offset': (page.number - 1) * WORDS_PER_PAGE + 1,
        'levels': _level_stats(),
    })


# ----------------------------------------------------------------- mülakat

def interview_index(request):
    categories = [
        {'code': code, 'label': label}
        for code, label in JOB_CATEGORIES
        if code != 'custom'
    ]
    return render(request, 'seo/interview_index.html', {
        'categories': categories,
        'total': len(categories),
    })


# ------------------------------------------------------------- site haritası

def html_sitemap(request):
    """İnsan ve tarayıcı için tek sayfalık dizin — derin sayfalara giden yol."""
    return render(request, 'seo/html_sitemap.html', {
        'topics': Topic.objects.all().order_by('order', 'name'),
        'levels': _level_stats(),
    })


# ---------------------------------------------------------------- robots.txt

def robots_txt(request):
    return render(
        request,
        'seo/robots.txt',
        {'site_url': settings.SITE_URL},
        content_type='text/plain; charset=utf-8',
    )


# ------------------------------------------------------------- hata sayfaları

def not_found(request, exception=None):
    """Soft 404 yerine gerçek 404 + kullanıcıyı içeride tutan bağlantılar."""
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)
