"""`BankWord.extra` alanının hedef dile özgü normalizasyonu.

Model morfoloji alanlarını tutarsız dolduruyor ve bu alanlar kullanıcıya
gösteriliyor. Normalizasyon **dışa aktarmada** koşuyor, dosyada elle
düzeltilmiyor: dosya üretim defterinden yeniden kurulabilir olmak zorunda,
aksi halde her yeniden dışa aktarma düzeltmeyi geri alırdı.

Kural tek yönlü: emin olunan biçim yazılır, emin olunmayan alan **silinir**.
Yanlış morfoloji, eksik morfolojiden daha kötü — öğrenci onu ezberliyor.
"""

#: Almanca Perfekt yardımcı fiili MASTAR hâlinde tutuluyor (`haben`/`sein`).
#: Ölçüm: 1.850 fiilin 1.023'ünde çekimli biçim gelmişti (`hat` 892, `ist` 105,
#: ayrıca `habe`, `hast`, `sind`). Alan "bu fiil Perfekt'i hangi yardımcı
#: fiille kurar" sorusunu yanıtlıyor, dolayısıyla çekim bilgi taşımıyor.
_DE_AUX = {
    'haben': 'haben', 'hat': 'haben', 'habe': 'haben', 'hast': 'haben',
    'habt': 'haben', 'hatte': 'haben',
    'sein': 'sein', 'ist': 'sein', 'sind': 'sein', 'bist': 'sein',
    'war': 'sein',
    # İki yardımcı fiille de kurulabilen fiiller (hareket fiilleri anlamına
    # göre değişiyor: "er ist gefahren" / "er hat das Auto gefahren").
    'hat/ist': 'haben/sein', 'ist/hat': 'haben/sein',
    'haben/sein': 'haben/sein', 'sein/haben': 'haben/sein',
    # Modal fiiller Perfekt'i `haben` ile kurar.
    'kann': 'haben', 'darf': 'haben', 'soll': 'haben', 'muss': 'haben',
    'will': 'haben', 'mag': 'haben',
    'können': 'haben', 'dürfen': 'haben', 'sollen': 'haben',
    'müssen': 'haben', 'wollen': 'haben', 'mögen': 'haben',
}

#: `werden` ailesi Perfekt yardımcı fiili DEĞİL (edilgen/gelecek zaman
#: yardımcısı); bu değerler modelin alanı yanlış anlamasından geliyor ve
#: tahmin edilerek düzeltilemiyor, o yüzden alan düşüyor.
_DE_AUX_DROP = {'werden', 'wird', 'wurde', 'würde', 'wäre', 'worden'}


def _normalise_de(extra: dict) -> dict:
    aux = (extra.get('auxiliary') or '').strip().lower().replace(' ', '')
    if not aux:
        return extra
    mapped = _DE_AUX.get(aux)
    if mapped:
        return {**extra, 'auxiliary': mapped}
    if aux in _DE_AUX_DROP or '/' in aux or ' ' in aux.strip():
        return {k: v for k, v in extra.items() if k != 'auxiliary'}
    # Sözlükte olmayan, tek parçalı bir değer: tanınmadığı için düşüyor.
    return {k: v for k, v in extra.items() if k != 'auxiliary'}


_BY_LANGUAGE = {'de': _normalise_de}


def normalise_extra(target: str, extra) -> dict:
    """`extra` sözlüğünü hedef dilin kuralına göre düzeltir."""
    if not isinstance(extra, dict) or not extra:
        return {}
    handler = _BY_LANGUAGE.get(target)
    return handler(extra) if handler else extra
