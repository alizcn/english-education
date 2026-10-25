"""Aktif kursu isteğe bağlar.

`LocaleMiddleware`DEN SONRA çalışmak zorunda: aktif kurs yoksa oluşturulurken
ana dil arayüz dilinden alınıyor ve o da `LocaleMiddleware` tarafından
belirleniyor.
"""

import logging

from apps.accounts.services import active_course

from .current import activate_target, deactivate, get_current_target
from .prefix import bind_reverse_cache

logger = logging.getLogger(__name__)


class CourseMiddleware:
    """`request.course`, `request.target_language`, `request.native_language`.

    URL'de kurs prefix'i varsa (`/learn/de/...`) `CoursePrefixPattern.match()`
    dili çözümleme sırasında zaten aktive etmiş oluyor; buradaki iş o dili
    kullanıcının gerçek kursuna bağlamak ve view'lerin elinin altına koymak.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = None
        try:
            token = self._bind(request)
            response = self.get_response(request)
        finally:
            # Contextvar'ın istekler arası sızması, bir kullanıcının Almanca
            # kursunun başkasının İngilizce isteğine karışması demek olurdu.
            deactivate(token)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """`reverse()` önbelleğini aktif kursa bağlar.

        `__call__` içinde YAPILAMIYOR: orası URL çözümlemesinden ÖNCE
        koşuyor, dolayısıyla `/learn/de/...` önekindeki kurs henüz aktive
        edilmemiş olurdu. `process_view` çözümlemeden sonra çalıştığı için
        contextvar doğru kursu taşıyor. Niçin gerekli: bkz.
        `prefix.bind_reverse_cache` — Django'nun reverse önbelleği kursu
        anahtarın parçası saymıyor.
        """
        bind_reverse_cache()
        return None

    def _bind(self, request):
        request.course = None
        request.target_language = None
        request.native_language = None

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None

        # URL prefix'i varsa o kursu istiyoruz; yoksa kullanıcının aktif kursu.
        requested = get_current_target()
        course = active_course(request)

        if requested and course is not None and course.target_language != requested:
            # Prefix başka bir kursu işaret ediyor: kullanıcının o dilde kursu
            # varsa onu kullan. Yoksa aktif kursta kal — URL'yi uydurmak yerine
            # view'in 404 vermesi daha dürüst.
            from apps.accounts.models import UserCourse
            other = UserCourse.objects.filter(
                user=user, target_language=requested,
            ).first()
            if other is not None:
                course = other
                request.course = other

        if course is None:
            return None

        request.course = course
        request.target_language = course.target_language
        request.native_language = course.native_language
        return activate_target(course.target_language)
