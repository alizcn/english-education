"""Aktif kursun hedef dilini istek boyunca taşıyan contextvar.

Niçin contextvar: `CoursePrefixPattern.match()` URL çözümlenirken dili
aktive etmek zorunda, çünkü `reverse()` prefix'i oradan okuyor. Bu, Django'nun
`i18n_patterns` mekanizmasının birebir aynısı (`LocalePrefixPattern` +
`translation.activate`), yalnızca eksen farklı.

contextvar yerine `request`e bağlamak YETMİYOR: `reverse()` request almıyor.
Thread-local yerine contextvar, çünkü ASGI altında aynı thread birden çok
isteği dokuyabiliyor.
"""

from contextvars import ContextVar

from django.conf import settings

#: Aktif hedef dil kodu. None = kurs prefix'i yok (halka açık sayfalar).
_current_target: ContextVar = ContextVar('learn_target', default=None)


def activate_target(code):
    """Bu bağlam için hedef dili ayarlar ve geri alma token'ı döndürür."""
    return _current_target.set(code)


def deactivate(token=None):
    """Hedef dili temizler.

    `token` verilirse o noktaya geri sarar; verilmezse None'a çeker.
    Middleware `process_response`ta çağırıyor — contextvar'ın istekler arası
    sızması, bir kullanıcının Almanca kursunun başkasının İngilizce isteğine
    karışması demek olurdu.
    """
    if token is not None:
        try:
            _current_target.reset(token)
            return
        except ValueError:
            # Token başka bir bağlamdan; aşağıdaki düz temizlik yeter.
            pass
    _current_target.set(None)


def get_current_target():
    """Aktif hedef dil ya da None."""
    return _current_target.get()


def get_current_target_or_default():
    return _current_target.get() or settings.LEARN_DEFAULT_TARGET
