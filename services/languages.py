"""Dil sicili — platformun tek dil doğruluk kaynağı.

Üç eksen var ve bu modül üçünü de besler:

* **Arayüz dili**  — menü/buton/katalog. `settings.LANGUAGES` buradan türetilir,
  `i18n_patterns` prefix'ini (`/`, `/en/`, …) belirler.
* **Hedef dil**    — öğrenilen dil. Kelime hazinesi, gramer konusu, örnek cümle
  bu dilde. Uygulamada `/learn/<target>/`, SEO'da slug kökü (`english-grammar`).
* **Ana dil**      — anlamın/anlatımın yazıldığı dil. Kullanıcının kursunda
  saklanır, arayüz dilinden bağımsızdır.

Niçin tablo değil: yeni bir öğrenilebilir dil hiçbir zaman saf veri işlemi
değil — `.po` katalogu, CEFR kelime listesi, gramer konuları ve bir giriş
sayfası gerekiyor; hepsi deploy artefaktı. Tablo olsaydı `settings.LANGUAGES`
ile ikinci bir doğruluk kaynağı doğar ve her test fixture yüklemek zorunda
kalırdı.

Niçin `apps/` altında değil: `config/settings.py` bunu modül seviyesinde import
ediyor, o anda Django app registry'si henüz kurulmamış oluyor.
"""

from dataclasses import dataclass, field
from types import MappingProxyType

# Türkçe'de dil adları hâl eki alıyor ve ünlü uyumu yüzünden ek, adın son
# ünlüsüne göre değişiyor: "İngilizce**yi**" ama "Almanca**yı**". Bu yüzden
# arayüz metinlerine dil adını düz değişken olarak gömmek bozuk gramer üretir;
# çekimli biçimler önceden yazılır. Hâl anahtarları:
#   nom  yalın        (İngilizce / German / anglais)
#   acc  belirtme     (İngilizceyi)
#   dat  yönelme      (İngilizceye)
#   loc  bulunma      (İngilizcede)
#   abl  ayrılma      (İngilizceden)
#   def  belirtili     (Fransızca'da artikelli biçim: l'anglais)
#   prep edat'lı      (en anglais / auf Englisch)
# Bir dilde bulunmayan hâl `display_name()` tarafından 'nom'a düşürülür.
CASES = ('nom', 'acc', 'dat', 'loc', 'abl', 'def', 'prep')


@dataclass(frozen=True)
class LangSpec:
    code: str
    english_name: str          # promptlarda kullanılır — model için kod belirsiz
    native_name: str           # dilin kendi adı: dil seçicide gösterilen
    og_locale: str             # Open Graph locale, örn. tr_TR
    seo_stem: str              # SEO slug kökü: english-grammar, german-vocabulary
    cefr_levels: tuple         # bu dil için yayınlanan seviyeler
    is_ui: bool                # arayüz dili olarak yayında mı
    is_learnable: bool         # öğrenilebilir (hedef) dil mi
    wordlist_source: str = ''  # kelime omurgasının kaynağı
    license_note: str = ''     # atıf/lisans notu — SEO lisans sayfasına basılır
    # {ad_dili: {hâl: metin}} — bu dilin adının diğer dillerdeki çekimleri.
    # compare=False: sözlük hash'lenemez ve `Pair` frozen olduğu için hash'i
    # alan değerlerinden üretiliyor. Kimlik zaten `code`ta; aynı kodun iki
    # farklı çekim tablosu olmaz.
    display: dict = field(default_factory=dict, compare=False)


_CEFR_FULL = ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')
_CEFR_TO_C1 = ('A1', 'A2', 'B1', 'B2', 'C1')

ENGLISH = LangSpec(
    code='en',
    english_name='English',
    native_name='English',
    og_locale='en_US',
    seo_stem='english',
    cefr_levels=_CEFR_FULL,
    is_ui=True,
    is_learnable=True,
    wordlist_source='Oxford 3000/5000 (A1–C1); C2 frekans türevi',
    license_note='Oxford University Press kelime listeleri',
    display={
        'tr': {'nom': 'İngilizce', 'acc': 'İngilizceyi', 'dat': 'İngilizceye',
               'loc': 'İngilizcede', 'abl': 'İngilizceden'},
        'en': {'nom': 'English'},
        'fr': {'nom': 'anglais', 'def': "l'anglais",
               'acc': "l'anglais", 'gen': "de l'anglais", 'prep': 'en anglais'},
        'de': {'nom': 'Englisch', 'prep': 'auf Englisch'},
    },
)

