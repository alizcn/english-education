"""Kurs prefix'i: `/learn/<hedef_dil>/...`

Django'nun `LocalePrefixPattern` + `i18n_patterns` mekanizmasının birebir
klonu, yalnızca eksen farklı: arayüz dili yerine ÖĞRENİLEN dil.

Niçin URL'de:

* Session'da tutmak çok sekmeli kullanımı kırıyor — bir sekmede Almanca,
  diğerinde İngilizce çalışmak çok kurslu olmanın doğal sonucu — ve POST'ları
  belirsizleştiriyor: `/quiz/answer/` isteği hangi kursa puan yazacak? Geri
  tuşu + session, yanlış kursa puan demek.
* Yalnızca profilde tutmak "tek aktif dil" demek, çok kursla çelişiyor.
* URL'de tutmak idempotent, paylaşılabilir ve cache güvenli.

SEO maliyeti sıfır: bu yollar `login_required` ve `base.html` gereği
varsayılan `noindex, follow`.

KRİTİK: prefix aktivasyonu İKİ yerde olmak zorunda —
`CourseMiddleware.process_request` (view için) ve `CoursePrefixPattern.match()`
(burada). İkincisi şart, çünkü `set_language` view'i `translate_url` çağırıyor,
o da `resolve()` + `reverse()` yapıyor; `match()` aktive etmezse `reverse`
prefix'i bilemiyor ve `/learn/de/topics/x/` → `/en/topics/x/` bozuk çıkıyor.
"""

import re

from django.urls import URLResolver, get_resolver
from django.utils.translation import get_language

from services import languages

from .current import activate_target, get_current_target_or_default

PREFIX_ROOT = 'learn'

#: `learn/<iki harfli kod>/`
_PREFIX_RE = re.compile(rf'^{PREFIX_ROOT}/([a-z]{{2}})/')


class CoursePrefixPattern:
    """`learn/<dil>/` önekini eşleyen ve çözerken aktive eden desen."""

    def __init__(self):
        self.converters = {}

    @property
    def regex(self):
        # Yalnızca reverse() kullanıyor ve _reverse_dict'te cache'leniyor.
        return re.compile(re.escape(self.course_prefix))

    @property
    def course_prefix(self):
        # Aktif kurs yoksa varsayılana düşüyoruz: `reverse()` her zaman
        # çözümlenebilir bir yol üretmek zorunda. Boş prefix döndürseydik
        # anonim bir ziyaretçinin menüsündeki `{% url 'topics:list' %}`
        # hiçbir yere gitmeyen `/topics/` üretirdi.
        return f'{PREFIX_ROOT}/{get_current_target_or_default()}/'

    def match(self, path):
        """YALNIZCA açık prefix'i eşler.

        Öneksiz yollar bilinçli olarak eşleşmiyor: `/topics/` gibi eski
        adresler `apps/learn/legacy.py` modülüne düşüp kullanıcının aktif
        kursuna 302 ile taşınıyor. Burada da eşleştirseydik view, hangi kursta
        olduğunu bilmeden çalışırdı.
        """
        match = _PREFIX_RE.match(path)
        if not match:
            return None
        code = match.group(1)
        if code not in languages.BY_CODE:
            return None
        # Çözümleme sırasında dili AKTİVE ediyoruz; aksi halde aynı istek
        # içinde üretilen URL'ler prefix'i kaybediyor.
        activate_target(code)
        return path[match.end():], (), {}

    def check(self):
        return []

    def describe(self):
        return f"'{self}'"

    def __str__(self):
        return self.course_prefix


def course_patterns(*urls):
    """`urls`u kurs prefix'i altına alır — `i18n_patterns` gibi kullanılır."""
    return [URLResolver(CoursePrefixPattern(), list(urls))]


# --------------------------------------------------------- reverse önbelleği

#: (arayüz dili, kurs) -> kök resolver'ın o çift için hesaplanmış sözlükleri.
_REVERSE_CACHE: dict = {}


def bind_reverse_cache():
    """Kök resolver'ın reverse önbelleğini AKTİF KURSA göre seçer.

    ÖLÇÜLMÜŞ HATA — bu olmadan çok kurslu gezinme bozuluyor:

    Django `URLResolver._reverse_dict`i YALNIZCA `get_language()`e göre
    anahtarlıyor, çünkü kendi `LocalePrefixPattern`ının öneki yalnızca ona
    bağlı. Bizim önekimiz ise kursa bağlı ve kurs anahtarın parçası değil.
    Sonuç: süreçteki İLK `reverse()` kurs önekini önbelleğe gömüyor ve
    sonraki bütün çağrılar aktif kurs ne olursa olsun onu döndürüyor::

        aktif kurs=de -> /learn/de/topics/
        aktif kurs=fr -> /learn/de/topics/   # yanlış
        aktif kurs=tr -> /learn/de/topics/   # yanlış

    Tek bir gunicorn işçisi birçok kullanıcıya hizmet ettiği için bu,
    İLK isteğin kursunun diğer herkesin menü bağlantılarına sızması demek.
    Almanca çalışan kullanıcı menüye bastığında `/learn/en/...`e gidiyor,
    `CourseMiddleware` de URL'deki kursu dikkate aldığı için kullanıcı
    farkında olmadan İngilizce kursuna geçiyor.

    Çözüm: önbelleği kendimiz (dil, kurs) çiftine göre tutup kök resolver'ın
    o dil için gözüken sözlüklerini doğru olanla değiştiriyoruz.

    EŞZAMANLILIK: kök resolver paylaşılan bir nesne, yani bu takas süreç
    başına tek isteğin koştuğunu varsayıyor — dağıtım `gunicorn --workers 3`
    ile SYNC işçi kullanıyor, koşul sağlanıyor. Thread'li bir işçiye
    (`gthread`, ASGI) geçilirse bu fonksiyon yerine istek başına ayrı
    `request.urlconf` kurmak gerekir.
    """
    resolver = get_resolver()
    language = get_language()
    key = (language, get_current_target_or_default())

    cached = _REVERSE_CACHE.get(key)
    if cached is None:
        # Django'nun bu dil için tuttuğu girdiyi düşürüp aktif kursla
        # yeniden kuruyoruz.
        for store in (resolver._reverse_dict, resolver._namespace_dict,
                      resolver._app_dict):
            store.pop(language, None)
        resolver._populate()
        cached = (
            resolver._reverse_dict[language],
            resolver._namespace_dict[language],
            resolver._app_dict[language],
        )
        _REVERSE_CACHE[key] = cached

    reverse_dict, namespace_dict, app_dict = cached
    resolver._reverse_dict[language] = reverse_dict
    resolver._namespace_dict[language] = namespace_dict
    resolver._app_dict[language] = app_dict


def clear_reverse_cache():
    """Testler için: (dil, kurs) önbelleğini boşaltır."""
    _REVERSE_CACHE.clear()
