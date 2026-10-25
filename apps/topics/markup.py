"""Konu anlatımlarının kısıtlı markdown ayrıştırıcısı.

Eski ayrıştırıcı başlıkları SEZGİSEL olarak tanıyordu: bir satır `?` veya `:`
ile bitiyorsa, tamamı büyük harfse ya da belirli bir karakter sınıfına uyuyorsa
başlık sayılıyordu. Beş kuralın hiçbiri dilden bağımsız değildi:

* Karakter sınıfı Türkçe büyük harfleri elle listeliyordu (`ÇĞİÖŞÜ`);
  Fransızca `ÉÈÊÀÂÎÔÛËÏ` ve Almanca `Ä` yoktu.
* `candidate.upper() == candidate` kuralı Almanca'da `ß` yüzünden kırılıyor
  (`'ß'.upper() == 'SS'`, kendine eşit değil).
* Başlıklar Title Case yazılırsa (Fransızca ve Almanca'da doğal olan) kural
  tamamen çöküyor.
* Ölçüldü: mevcut veride bile Türkçe metinlerin %30'u, İngilizce metinlerin
  %24'ü başlık tanınmadığı için gövdeye düşüyordu.

Bu yüzden sezgi tamamen silindi ve konvansiyon değişti: başlık `##` ile
başlıyor. Büyük-küçük harf, alfabe ve aksan artık tamamen önemsiz.

Ayrıca bu modül GÖRÜNÜR METİN ÜRETMİYOR. Eskiden başlıksız bloklara `'Özet'`
yazılıyor ve şablon bunu `section.title == 'Özet'` ile karşılaştırıyordu —
yani metin çevrilse şablon mantığı sessizce bozulacaktı. Artık başlıksız blok
`title=None, prose=True` dönüyor ve etiketi şablon koyuyor.
"""

import re
from dataclasses import dataclass, field

#: `## Başlık` / `### Alt başlık`. Satır başındaki boşluğa toleranslı.
_HEADING = re.compile(r'^\s{0,3}(#{2,4})\s+(.+?)\s*#*\s*$')

#: Madde işareti. Eski kod `stripped[1:]` ile TEK karakter kesiyordu, bu yüzden
#: `–` (en dash) gibi çok baytlı işaretlerde metnin başı bozuluyordu.
_BULLET = re.compile(r'^\s{0,3}[-*+•‣·–—]\s+(.*)$')

#: `1.` / `1)` biçiminde numaralı madde.
_ORDERED = re.compile(r'^\s{0,3}\d+[.)]\s+(.*)$')


@dataclass
class Section:
    """Anlatımın tek bir bloğu.

    `title is None` ise blok başlıksız. `prose` True ise içerik madde listesi
    değil düz paragraf — şablon bunu `<ul>` yerine `white-space: pre-line` bir
    blok olarak basıyor.
    """

    title: str | None = None
    items: list = field(default_factory=list)
    prose: bool = False

    @property
    def is_empty(self):
        return not self.items and not self.title


def parse_sections(text) -> list:
    """Metni `Section` listesine çevirir.

    Kurallar:
      * `##` ile başlayan satır yeni bir bölüm açar.
      * Boş satır, başlıksız bir bölüm içinde yeni bölüm açar (eski davranış).
      * Madde işaretli satırlar `items`a girer, bölüm liste olur.
      * Madde işareti olmayan satırlar da `items`a girer ama bölüm `prose`
        işaretlenir; şablon onları paragraf olarak basar.
    """
    text = (text or '').strip()
    if not text:
        return []

    sections: list = []
    current: Section | None = None
    saw_bullet = False
    pending_blank = False

    def flush():
        nonlocal current, saw_bullet
        if current is not None and not current.is_empty:
            # Hiç madde işareti görülmediyse blok düz metindir.
            current.prose = not saw_bullet
            sections.append(current)
        current = None
        saw_bullet = False

    for raw in text.splitlines():
        line = raw.rstrip()

        if not line.strip():
            pending_blank = True
            continue

        heading = _HEADING.match(line)
        if heading:
            flush()
            pending_blank = False
            current = Section(title=heading.group(2).strip())
            continue

        bullet = _BULLET.match(line) or _ORDERED.match(line)

        # Başlıksız bir blokta boş satır yeni blok açar; başlıklı blokta
        # boş satır yalnızca paragraf ayracıdır, başlığı düşürmez.
        if pending_blank and current is not None and current.title is None:
            flush()
        pending_blank = False

        if current is None:
            current = Section()

        if bullet:
            saw_bullet = True
            content = bullet.group(1).strip()
            if content:
                current.items.append(content)
        else:
            current.items.append(line.strip())

    flush()
    return sections
