"""Model çıktısındaki terimi payload terimine bağlar — TEK tanım.

Niçin ayrı modül: `enrich_wordbank._validate` ile `export_content._merge_wordbank`
AYNI eşlemeyi yapmak zorunda. Doğrulayıcı gevşek, dışa aktarma katı olursa
parça `done` olur ama kayıt dosyaya hiç yazılmaz — sessiz veri kaybı. İkisi de
buradan okuyor.

Ölçülmüş iki sapma:

* **Aksan düşmesi.** Fransızca'da modelin `épisode` yerine `episode` döndürdüğü
  ölçüldü. Birebir karşılaştırma bütün parçayı reddediyordu; parçayı kurtarmak
  için terim payload'dan çıkarılınca o kelime kalıcı olarak kayboldu —
  Fransızca'da `é`/`ô`/`î` ile başlayan **77 gerçek kelime** böyle düştü.
* **Türkçe harf sapması.** `yök` → `yok`, `sık` → `sik`. Burada aksan katlama
  TEK BAŞINA tehlikeli: `yok` ve `yök` ayrı kelimeler. O yüzden katlanmış
  eşleşme yalnızca **tek aday** varken kabul ediliyor; iki payload terimi aynı
  katlanmış biçme düşerse eşleme belirsiz sayılıp reddediliyor.

Kanonik biçim her zaman PAYLOAD terimi: modelin yeniden yazdığı hâli değil.
Böylece `rank` ile gelen kaynak kelime hiç değişmiyor.
"""

import unicodedata


def fold(text: str) -> str:
    """Küçük harfe indirip diakritikleri düşürür: `Épisode` → `episode`."""
    lowered = unicodedata.normalize('NFKD', (text or '').strip().lower())
    return ''.join(c for c in lowered if not unicodedata.combining(c))


def build_index(terms):
    """Payload terimlerinden eşleme dizini kurar.

    `terms`: `{'term': …}` sözlükleri ya da düz dizgiler.

    Dönen: `(exact, folded)` — `exact` birebir küçük harf eşlemesi,
    `folded` yalnızca TEK adayı olan katlanmış biçimler. Çok adaylı katlanmış
    biçimler dizine hiç girmiyor, yani belirsiz eşleme sessizce yanlış
    kelimeye anlam yazamıyor.
    """
    exact, buckets = {}, {}
    for item in terms:
        term = item['term'] if isinstance(item, dict) else item
        term = (term or '').strip()
        if not term:
            continue
        exact.setdefault(term.lower(), term)
        buckets.setdefault(fold(term), []).append(term)
    folded = {key: names[0] for key, names in buckets.items()
              if len(set(names)) == 1}
    return exact, folded


def resolve(term, index):
    """Modelin döndürdüğü terimi payload terimine çevirir, yoksa `None`."""
    exact, folded = index
    term = (term or '').strip()
    if not term:
        return None
    hit = exact.get(term.lower())
    if hit is not None:
        return hit
    return folded.get(fold(term))
