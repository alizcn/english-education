"""Halka açık (login gerektirmeyen) içerik sayfaları + robots.txt.

Uygulamanın kendi `/topics/`, `/wordbank/` akışları interaktif ve login'e
bağlı kalır; buradaki sayfalar aynı içeriğin arama motorlarına açık,
okunabilir sürümüdür. Böylece indekslenebilir yüzey büyür, ürün akışı
değişmez.
"""
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.utils.translation import get_language, gettext, gettext_lazy as _

from apps.dashboard import faq

from . import gating
from apps.interviews.models import JOB_CATEGORIES
from services import languages
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


# Varsayılan hedef: sitemap ve HTML site haritası gibi tek dilli yüzeyler
# için. Sayfa view'leri hedefi URL'den (`<target:lang>`) alıyor.
PUBLIC_TARGET = 'en'


def _require_public_pair(lang):
    """Yayında olmayan hedef dil 404.

    Hedef dil ile arayüz dilinin AYNI olması engellenmiyor. Bir ara
    engellemek düşünüldü ("Türkçe konuşana Türkçe öğretmek anlamsız") ama iki
    gerekçe bunu çürütüyor:

    1. `/en/english-grammar/` İNDEKSLİ bir adres ve korunmak zorunda. Self-pair
       yasağı onu 404 yapardı — indekslenmiş bağlantıları kırmak, kazanılacak
       her şeyden pahalı.
    2. İçerik meşru: hedef dilin kendi dilinde anlatımı normal bir gramer
       referansı (tek dilli sözlükler böyle çalışır) ve `TopicExplanation`
       zaten o dilde gövde taşıyabiliyor.

    Yayında olmayan dil kontrolü duruyor: içeriği üretilmemiş bir dil için
    boş sayfa yayınlamak arama motoruna da kullanıcıya da zarar.
    """
    if lang not in languages.LEARNABLE_CODES:
        raise Http404('bu dil henüz öğrenilebilir değil')
    return lang, get_language()