TURKISH = LangSpec(
    code='tr',
    english_name='Turkish',
    native_name='Türkçe',
    og_locale='tr_TR',
    seo_stem='turkish',
    cefr_levels=_CEFR_FULL,
    is_ui=True,
    # Hedef dil olarak Faz 7'de açılır (kelime hazinesi + gramer konuları o
    # zaman üretiliyor). Arayüz dili olarak zaten varsayılan.
    is_learnable=True,
    wordlist_source='wordfreq (CC BY-SA 4.0) frekans listesi + Claude lemmatizasyon',
    license_note='wordfreq, CC BY-SA 4.0 — Robyn Speer',
    display={
        'tr': {'nom': 'Türkçe', 'acc': 'Türkçeyi', 'dat': 'Türkçeye',
               'loc': 'Türkçede', 'abl': 'Türkçeden'},
        'en': {'nom': 'Turkish'},
        'fr': {'nom': 'turc', 'def': 'le turc',
               'acc': 'le turc', 'gen': 'du turc', 'prep': 'en turc'},
        'de': {'nom': 'Türkisch', 'prep': 'auf Türkisch'},
    },
)

FRENCH = LangSpec(
    code='fr',
    english_name='French',
    native_name='Français',
    og_locale='fr_FR',
    seo_stem='french',
    cefr_levels=_CEFR_FULL,
    # 2026-10-24'te yayına alındı: `locale/fr` 675/675 dolu. Katalog %100
    # olmadan açılamazdı — msgid'ler Türkçe olduğu için eksik girdi
    # kullanıcıya yarı Türkçe bir sayfa gösterirdi. Kapı:
    # `manage.py check_translations`.
    is_ui=True,
    is_learnable=True,
    wordlist_source='FLELex-CRF (UCLouvain CEFRLex) — 17.871 lemma, CEFR dereceli',
    license_note='FLELex, CC BY-NC — François, Gala, Watrin & Fairon (LREC 2014)',
    display={
        'tr': {'nom': 'Fransızca', 'acc': 'Fransızcayı', 'dat': 'Fransızcaya',
               'loc': 'Fransızcada', 'abl': 'Fransızcadan'},
        'en': {'nom': 'French'},
        'fr': {'nom': 'français', 'def': 'le français',
               'acc': 'le français', 'gen': 'du français', 'prep': 'en français'},
        'de': {'nom': 'Französisch', 'prep': 'auf Französisch'},
    },
)

GERMAN = LangSpec(
    code='de',
    english_name='German',
    native_name='Deutsch',
    og_locale='de_DE',
    seo_stem='german',
    cefr_levels=_CEFR_FULL,
    # 2026-10-24'te yayına alındı: `locale/de` 675/675 dolu (bkz. FRENCH).
    is_ui=True,
    is_learnable=True,
    wordlist_source='Goethe-Institut Wortliste (A1–B1) + wordfreq türevi (B2–C1)',
    license_note='Goethe-Institut Wortliste; wordfreq, CC BY-SA 4.0',
    display={
        'tr': {'nom': 'Almanca', 'acc': 'Almancayı', 'dat': 'Almancaya',
               'loc': 'Almancada', 'abl': 'Almancadan'},
        'en': {'nom': 'German'},
        'fr': {'nom': 'allemand', 'def': "l'allemand",
               'acc': "l'allemand", 'gen': "de l'allemand", 'prep': 'en allemand'},
        'de': {'nom': 'Deutsch', 'acc': 'Deutsch', 'prep': 'auf Deutsch'},
    },
)

#: Sicildeki tüm diller. Sıra anlamlı: `settings.LANGUAGES` ve dil seçici bunu
#: kullanıyor, varsayılan dil (tr) başta.
ALL = (TURKISH, ENGLISH, FRENCH, GERMAN)

