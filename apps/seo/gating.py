"""Halka açık sayfalarda kayıtsız ziyaretçiye gösterilen içerik payı.

Sayfalar indekslenebilir KALIYOR: içeriğin bir kısmı herkese açık, gerisi
kayda bağlı. Amaç hem arama motoru yüzeyini korumak hem de tam erişimi
hesaba bağlamak.

İKİ KURAL — ikisi de SEO cezası riskini önlüyor:

1. **Gizleme kayıtsız HERKESE aynı uygulanıyor, Googlebot'a ayrıcalık yok.**
   Tarayıcıya tam metni verip kullanıcıdan saklamak "cloaking"tir ve
   cezalandırılır. Burada tarayıcı da ziyaretçinin gördüğünü görüyor.
2. **Gizlenen bölüm yapısal veride BİLDİRİLİYOR** (`isAccessibleForFree`
   false + `hasPart`/`cssSelector`). Tam erişim yokken "ücretsiz erişilebilir"
   demek yanlış beyan olurdu.

Limitler burada tek yerde: şablon ve view aynı sayıyı okuyor, aksi halde
"3 bölüm göster" deyip "5 bölüm gizli" yazan bir sayfa çıkardı.
"""

#: Anlatımdan gösterilen bölüm sayısı. Giriş paragrafı + ilk bölümler konunun
#: ne olduğunu anlatmaya yetiyor; kalanı kayda bağlı.
PREVIEW_SECTIONS = 2

#: Her biçimden (olumlu/olumsuz/soru) gösterilen örnek cümle sayısı.
PREVIEW_EXAMPLES_PER_KIND = 2

#: Seviye sayfasında gösterilen kelime sayısı.
PREVIEW_WORDS = 20

#: Gizlenen bloğun CSS seçicisi — yapısal veride `hasPart` bunu gösteriyor.
GATED_SELECTOR = '.seo-gated'


def is_gated(request) -> bool:
    """Bu istek kısıtlı içerik mi görecek?

    Tek ölçüt oturum: site ücretsiz, "abonelik" diye bir kademe yok, tam
    erişim için kayıt yeterli.
    """
    user = getattr(request, 'user', None)
    return not (user is not None and user.is_authenticated)


def limit(items, count, gated):
    """`gated` ise listeyi kırpar; değilse olduğu gibi döner."""
    items = list(items)
    return items[:count] if gated else items