def _level_stats(target_language=PUBLIC_TARGET):
    counts = {
        row['level']: row['c']
        for row in BankWord.objects.filter(language=target_language)
                                   .values('level').annotate(c=Count('id'))
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

def grammar_index(request, lang):
    target, native = _require_public_pair(lang)
    topics = list(Topic.objects.filter(language=target).order_by('order', 'name'))
    return render(request, 'seo/grammar_index.html', {
        'topics': topics,
        'total': len(topics),
        'target_language': target,
        'native_language': native,
    })


def grammar_detail(request, lang, slug):
    target, native = _require_public_pair(lang)
    topic = get_object_or_404(Topic, slug=slug, language=target)
    examples = list(topic.examples.all())
    ordered = list(Topic.objects.filter(language=target).order_by('order', 'name'))
    idx = next((i for i, t in enumerate(ordered) if t.pk == topic.pk), 0)
    # Halka açık sayfada anlatım dili ARAYÜZ dili: ziyaretçinin kursu yok.
    explanation, explanation_lang = topic.explanation_for(get_language())

    # Kayıtsız ziyaretçi anlatımın ilk bölümlerini ve her biçimden birkaç
    # örneği görüyor; gerisi kayda bağlı (bkz. apps/seo/gating.py).
    gated = gating.is_gated(request)
    all_sections = topic.explanation_sections(native)
    positives = [e for e in examples if e.kind == 'positive']
    negatives = [e for e in examples if e.kind == 'negative']
    questions = [e for e in examples if e.kind == 'question']
    shown_examples = sum(
        len(gating.limit(group, gating.PREVIEW_EXAMPLES_PER_KIND, gated))
        for group in (positives, negatives, questions)
    )

    return render(request, 'seo/grammar_detail.html', {
        'topic': topic,
        'explanation': explanation,
        'explanation_lang': explanation_lang,
        'sections': gating.limit(all_sections, gating.PREVIEW_SECTIONS, gated),
        'gated': gated,
        'hidden_sections': max(len(all_sections) - gating.PREVIEW_SECTIONS, 0) if gated else 0,
        'hidden_examples': len(examples) - shown_examples if gated else 0,
        'gated_selector': gating.GATED_SELECTOR,
        'target_language': target,
        'native_language': native,
        'positives': gating.limit(positives, gating.PREVIEW_EXAMPLES_PER_KIND, gated),
        'negatives': gating.limit(negatives, gating.PREVIEW_EXAMPLES_PER_KIND, gated),
        'questions': gating.limit(questions, gating.PREVIEW_EXAMPLES_PER_KIND, gated),
        'example_count': len(examples),
        'prev_topic': ordered[idx - 1] if idx > 0 else None,
        'next_topic': ordered[idx + 1] if idx + 1 < len(ordered) else None,
        'siblings': [t for t in ordered if t.pk != topic.pk][:12],
    })


# ---------------------------------------------------------------- kelimeler

def words_index(request, lang):
    target, native = _require_public_pair(lang)
    levels = _level_stats(target)
    return render(request, 'seo/words_index.html', {
        'levels': levels,
        'total': sum(item['total'] for item in levels),
        'target_language': target,
        'native_language': native,
    })


def words_level(request, lang, level):
    target, native = _require_public_pair(lang)
    code = level.upper()
    # Seviye DİLİN KENDİ listesine karşı doğrulanıyor, global model
    # seçeneklerine karşı değil. Ölçülmüş hata: Türkçe ve Almanca'da C2 yok
    # (resmî CEFR listesi bulunmadığı için sicilde A1–C1), ama global liste
    # C2'yi içerdiği için `/turkish-vocabulary/c2/` SIFIR kelimeyle 200
    # dönüyordu — kullanıcıya boş tablo, arama motoruna içeriksiz sayfa.
    if code not in set(languages.get(target).cefr_levels):
        raise Http404(f'{target} dilinde {code} seviyesi yok')

    qs = (
        BankWord.objects
        .filter(language=target, level=code)
        .prefetch_related('translations')
        .order_by('rank', 'term')
    )
    # Kayıtsız ziyaretçi ilk sayfanın bir bölümünü görüyor; sayfalama da
    # kapanıyor ki "devam" tuşuyla kapı aşılamasın (bkz. apps/seo/gating.py).
    gated = gating.is_gated(request)
    paginator = Paginator(qs, gating.PREVIEW_WORDS if gated else WORDS_PER_PAGE)
    page = paginator.get_page(1 if gated else request.GET.get('page'))
    # Şablon her satırın anlamını arıyor; ana dil arayüz dili.
    for word in page.object_list:
        translation = word.translation_for(native) or word.translations.first()
        word.display_meaning = translation.meaning if translation else ''
        word.display_example_translation = (
            translation.example_translation if translation else ''
        )

    return render(request, 'seo/words_level.html', {
        'level': code,
        'native_language': native,
        'blurb': LEVEL_BLURBS.get(code, ''),
        'page_obj': page,
        'paginator': paginator,
        'total': paginator.count,
        # Sıra numarası listede kesintisiz aksın: DB'deki rank alanı seyrek.
        # `paginator.per_page` okunuyor, sabit WORDS_PER_PAGE değil: kapı
        # açıkken sayfa boyutu PREVIEW_WORDS ve numaralar kayardı.
        'offset': (page.number - 1) * paginator.per_page + 1,
        'levels': _level_stats(target),
        'target_language': target,
        'gated': gated,
        'hidden_words': max(paginator.count - len(page.object_list), 0) if gated else 0,
        'gated_selector': gating.GATED_SELECTOR,
    })


# ----------------------------------------------------------------- mülakat

def interview_index(request, lang):
    target, native = _require_public_pair(lang)
    categories = [
        {'code': code, 'label': label}
        for code, label in JOB_CATEGORIES
        if code != 'custom'
    ]
    return render(request, 'seo/interview_index.html', {
        'categories': categories,
        'total': len(categories),
        'target_language': target,
        'native_language': native,
    })


# ------------------------------------------------- hedef dil giriş sayfaları

def learn_landing(request, lang):
    """`/learn-german/` gibi hedef dil başına indekslenebilir giriş sayfası.

    Öneksiz `/` İngilizce hedefin landing'i olarak KALIYOR (en çok trafik alan
    adres, değiştirmenin getirisi yok). Diğer üç dil kendi H1'i, kendi
    pazarlama metni ve aynı SSS'yle buradan giriyor; metin
    `templates/dashboard/landing/<kod>.html` içinde.

    `/learn-english/` ayrıca yayınlanmıyor: `/` ile birebir aynı içerik olurdu
    ve iki adres aynı metni indekslettirmek demek. `legacy_urls` desenindeki
    gibi kalıcı yönlendirme `urls.py`de.
    """
    target, _native = _require_public_pair(lang)
    return render(request, f'dashboard/landing/{target}.html', {
        'landing_target': target,
        'faq_items': faq.as_dicts(),
        'faq_schema': faq.as_schema_json(),
    })


def licenses(request):
    """Kelime listelerinin kaynak ve lisans atıfları.

    FLELex (CC BY-NC), wordfreq (CC BY-SA 4.0) ve Goethe Wortliste atıf
    istiyor; sayfa bu yüzden var. Tablo sicilden doluyor
    (`LangSpec.wordlist_source` / `license_note`), böylece yeni bir dil
    eklendiğinde atıf da otomatik geliyor.
    """
    return render(request, 'seo/licenses.html', {
        'target_language': PUBLIC_TARGET,
        'native_language': get_language(),
    })


# ------------------------------------------------------------- site haritası

def html_sitemap(request):
    """İnsan ve tarayıcı için tek sayfalık dizin — derin sayfalara giden yol."""
    return render(request, 'seo/html_sitemap.html', {
        'topics': Topic.objects.filter(language=PUBLIC_TARGET).order_by('order', 'name'),
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


def llm_txt(request):
    import os
    from django.http import Http404, HttpResponse
    for static_dir in settings.STATICFILES_DIRS:
        path = os.path.join(str(static_dir), 'llm.txt')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                return HttpResponse(f.read(), content_type='text/plain; charset=utf-8')
    raise Http404


def privacy_policy(request):
    return render(request, 'legal/privacy.html', {
        'target_language': 'en',
    })


def terms_of_service(request):
    return render(request, 'legal/terms.html', {
        'target_language': 'en',
    })


# ------------------------------------------------------------------- manifest

def manifest(request):
    """PWA manifesti — aktif dile göre üretilir.

    Eskiden `static/manifest.json` tek bir dosyaydı: `lang` sabit "tr",
    `name`/`description` Türkçe ve dil değişince hiçbir şey değişmiyordu. Bu
    view `i18n_patterns` içinde yayınlandığı için her dil kendi manifestini
    alıyor; `start_url` ve `scope` da o dilin prefix'ini taşıyor, böylece
    yüklenen uygulama kullanıcının dilinde açılıyor.

    Eski statik dosya bir süre yerinde bırakılıyor: kurulu uygulamalar onu
    cache'lemiş durumda.
    """
    prefix = '' if get_language() == settings.LANGUAGE_CODE else f'/{get_language()}'

    def icon(name, size, purpose='any'):
        return {
            'src': static(f'icons/{name}'),
            'sizes': f'{size}x{size}',
            'type': 'image/png',
            'purpose': purpose,
        }

    def shortcut(name, short_name, path):
        return {
            'name': str(name),
            'short_name': str(short_name),
            'url': f'{prefix}{path}',
            'icons': [icon('icon-192.png', 192)],
        }

    return JsonResponse(
        {
            'name': gettext('LevelEnAI — İngilizce öğren, mülakatı kap'),
            'short_name': settings.SITE_NAME,
            'description': gettext(
                'İngilizce kelime, gramer ve AI destekli mülakat hazırlığı. '
                "A1'den C2'ye 6.000+ kelime, 18 gramer konusu — tamamen ücretsiz."
            ),
            'start_url': f'{prefix}/?utm_source=pwa',
            'id': f'{prefix}/',
            'scope': f'{prefix}/',
            'display': 'standalone',
            'orientation': 'portrait',
            'background_color': '#F4F7F9',
            'theme_color': '#0E7490',
            'lang': get_language(),
            'dir': 'ltr',
            'categories': ['education', 'productivity'],
            'icons': [
                icon('icon-192.png', 192),
                icon('icon-512.png', 512),
                icon('icon-maskable-512.png', 512, 'maskable'),
            ],
            'shortcuts': [
                shortcut(gettext('Mülakat Pratiği'), gettext('Mülakat'), '/interviews/'),
                shortcut(gettext('Kelime Hazinesi'), gettext('Kelime'), '/wordbank/'),
                shortcut(gettext('AI Sohbet'), gettext('Sohbet'), '/chat/'),
            ],
        },
        content_type='application/manifest+json',
        json_dumps_params={'ensure_ascii': False},
    )


# ------------------------------------------------------------- hata sayfaları

def not_found(request, exception=None):
    """Soft 404 yerine gerçek 404 + kullanıcıyı içeride tutan bağlantılar."""
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)
