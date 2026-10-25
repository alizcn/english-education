"""SEO slug köklerinde hedef dil: `english-grammar`, `german-vocabulary`.

Niçin converter: `/english-grammar/` adresi İNDEKSLİ ve bayt bayt korunmak
zorunda. Converter sayesinde aynı URL, aynı view adıyla çözümlenmeye devam
ediyor; `reverse('seo:grammar_index', kwargs={'lang': 'en'})` yine
`/english-grammar/` üretiyor. Alternatif (dil başına ayrı path) hem URL
adlarını çoğaltır hem de `legacy_urls.py`deki dondurulmuş 301'leri kırardı.

Regex sicilden türetiliyor, elle yazılmıyor: bir dilin `seo_stem`i
değiştiğinde ya da yeni dil eklendiğinde burayı güncellemeyi unutmak
sessizce 404 üretirdi.
"""

from services import languages

#: 'english' -> 'en'
STEM_TO_CODE = {spec.seo_stem: spec.code for spec in languages.ALL}
#: 'en' -> 'english'
CODE_TO_STEM = {spec.code: spec.seo_stem for spec in languages.ALL}


class TargetLangConverter:
    """Slug kökündeki dil adını koda çevirir."""

    regex = '|'.join(sorted(STEM_TO_CODE, key=len, reverse=True))

    def to_python(self, value):
        return STEM_TO_CODE[value]

    def to_url(self, value):
        # `reverse` hem kod ('en') hem kök ('english') kabul etsin: şablonlarda
        # ikisi de doğal geliyor.
        if value in CODE_TO_STEM:
            return CODE_TO_STEM[value]
        if value in STEM_TO_CODE:
            return value
        raise ValueError(f'bilinmeyen hedef dil: {value!r}')
