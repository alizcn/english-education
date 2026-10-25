"""Quiz cevaplarının normalizasyonu ve karşılaştırması.

`apps/quizzes/views.py`den buraya taşındı: request'ten bağımsız olduğu için
birim test edilebiliyor (eskiden hiç testi yoktu) ve dil ekseni geldiğinde
Türkçe'ye özgü varsayımları ayıklamak gerekiyordu.

Eski sürüm harfleri WHITELIST'liyordu:

    re.sub(r"[^\\w\\sğüşıöçİĞÜŞÖÇ'-]", '', s, flags=re.UNICODE)

Bu iki şeyi birden yapıyordu: Türkçe harfleri elle sayıyor (Fransızca `œ`,
Almanca `ß` listede yok) ve Fransızca'nın tipografik kesme işaretini (`’`,
U+2019) atıyordu — `l'homme` yerine `l’homme` yazan kullanıcının cevabı yanlış
sayılıyordu. Artık `str.isalnum()` kullanılıyor: Unicode farkında olduğu için
HİÇBİR dilde harf listesi tutulmuyor.
"""

import re
import unicodedata
from dataclasses import dataclass

#: Tipografik varyantlar düz karşılıklarına indirilir. Kullanıcı klavyesinde
#: hangi apostrofun olduğu bir öğrenme sinyali değil.
_PUNCT = str.maketrans({
    '’': "'",   # ’ sağ tek tırnak (Fransızca'da yaygın)
    '‘': "'",   # ‘
    'ʼ': "'",   # ʼ
    '´': "'",   # ´
    '`': "'",
    '“': '"',   # “
    '”': '"',   # ”
    '–': '-',   # – en dash
    '—': '-',   # — em dash
    ' ': ' ',   # kırılmaz boşluk
    # Türkçe noktalı/noktasız I ayrımı quiz cevabında yanlış-negatif
    # üretmemeli: klavye düzeni ya da otomatik düzeltme kolayca değiştiriyor.
    'İ': 'i',
    'ı': 'i',
})

_WHITESPACE = re.compile(r'\s+')

#: Alternatif cevap konvansiyonu: "colour / color".
_ALTERNATIVES = re.compile(r'\s*/\s*')


def normalize(s: str) -> str:
    """Karşılaştırma için metni sadeleştirir.

    `casefold()` kullanılıyor, `lower()` değil: Almanca `ß` ile `ss`i eşitlemek
    için gerekiyor (`'ß'.lower()` hâlâ `'ß'`).
    """
    s = unicodedata.normalize('NFC', (s or '').strip()).translate(_PUNCT)
    s = ''.join(c for c in s if c.isalnum() or c.isspace() or c in "'-")
    return _WHITESPACE.sub(' ', s).strip().casefold()


def fold_accents(s: str) -> str:
    """Diakritikleri düşürür: `é`→`e`, `ü`→`u`, `ç`→`c`."""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )


@dataclass(frozen=True)
class Verdict:
    is_correct: bool
    #: Cevap yalnızca diakritik farkıyla tuttu. Doğru sayılıyor ama kullanıcıya
    #: ipucu gösteriliyor — Fransızca ve Almanca'da gerçek bir öğrenme sinyali.
    diacritics_only: bool = False


def _candidates(correct: str):
    """Kabul edilen cevaplar: tamamı ve "/" ile ayrılmış alternatifler."""
    whole = normalize(correct)
    parts = [normalize(p) for p in _ALTERNATIVES.split(correct or '')]
    return {c for c in [whole, *parts] if c}


def check_answer(user_answer: str, correct: str) -> Verdict:
    """İki kademeli karşılaştırma: tam eşleşme, sonra aksansız eşleşme."""
    given = normalize(user_answer)
    if not given:
        return Verdict(False)

    accepted = _candidates(correct)
    if given in accepted:
        return Verdict(True)

    folded_given = fold_accents(given)
    folded_accepted = {fold_accents(c) for c in accepted}
    if folded_given in folded_accepted:
        return Verdict(True, diacritics_only=True)

    return Verdict(False)


def is_answer_correct(user_answer: str, correct: str) -> bool:
    """Geriye dönük uyumlu kısayol."""
    return check_answer(user_answer, correct).is_correct
