"""Dil adlarını arayüz metinlerine çekimli basan etiketler.

Niçin düz değişken yetmiyor: Türkçe'de dil adı hâl eki alıyor ve ek, adın son
ünlüsüne göre değişiyor — "İngilizce**yi** öğren" ama "Almanca**yı** öğren".
`{% blocktrans %}{{ lang }} öğren{% endblocktrans %}` kalıbı bu yüzden dört
dilin üçünde bozuk gramer üretir. Çekimli biçimler sicilde önceden yazılı
(`LangSpec.display`), bu etiketler oradan okuyor.

Kullanım::

    {% load learn_extras %}
    {% target_name 'acc' %} öğrenmeye devam et      -> "İngilizceyi öğrenmeye…"
    {% native_name %} anlatımlı                      -> "Türkçe anlatımlı"
    {% lang_name 'de' 'loc' %} nasıl denir            -> "Almancada nasıl denir"

Hâl anahtarları `services.languages.CASES` ile aynı; bulunmayan hâl yalın
biçime düşüyor, yani İngilizce arayüzde `'acc'` istemek güvenli.
"""

from django import template
from django.utils.translation import get_language

from apps.learn.current import get_current_target_or_default
from services import languages

register = template.Library()


def _ui_language():
    """Geçerli arayüz dili — adların hangi dilde yazılacağını belirler."""
    return (get_language() or '').split('-')[0] or 'en'


@register.simple_tag(takes_context=True)
def target_name(context, case='nom'):
    """Aktif kursun HEDEF dilinin adı (öğrenilen dil)."""
    request = context.get('request')
    code = getattr(request, 'target_language', None) or get_current_target_or_default()
    return languages.display_name(code, in_language=_ui_language(), case=case)


@register.simple_tag(takes_context=True)
def native_name(context, case='nom'):
    """Aktif kursun ANA dilinin adı (anlatımın yazıldığı dil).

    Kurs yoksa arayüz diline düşüyor: anlatım dili seçilmemişken kullanıcının
    okuduğu dil arayüz dilidir.
    """
    request = context.get('request')
    code = getattr(request, 'native_language', None) or _ui_language()
    return languages.display_name(code, in_language=_ui_language(), case=case)


@register.simple_tag
def lang_name(code, case='nom'):
    """Herhangi bir dilin adı — katalog ve giriş sayfalarında kullanılıyor."""
    try:
        return languages.display_name(code, in_language=_ui_language(), case=case)
    except languages.UnknownLanguage:
        return code


@register.simple_tag
def learnable_languages():
    """Yayındaki öğrenilebilir diller — kurs seçicide dönülüyor."""
    return languages.LEARNABLE_LANGUAGES


SHOWCASE_LEVELS = ('A1', 'A2', 'B1')


@register.simple_tag
def showcase_words(target, count=30, fallback=False):
    """Landing'deki kelime şeridi ve canlı quiz için gerçek kelimeler.

    Ana dil arayüz dili. Hedef ile aynıysa (İngilizce arayüzde İngilizce)
    anlam yok: `fallback` açıksa (dört dili tanıtan genel ana sayfa) başka bir
    öğrenilebilir dile geçilir, kapalıysa liste boş döner ve şablon bölümleri
    gizler. Saatte bir yenileniyor.
    """
    from django.core.cache import cache
    from apps.wordbank.models import BankWord

    native = _ui_language()
    if native == target:
        if not fallback:
            return []
        target = next((c for c in languages.LEARNABLE_CODES if c != native), None)
        if not target:
            return []
    key = f'showcase_words:{target}:{native}:{count}'
    words = cache.get(key)
    if words is not None:
        return words
    qs = (BankWord.objects
          .filter(language=target, level__in=SHOWCASE_LEVELS,
                  translations__language=native)
          .exclude(example='')
          .prefetch_related('translations')
          .order_by('?')[:count])
    words = []
    for w in qs:
        tr = w.translation_for(native)
        if not tr:
            continue
        meaning = tr.meaning.split(',')[0].split(';')[0].strip()
        if not meaning or len(meaning) > 32 or len(w.term) > 22:
            continue
        words.append({
            'lang': target,
            'term': w.term,
            'level': w.level,
            'meaning': meaning,
            'example': w.example,
            'example_translation': tr.example_translation,
        })
    cache.set(key, words, 3600)
    return words