BY_CODE = MappingProxyType({spec.code: spec for spec in ALL})
BY_SEO_STEM = MappingProxyType({spec.seo_stem: spec for spec in ALL})

#: Arayüz dili olarak yayında olanlar — `settings.LANGUAGES` buradan türer.
UI_LANGUAGES = tuple(spec for spec in ALL if spec.is_ui)
#: Öğrenilebilir (hedef) diller.
LEARNABLE_LANGUAGES = tuple(spec for spec in ALL if spec.is_learnable)

UI_CODES = tuple(spec.code for spec in UI_LANGUAGES)
LEARNABLE_CODES = tuple(spec.code for spec in LEARNABLE_LANGUAGES)
#: Sicildeki tüm kodlar. İÇERİK ÜRETİMİ bunu kullanıyor, `UI_CODES`i değil:
#: kurs ana dili arayüz diline bağlı değil (`UserCourse.native_language`
#: tam dil listesinden seçiliyor), dolayısıyla bir örnek cümlenin çevirisi
#: o dil henüz arayüz dili olarak yayına girmeden de gerekiyor. Üretimi
#: arayüz yayın takvimine bağlamak, dil açıldığı gün içeriği eksik bırakırdı.
ALL_CODES = tuple(spec.code for spec in ALL)

#: Model alanları için. `CharField(max_length=5, choices=LANGUAGE_CHOICES)`.
LANGUAGE_CHOICES = tuple((spec.code, spec.native_name) for spec in ALL)
LEARNABLE_CHOICES = tuple((spec.code, spec.native_name) for spec in LEARNABLE_LANGUAGES)


class UnknownLanguage(KeyError):
    """Sicilde olmayan bir dil kodu istendi."""


def get(code) -> LangSpec:
    try:
        return BY_CODE[code]
    except KeyError:
        raise UnknownLanguage(code) from None


def by_seo_stem(stem) -> LangSpec:
    try:
        return BY_SEO_STEM[stem]
    except KeyError:
        raise UnknownLanguage(stem) from None


def display_name(code, *, in_language, case='nom') -> str:
    """`code` dilinin adını `in_language` dilinde, istenen hâlde döndürür.

    Bulunmayan hâl 'nom'a düşer (İngilizce'de hâl eki yok); bilinmeyen ad dili
    İngilizce'ye düşer.
    """
    spec = get(code)
    table = spec.display.get(in_language) or spec.display.get('en') or {}
    return table.get(case) or table.get('nom') or spec.english_name


@dataclass(frozen=True)
class Pair:
    """Bir (hedef, ana dil) çifti — AI çağrılarının ve içerik üretiminin birimi."""

    target: LangSpec
    native: LangSpec

    @property
    def target_code(self) -> str:
        return self.target.code

    @property
    def native_code(self) -> str:
        return self.native.code

    @property
    def target_name(self) -> str:
        """Promptlara giden ad — İngilizce, çünkü model için 'de' belirsiz."""
        return self.target.english_name

    @property
    def native_name(self) -> str:
        return self.native.english_name

    @property
    def is_mono(self) -> bool:
        """Hedef ve ana dil aynı mı — böyle bir kurs anlamsız."""
        return self.target.code == self.native.code

    def __str__(self):
        return f'{self.target.code}->{self.native.code}'


def pair(target, native) -> Pair:
    """Kod ya da `LangSpec` kabul eder; aynı dil verilirse hata."""
    t = target if isinstance(target, LangSpec) else get(target)
    n = native if isinstance(native, LangSpec) else get(native)
    if t.code == n.code:
        raise ValueError(f'hedef ve ana dil aynı olamaz: {t.code}')
    return Pair(target=t, native=n)


def course_pairs(*, learnable_only=True):
    """Yayında olan tüm (hedef, ana dil) çiftleri."""
    targets = LEARNABLE_LANGUAGES if learnable_only else ALL
    return tuple(
        Pair(target=t, native=n)
        for t in targets
        for n in UI_LANGUAGES
        if t.code != n.code
    )
