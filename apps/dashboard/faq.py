"""Giriş sayfası SSS'si — JSON-LD ile görünür listenin TEK kaynağı.

Eskiden aynı metin `landing.html` içinde iki kez yazılıydı: bir kez
`FAQPage` yapısal verisi, bir kez görünür `<details>` listesi. Üç sorun
çıkarıyordu:

1. **İkizler ayrışıyordu.** Üçüncü cevabın görünür sürümünde fazladan bir
   cümle vardı; yapısal veri ile sayfa farklı şey söylüyordu.
2. **Apostrof iki msgid üretiyordu.** JSON-LD sürümü `A1&#39;den` yazıyor,
   görünür sürüm `A1'den` — gettext için bunlar ayrı dizgeler, yani her cevap
   iki kez çevriliyordu. Dört dilde bu dört kat demek.
3. Çeviri yükü soru sayısının iki katıydı.

Artık metin burada bir kez duruyor; şablon iki kez dönüyor. HTML kaçışı
*render anında* Django'nun otomatik escape'i ile oluyor, msgid'de değil —
entity'li msgid'ler tamamen ortadan kalktı.
"""

import json

from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

#: `json_script` ile aynı küme: bu üç karakter kaçırılmazsa gövdedeki
#: `</script>` etiketi erken kapatır ve XSS'e açar.
_SCRIPT_ESCAPES = {
    '<': '\\u003C',
    '>': '\\u003E',
    '&': '\\u0026',
}

#: `(soru, cevap)` ikilileri. Sıra sayfadaki sıra.
ITEMS = (
    (
        _('Hangi dilleri öğrenebilirim?'),
        _('İngilizce, Almanca, Fransızca ve Türkçe. Aynı hesapla birden çok '
          'dil çalışabilirsiniz; her kursun kendi seviyesi ve puanı vardır. '
          'Anlatım dilini de siz seçersiniz — örneğin Almancayı Türkçe, '
          'İngilizce ya da Fransızca açıklamalarla çalışabilirsiniz.'),
    ),
    (
        _('Platform ücretli mi?'),
        _('Hayır, platform tamamen ücretsizdir. Kayıt olun ve hemen '
          'kullanmaya başlayın.'),
    ),
    (
        _('Kelime Hazinesi\'nde hangi seviyeler var?'),
        _('A1\'den C2\'ye kadar 6 seviye ve binlerce kelime mevcuttur. '
          'Her seviyede sırayla ilerlersiniz.'),
    ),
    (
        _('Yanlış yaptığım kelimeler ne oluyor?'),
        _('Yanlış cevapladığınız kelimeler otomatik olarak tekrar havuzuna '
          'eklenir ve ileriki sorularda karşınıza çıkar. Doğru cevaplayana '
          'kadar peşinizi bırakmaz.'),
    ),
    (
        _('Kendi kelimelerimi ekleyebilir miyim?'),
        _('Evet. Kelimelerim bölümünden istediğiniz kelimeleri girebilirsiniz. '
          'AI otomatik olarak anlamını ve örnek cümlesini üretir.'),
    ),
    (
        _('AI Chat ne işe yarar?'),
        _('AI Chat ile pratik yapabilirsiniz. Ana dilinizde ya da öğrendiğiniz '
          'dilde yazın, AI asistan hatalarınızı düzeltir ve doğal konuşma '
          'pratiği sunar.'),
    ),
)


def as_dicts():
    """Şablon döngüsü için `[{'question': …, 'answer': …}]`."""
    return [{'question': q, 'answer': a} for q, a in ITEMS]


def as_schema_json():
    """Gömülmeye hazır `schema.org/FAQPage` JSON'u.

    Sunucu tarafında üretiliyor: yapısal veriyi JavaScript ile kurmak,
    tarayıcısında JS koşturmayan tarayıcıya ve bazı doğrulayıcılara boş
    `mainEntity` göstermek demekti.

    `</script>` ve HTML'de anlam taşıyan karakterler Django'nun `json_script`
    ile aynı biçimde kaçırılıyor; dönen değer şablonda `|safe` ile basılıyor.
    Lazy çeviri proxy'leri `str()` ile çözülüyor, aksi hâlde serileştirici
    onları tanımıyor.
    """
    payload = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': str(q),
                'acceptedAnswer': {'@type': 'Answer', 'text': str(a)},
            }
            for q, a in ITEMS
        ],
    }
    body = json.dumps(payload, ensure_ascii=False)
    for char, escaped in _SCRIPT_ESCAPES.items():
        body = body.replace(char, escaped)
    return mark_safe(body)  # noqa: S308 — kaçış yukarıda yapıldı
