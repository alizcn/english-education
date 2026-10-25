"""Kurs (dil çifti) yönetimi.

Aktif kursu bulmanın ve kurmanın tek yeri burası. View'ler `current_pair(request)`
çağırıyor; böylece Faz 3'te URL tabanlı kurs yönlendirmesi geldiğinde yalnızca
bu modülün içi değişiyor, çağrı noktaları değişmiyor.

Kurs oluşturma neden bir SİNYAL değil: `post_save(User)` sinyalinin `request`e
erişimi yok, dolayısıyla kullanıcının ana dilini tahmin edemiyor. İngilizce
konuşan bir kullanıcıya `native_language='tr'` kurs açmak sessiz bir veri
hatası olurdu. Bu yüzden kurs, dili bilen yerlerde (signup view'i, kurs
seçici, middleware fallback) açıkça kuruluyor.
"""

from django.conf import settings
from django.db import transaction
from django.utils.translation import get_language

from services import languages

from .models import UserCourse

#: Mevcut tek kurs: Türk kullanıcıya İngilizce. Yeni kullanıcılarda ve dili
#: belirleyemediğimiz durumlarda bu çifte düşülür.
DEFAULT_TARGET = 'en'


def default_native_for(target_language, *, requested=None):
    """Hedef dile uygun bir ana dil seçer.

    Aktif arayüz dili tercih edilir; hedef dille çakışıyorsa (İngilizce arayüz
    + İngilizce kurs) varsayılan dile düşülür. İkisi de çakışıyorsa yayında
    olan ilk uygun dil alınır.
    """
    candidates = [
        requested or get_language(),
        settings.LANGUAGE_CODE,
        *languages.UI_CODES,
    ]
    for code in candidates:
        if code and code != target_language and code in languages.BY_CODE:
            return code
    # Sicilde tek dil kalmadıysa buraya düşer; pratikte imkânsız.
    raise ValueError(f'{target_language} için uygun ana dil yok')


@transaction.atomic
def ensure_active_course(user, *, target=None, native=None) -> UserCourse:
    """Kullanıcının aktif kursunu döndürür, yoksa oluşturur.

    Zaten aktif bir kurs varsa ve `target` istenmediyse o döner. `target`
    verilmişse o kurs aktif edilir (varsa), yoksa oluşturulur.
    """
    if target is None:
        existing = UserCourse.objects.filter(user=user, is_active=True).first()
        if existing:
            return existing
        # Aktif kurs yok ama kurs olabilir (ör. hepsi pasif bırakılmış).
        any_course = UserCourse.objects.filter(user=user).first()
        if any_course:
            return activate(any_course)
        target = DEFAULT_TARGET

    native = native or default_native_for(target)
    course = UserCourse.objects.filter(
        user=user, target_language=target,
    ).first()
    if course is not None:
        return activate(course)

    # `one_active_course` KISMİ tekilliği: aktif satır kullanıcı başına bir
    # tane. `get_or_create(defaults={'is_active': True})` kullanılıyordu ve
    # yeni satırı aktif doğurduğu için ikinci kurs eklemek `IntegrityError`
    # veriyordu — diğerlerini pasife çekmek INSERT'ten SONRA geliyordu.
    # Sıra tersine çevrildi; `activate()` aynı kuralı açıklıyor.
    UserCourse.objects.filter(user=user, is_active=True).update(is_active=False)
    return UserCourse.objects.create(
        user=user, target_language=target, native_language=native,
        is_active=True,
    )


@transaction.atomic
def activate(course: UserCourse) -> UserCourse:
    """Bu kursu aktif, kullanıcının diğerlerini pasif yapar.

    `one_active_course` kısmi tekilliği yüzünden sıra önemli: önce diğerleri
    pasife çekilmeli, yoksa iki aktif kurs anlık olarak var olup kısıt ihlal
    edilir.
    """
    UserCourse.objects.filter(user_id=course.user_id, is_active=True).exclude(
        pk=course.pk,
    ).update(is_active=False)
    if not course.is_active:
        course.is_active = True
        course.save(update_fields=['is_active', 'updated_at'])
    return course


def active_course(request):
    """İstekteki aktif kurs. Giriş yapılmamışsa None.

    Faz 3'te `CourseMiddleware` `request.course`u dolduracak; burada o değer
    varsa doğrudan kullanılıyor.
    """
    cached = getattr(request, 'course', None)
    if cached is not None:
        return cached
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    course = ensure_active_course(user)
    request.course = course
    return course


def current_pair(request):
    """İsteğin (hedef, ana dil) çifti.

    Giriş yapılmamış sayfalarda (landing, SEO) kurs yok; o durumda varsayılan
    çift dönüyor, çünkü halka açık içerik bugün yalnızca İngilizce.
    """
    course = active_course(request)
    if course is not None:
        return course.pair
    return languages.pair(DEFAULT_TARGET, default_native_for(DEFAULT_TARGET))
