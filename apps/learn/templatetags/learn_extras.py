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
