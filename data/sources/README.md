# Kelime listesi kaynakları

Bu dizin **ham kaynak dosyaları** tutar: dört dilin seviye omurgası (hangi
kelime hangi CEFR seviyesinde). Dosyalar repoya konmaz — `.gitignore`
kapsamında; lisansları yeniden dağıtıma izin vermiyor ya da boyutları büyük.
Buradaki dosyalar yalnızca `build_wordlist` komutunun girdisi.

Üretim zinciri:

```
data/sources/<ham dosya>
  → manage.py build_wordlist --target <dil>      (lemma + seviye, deterministik)
  → apps/wordbank/data/<dil>/<seviye>.raw.json
  → manage.py enrich_wordbank --target <dil> --native <dil>   (Claude: anlam, örnek)
  → manage.py export_content --kind wordbank --target <dil>
  → apps/wordbank/data/<dil>/<seviye>.json       (gözden geçirilebilir artefakt)
  → manage.py load_wordbank --target <dil>
```

Kaynaklardan **yalnızca** şu alanlar alınır: başlık kelime (lemma), CEFR
seviyesi, sözcük türü, Almanca isimlerde artikel ve çoğul. Tanımlar, örnek
cümleler ve açıklamalar kopyalanmaz — onlar platformda üretilir. Kullanıcıya
görünen atıf sayfası: `templates/seo/licenses.html` (adres `/licenses/`),
metni `services/languages.py` sicilindeki `wordlist_source` ve `license_note`
alanlarından geliyor.

## Diller

### Fransızca — FLELex-CRF

* İndirme: <https://cental.uclouvain.be/cefrlex/flelex/download/>
* Biçim: 8 kolonlu TSV, 17.871 lemma, seviye bazlı frekans
* Seviye **deterministik** — LLM gerekmiyor, en güvenilir kaynağımız
* Lisans: CC BY-NC. Atıf: François, Gala, Watrin & Fairon (LREC 2014)
* Dosya: `FLELex_CRF.tsv`

### Almanca — Goethe Wortliste (A1–B1) + wordfreq (B2–C1)

* A1: <https://www.goethe.de/pro/relaunch/prf/ca/A1_SD1_Wortliste_02.pdf>
* B1: <https://www.goethe.de/pro/relaunch/prf/da/Goethe-Zertifikat_B1_Wortliste.pdf>
* Artikel ve çoğul biçim listede var — `BankWord.extra` oradan doluyor
* PDF okuma: `PyPDF2` (zaten kurulu)
* Lisans: Goethe-Institut telifi; çoğaltma kısıtlı, yalnızca başlık kelime alındı
* B2–C1 için resmî liste **yok**:
  * DAFlex (<https://cental.uclouvain.be/cefrlex/daflex/>) ideal olurdu ama
    2021'den beri "manuel düzeltme bitince" notuyla indirilemiyor
  * IDS DeReWo en yetkili kaynak ama **NC-ND** (türev yasak) → kullanılamaz
  * Çözüm: `wordfreq('de')` artığından A1–B1 dışı en sık lemmalar, seviye Claude ile
* Dosyalar: `goethe_a1.pdf`, `goethe_a2.pdf`, `goethe_b1.pdf`

### Türkçe — wordfreq

* Resmî CEFR listesi yok (akademik literatür de bunu söylüyor)
* `wordfreq.top_n_list('tr', 25000)` → filtre → lemmatizasyon + seviye Claude ile
* Yedek kaynak: Leipzig Corpora TR (<https://wortschatz.uni-leipzig.de/en/download>),
  indirmeleri CC BY
* Lisans: wordfreq CC BY-SA 4.0 — Robyn Speer
* Dosya üretimi: `python -c "import wordfreq, json; ..."` (ham dosya gerekmez)

### İngilizce — Oxford 3000 / 5000

* `words/Oxford_*.xlsx` (repo içinde, eski karar)
* Oxford 3000 → A1–B2, Oxford 5000 → B2–C1
* **C2 için Oxford listesi yok**; mevcut C2 (250 kelime) frekans türevi
* Lisans: Oxford University Press kelime listeleri

## Not

Lisans değerlendirmeleri hukuki görüş değildir. Mevcut Oxford listesi de OUP
telifli ve sitede yayınlanıyor — bu risk profili İngilizce'de zaten kabul
edilmiş durumda.
