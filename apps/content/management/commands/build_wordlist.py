"""Kaynak dosyalardan ham kelime listesi üretir.

Üç kaynak desteklenir:

* **flelex**   — FLELex TSV (Fransızca). Seviye sütunu olan Beacco dosyası
  ya da frekans sütunlarından seviye türetilen CRF dosyası kabul edilir.
* **goethe**   — Goethe-Institut Wortliste PDF (Almanca A1–B1).
  `--level` ile hangi seviyeye yazılacağı belirtilir.
* **wordfreq** — `wordfreq` kütüphanesinden frekans listesi (Türkçe, Almanca
  B2–C1 vb.). Seviye ataması frekans bantlarıyla yapılır.

Çıktı: ``apps/wordbank/data/<hedef>/<seviye>.raw.json`` — yalnızca `rank` ve
`term` (zorunlu), ek olarak `part_of_speech` ve `extra` (opsiyonel). Bu dosyalar
``enrich_wordbank`` tarafından okunur ve Claude ile zenginleştirilir.

Kullanım::

    manage.py build_wordlist --target fr --source flelex \\
        --path dosya/FleLex_TT_Beacco.tsv

    manage.py build_wordlist --target de --source goethe \\
        --path dosya/A1_SD1_Wortliste_02.pdf --level A1

    manage.py build_wordlist --target de --source wordfreq \\
        --levels B2,C1 --exclude-existing

    manage.py build_wordlist --target tr --source wordfreq \\
        --levels A1,A2,B1,B2,C1
"""

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from services import languages

OUT_DIR = Path(__file__).resolve().parents[3] / 'wordbank' / 'data'

# --- FLELex POS eşlemesi --------------------------------------------------

_FLELEX_POS = {
    'NOM': 'noun', 'N': 'noun',
    'VER': 'verb', 'V': 'verb',
    'ADJ': 'adjective', 'A': 'adjective',
    'ADV': 'adverb',
    'PREP': 'preposition', 'PRP': 'preposition',
}

_FLELEX_CEFR = ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')

_FLELEX_SKIP_POS = {
    'PRO', 'DET', 'DET:POS', 'DET:ART', 'DETWH',
    'KON', 'CONJS', 'CONJC', 'INT',
    'PREPDET', 'PRP:det', 'PREPPRO', 'X',
}


def _parse_flelex(path):
    """FLELex TSV/CSV okur → {seviye: [{rank, term, part_of_speech}]}."""
    path = Path(path)
    with open(path, newline='', encoding='utf-8') as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters='\t,')
        reader = csv.DictReader(f, delimiter=dialect.delimiter)
        fields = reader.fieldnames or []

        has_level = 'level' in fields
        freq_keys = []
        for level in _FLELEX_CEFR:
            for pattern in (f'freq_{level}', f'freq_{level.lower()}'):
                if pattern in fields:
                    freq_keys.append((level, pattern))
                    break

        by_level = defaultdict(list)
        for row in reader:
            tag = (row.get('tag') or '').strip()
            if tag in _FLELEX_SKIP_POS:
                continue

            word = (row.get('word') or '').strip()
            if not word or len(word) < 2:
                continue

            pos = _FLELEX_POS.get(tag, '')

            if has_level:
                level = (row.get('level') or '').strip().upper()
                if level not in _FLELEX_CEFR:
                    continue
                freq = 0.0
                for lv, key in freq_keys:
                    if lv == level:
                        try:
                            freq = float(row.get(key, 0))
                        except (ValueError, TypeError):
                            pass
                        break
            else:
                best_level, best_freq = 'B2', 0.0
                for lv, key in freq_keys:
                    try:
                        val = float(row.get(key, 0))
                    except (ValueError, TypeError):
                        continue
                    if val > best_freq:
                        best_freq = val
                        best_level = lv
                level = best_level
                freq = best_freq

            by_level[level].append({
                'term': word,
                'part_of_speech': pos,
                '_freq': freq,
            })

    result = {}
    for level, items in by_level.items():
        items.sort(key=lambda x: -x['_freq'])
        for rank, item in enumerate(items, 1):
            del item['_freq']
            item['rank'] = rank
        result[level] = items
    return result


# --- Goethe PDF ayrıştırıcı -----------------------------------------------

_ARTICLE_RE = re.compile(
    r'^(der|die|das)\s+'
    r'([\wÄÖÜäöüß][\wÄÖÜäöüß/-]*)'
    r'(?:\s*,\s*([^A-ZÄÖÜ\n]*))?',
    re.UNICODE,
)

_HEADER_PATTERNS = (
    'VS_02_', 'Seite ', 'WORTLISTE', 'INVENTARE', 'INVeNTAre',
    'ZERTIFIKAT', 'GOETHE-ZERTIFIKAT', 'START DEUTSCH', 'FIT IN',
    'Alphabetische', 'wortliste', 'LITerATur', 'LITERATUR',
)

_SECTION_HEADERS = re.compile(
    r'^(zahlen|uhrzeit|zeitmaße|zeitangaben|wochentage?|monat|'
    r'jahr|währung|farben|himmelsrichtung|wortgruppen|maße|datum|'
    r'länder|themen|inventare|vorwort|inhalt|literatur|abkürzung|'
    r'berufe|familie|person|wohnen|umwelt|reisen|essen|einkaufen|'
    r'dienstleistung|erziehung|arbeit|freizeit|gesundheit|sprache|'
    r'grammatik|kommunikation|anweisung|schule|feiertage|'
    r'tag\s*/\s*tageszeiten|woche\s*/\s*wochentage|monat\s*/\s*monats)',
    re.IGNORECASE,
)

# B1 fiil çekim kalıbı: "verb, konjuge, geçmiş, hat/ist partizip"
_VERB_CONJ_RE = re.compile(
    r'^([\wäöüß]+(?:en|ern|eln))\s*,\s*\w',
    re.UNICODE,
)

# Parantezli giriş: "(sich) verb" veya "(etwas) verb"
_PAREN_ENTRY_RE = re.compile(
    r'^\(([^)]+)\)\s*([\wäöüß][\wäöüß-]*)',
    re.UNICODE,
)

# Yalın giriş: tek sözcük
_BARE_WORD_RE = re.compile(
    r'^([\wÄÖÜäöüß][\wÄÖÜäöüß-]*)\s*$',
    re.UNICODE,
)


def _clean_term(s):
    s = unicodedata.normalize('NFC', s.strip())
    s = re.sub(r'\s+', ' ', s)
    return s


def _is_header(line):
    for pat in _HEADER_PATTERNS:
        if pat in line:
            return True
    return False


def _strip_page_header(line):
    """Sayfa başlığını satırın başından temizler.

    A1: "VS_02_280312 Seite 9A" + içerik
    A2: "8 WORTLISTEA2_Wortliste_04_050526" + içerik
    B1: "17 WORTLISTEVS_03" + içerik
    """
    # A1 başlığı
    m = re.match(r'VS_\d+_\d+\s*Seite\s*\d+[A-Z]?\s*', line)
    if m:
        return line[m.end():]
    # A2 başlığı
    m = re.match(r'\d+\s*WORTLISTE\w*_\d+\s*', line)
    if m:
        return line[m.end():]
    # B1 başlığı
    m = re.match(r'\d+\s*WORTLISTEVS_\d+\s*', line)
    if m:
        return line[m.end():]
    # Genel sayfa numarası başlığı
    m = re.match(r'(GOETHE-ZERTIFIKAT\s+[AB]\d|ZERTIFIKAT\s+B\d)\s*', line)
    if m:
        return line[m.end():]
    return line


def _parse_goethe_a1a2(pages_text):
    """A1/A2 Goethe Wortliste: her satırda terim + örnek cümle."""
    entries = []
    seen = set()

    for text in pages_text:
        lines = text.split('\n')
        for raw_line in lines:
            # Devam satırı (boşlukla başlar)
            if raw_line and raw_line[0] in (' ', '\t'):
                continue

            line = _strip_page_header(raw_line)
            stripped = line.strip()
            if not stripped or len(stripped) < 2:
                continue
            if _is_header(stripped):
                continue
            if _SECTION_HEADERS.match(stripped):
                continue

            # İsim girişi: "der/die/das Term, -çoğul Örnek..."
            m = _ARTICLE_RE.match(stripped)
            if m:
                article = m.group(1)
                term = _clean_term(m.group(2))
                if not term or len(term) < 2 or term.lower() in seen:
                    continue
                extra = {'gender': article}
                plural_raw = (m.group(3) or '').strip()
                if plural_raw:
                    plural_raw = re.sub(r'\s+', '', plural_raw)
                    if '¨' in plural_raw:
                        extra['umlaut_plural'] = True
                    suffix = plural_raw.strip('¨').lstrip('-').rstrip('.')
                    if suffix and suffix not in ('–', '-'):
                        extra['plural_suffix'] = suffix
                entries.append({
                    'term': term,
                    'part_of_speech': 'noun',
                    'extra': extra,
                })
                seen.add(term.lower())
                continue

            # Parantezli: "(sich) anmelden ..."
            pm = _PAREN_ENTRY_RE.match(stripped)
            if pm:
                prefix = pm.group(1).strip()
                verb = _clean_term(pm.group(2))
                full = f'({prefix}) {verb}'
                if full.lower() not in seen:
                    entries.append({
                        'term': full,
                        'part_of_speech': 'verb',
                        'extra': {},
                    })
                    seen.add(full.lower())
                continue

            # Diğer giriş: satırın ilk sözcüğü terimdir
            # Satır boşlukla başlamıyor (yukarıda kontrol edildi),
            # dolayısıyla ilk sözcük giriş adayı.
            first_m = re.match(
                r'^([\wäöüß][\wäöüß-]*)',
                stripped, re.UNICODE,
            )
            if first_m:
                candidate = first_m.group(1)
                # Büyük harfle başlayan kelimeler genellikle örnek cümle
                # başıdır — ama bazı istisnalar var
                if candidate[0].isupper():
                    # Achtung gibi büyük harfli girişler sadece isim olarak
                    # yukarıda yakalanmalıydı (der/die/das ile). Büyük harfli
                    # ama artikelsiz girişler nadir — atla.
                    continue
                if candidate.lower() in seen:
                    continue
                if len(candidate) < 2:
                    continue
                # Sayısal giriş atla
                if candidate[0].isdigit():
                    continue
                entries.append({
                    'term': _clean_term(candidate),
                    'part_of_speech': '',
                    'extra': {},
                })
                seen.add(candidate.lower())

    return entries


def _parse_goethe_b1(pages_text):
    """B1 Goethe Wortliste: iki sütunlu düzen, terimler sol sütunda."""
    entries = []
    seen = set()

    for text in pages_text:
        lines = text.split('\n')
        for raw_line in lines:
            line = _strip_page_header(raw_line)
            stripped = line.strip()
            if not stripped or len(stripped) < 2:
                continue
            if _is_header(stripped):
                continue
            if _SECTION_HEADERS.match(stripped):
                continue

            # Numaralı örnek cümle
            if re.match(r'^\d+\.\s+[A-ZÄÖÜ]', stripped):
                continue

            # İsim girişi
            m = _ARTICLE_RE.match(stripped)
            if m:
                article = m.group(1)
                term = _clean_term(m.group(2))
                if not term or len(term) < 2 or term.lower() in seen:
                    continue
                extra = {'gender': article}
                plural_raw = (m.group(3) or '').strip()
                if plural_raw:
                    plural_raw = re.sub(r'\s+', '', plural_raw)
                    if '¨' in plural_raw:
                        extra['umlaut_plural'] = True
                    suffix = plural_raw.strip('¨').lstrip('-').rstrip('.')
                    if suffix and suffix not in ('–', '-'):
                        extra['plural_suffix'] = suffix
                entries.append({
                    'term': term,
                    'part_of_speech': 'noun',
                    'extra': extra,
                })
                seen.add(term.lower())
                continue

            # Fiil + çekim: "verb, konjuge ..."
            vm = _VERB_CONJ_RE.match(stripped)
            if vm:
                verb = _clean_term(vm.group(1))
                if verb.lower() not in seen and len(verb) >= 3:
                    entries.append({
                        'term': verb,
                        'part_of_speech': 'verb',
                        'extra': {},
                    })
                    seen.add(verb.lower())
                continue

            # Parantezli: "(sich) verb ..."
            pm = _PAREN_ENTRY_RE.match(stripped)
            if pm:
                prefix = pm.group(1).strip()
                verb = _clean_term(pm.group(2))
                full = f'({prefix}) {verb}'
                if full.lower() not in seen:
                    entries.append({
                        'term': full,
                        'part_of_speech': 'verb',
                        'extra': {},
                    })
                    seen.add(full.lower())
                continue

            # Yalın giriş: tek kelime veya kısa giriş
            bare = _BARE_WORD_RE.match(stripped)
            if bare:
                candidate = _clean_term(bare.group(1))
                if len(candidate) < 2 or candidate.lower() in seen:
                    continue
                if len(candidate) == 1 and candidate.isupper():
                    continue
                if candidate[0].isdigit():
                    continue
                if re.match(r'^[IVXL]+$', candidate):
                    continue
                entries.append({
                    'term': candidate,
                    'part_of_speech': '',
                    'extra': {},
                })
                seen.add(candidate.lower())
                continue

            # Tire ile biten: "heutig-", "ander-"
            dash = re.match(r'^([\wäöüß][\wäöüß]*-)\s*$', stripped, re.UNICODE)
            if dash:
                candidate = _clean_term(dash.group(1))
                if candidate.lower() not in seen:
                    entries.append({
                        'term': candidate,
                        'part_of_speech': '',
                        'extra': {},
                    })
                    seen.add(candidate.lower())
                continue

            # Eğik çizgili giriş: "hier/hier-" → "hier"
            slash = re.match(
                r'^([\wäöüß]+)/([\wäöüß-]+)\s*$',
                stripped, re.UNICODE,
            )
            if slash:
                candidate = _clean_term(slash.group(1))
                if candidate.lower() not in seen and len(candidate) >= 2:
                    entries.append({
                        'term': candidate,
                        'part_of_speech': '',
                        'extra': {},
                    })
                    seen.add(candidate.lower())

    return entries


def _find_alphabet_start(reader):
    """İlk harf bölümü işaretçisini (A, B, ...) bularak alfabetik listenin
    başladığı sayfayı döndürür.

    Goethe Wortliste PDF'lerinde her harf bölümü tek harflik bir satırla
    ya da sayfa başlığının sonundaki harfle başlar (ör. "Seite 9A").
    İlk işaretçinin bulunduğu sayfa listenin başıdır.
    """
    for i in range(len(reader.pages)):
        text = reader.pages[i].extract_text() or ''
        for ln in text.split('\n'):
            s = ln.strip()
            # "Seite 9A" biçiminde başlık
            if re.match(r'.*Seite\s*\d+\s*A$', s):
                return i
            # Yalnız "A" satırı — ama İçindekiler sayfası değil (sayfa>4)
            if s == 'A' and i > 4:
                return i
    return None


def _find_alphabet_end(reader, start_idx):
    """Arka boşluğu (Literatur, Grammatik) bulur.

    Yalnızca PDF'in son %20'sinde arar — erken sayfalardaki İçindekiler
    tablosu yanlış pozitif veriyor.
    """
    total = len(reader.pages)
    search_start = max(start_idx, int(total * 0.8))
    for i in range(total - 1, search_start, -1):
        text = reader.pages[i].extract_text() or ''
        if re.search(r'LITerATur|LITERATUR|Literatur', text):
            return i
        if re.search(r'^Grammatik\s*$', text, re.MULTILINE):
            return i
    return total


def _parse_goethe_pdf(path, level):
    """Goethe Wortliste PDF'inden kelime listesi çıkarır."""
    from PyPDF2 import PdfReader

    reader = PdfReader(str(path))
    total_pages = len(reader.pages)

    # Alfabetik listenin başlangıcını bul
    start_idx = _find_alphabet_start(reader)
    if start_idx is None:
        # Fallback: bilinen sayfa numaraları
        start_idx = {'A1': 8, 'A2': 7, 'B1': 15}.get(level, 5)

    end_idx = _find_alphabet_end(reader, start_idx)

    pages_text = [
        reader.pages[i].extract_text() or ''
        for i in range(start_idx, end_idx)
    ]

    if level in ('A1', 'A2'):
        entries = _parse_goethe_a1a2(pages_text)
    else:
        entries = _parse_goethe_b1(pages_text)

    return entries


# --- wordfreq ayrıştırıcı ------------------------------------------------

_FREQ_BANDS = {
    'A1': (0, 1000),
    'A2': (1000, 2000),
    'B1': (2000, 3500),
    'B2': (3500, 5500),
    'C1': (5500, 8000),
    # C2 = frekans kuyruğu. Türkçe ve Almanca'da C2 için resmî CEFR listesi
    # YOK (Goethe yalnızca A1–B1 yayınlıyor, Türkçe'de hiç yok), bu yüzden
    # seviye frekansla türetiliyor — planın Almanca B2–C1 için öngördüğü
    # yöntemin aynısı.
    'C2': (8000, 12000),
}

#: Frekans listesinin kuyruğunda çöp oranı yükseliyor. ÖLÇÜLDÜ: Türkçe
#: listesinde 43 kayıt hiçbir dilde karşılık alamadı ve sebebi terimlerin
#: kendisiydi — özel adlar (`zonguldak`, `vincent`), listeye sızmış İngilizce
#: kelimeler (`the`, `you`, `off`), bozuk token'lar (`cc`, `u00`, `ıı`,
#: `ınstagram`). C2 bandı daha derinde olduğu için filtre orada sıkılaşıyor.
_TAIL_MIN_LENGTH = 3

#: Latin alfabesinde yazılan dillerde bu diziler neredeyse yalnızca
#: kırpılmış/bozuk token'larda görülüyor.
_BROKEN_TOKEN_HINTS = ('u00', 'x00', '\\u', '\\x')


def _parse_wordfreq(lang_code, levels, exclude_terms=None, top_n=10000):
    """wordfreq kütüphanesinden frekans listesi üretir."""
    try:
        from wordfreq import top_n_list
    except ImportError:
        raise CommandError(
            'wordfreq kütüphanesi kurulu değil. '
            'requirements.txt\'e ekleyip yeniden kurun: pip install wordfreq'
        )

    exclude = {t.lower() for t in (exclude_terms or [])}
    words = top_n_list(lang_code, top_n, wordlist='best')

    # C2 istendiğinde filtre sıkılaşıyor: o bant frekans kuyruğunda ve
    # oradaki çöp oranı ölçülmüş biçimde yüksek (bkz. _TAIL_MIN_LENGTH).
    strict = 'C2' in levels
    min_length = _TAIL_MIN_LENGTH if strict else 2

    filtered = []
    for word in words:
        if len(word) < min_length:
            continue
        if word.lower() in exclude:
            continue
        if not any(c.isalpha() for c in word):
            continue
        if strict:
            lowered = word.lower()
            # Rakam ya da noktalama taşıyan token sözlük kelimesi değil.
            if not lowered.isalpha():
                continue
            if any(hint in lowered for hint in _BROKEN_TOKEN_HINTS):
                continue
            # Aynı harfin üç kez üst üste tekrarı (ör. `aaa`) bozuk token.
            if any(lowered[i] == lowered[i + 1] == lowered[i + 2]
                   for i in range(len(lowered) - 2)):
                continue
        filtered.append(word)

    by_level = {}
    for level in levels:
        if level not in _FREQ_BANDS:
            continue
        start, end = _FREQ_BANDS[level]
        level_words = filtered[start:end]
        by_level[level] = [
            {'rank': rank, 'term': word, 'part_of_speech': '', 'extra': {}}
            for rank, word in enumerate(level_words, 1)
        ]
    return by_level


# --- Komut ----------------------------------------------------------------

class Command(BaseCommand):
    help = 'Kaynak dosyalardan ham kelime listesi üretir (.raw.json).'

    def add_arguments(self, parser):
        parser.add_argument('--target', required=True,
                            help='Hedef dil kodu (fr, de, tr).')
        parser.add_argument('--source', required=True,
                            choices=['flelex', 'goethe', 'wordfreq'],
                            help='Kaynak biçimi.')
        parser.add_argument('--path', nargs='+', default=[],
                            help='Kaynak dosya yolları.')
        parser.add_argument('--level', default=None,
                            help='Goethe PDF için hedef seviye (A1, A2, B1).')
        parser.add_argument('--levels', default=None,
                            help='wordfreq için seviyeler (virgülle ayrılmış).')
        parser.add_argument('--top', type=int, default=10000,
                            help='wordfreq: en çok N kelime (varsayılan 10000).')
        parser.add_argument('--force-level', action='store_true',
                            help='Sicilde olmayan seviyeyi de üret. Yeni '
                                 'seviye kurarken sıra: ÖNCE içerik, SONRA '
                                 'sicil — erken eklemek boş sayfa yayınlar.')
        parser.add_argument('--exclude-existing', action='store_true',
                            help='wordfreq: mevcut seviyelerdeki kelimeleri dışla.')
        parser.add_argument('--out-dir', default=None,
                            help=f'Çıktı dizini (varsayılan: {OUT_DIR}/<hedef>/).')
        parser.add_argument('--check', action='store_true',
                            help='Yazmadan kontrol et; fark varsa non-zero çıkış.')
        parser.add_argument('--stats', action='store_true',
                            help='Kaynak dosyayı analiz et, yazmadan istatistik göster.')

    def handle(self, *args, **opts):
        target = opts['target']
        try:
            spec = languages.get(target)
        except languages.UnknownLanguage:
            raise CommandError(f'Sicilde olmayan dil: {target}')

        source = opts['source']
        out_dir = Path(opts['out_dir']) if opts['out_dir'] else OUT_DIR / target

        if source == 'flelex':
            by_level = self._handle_flelex(opts)
        elif source == 'goethe':
            by_level = self._handle_goethe(opts)
        elif source == 'wordfreq':
            by_level = self._handle_wordfreq(target, spec, opts)
        else:
            raise CommandError(f'Bilinmeyen kaynak: {source}')

        if opts['stats']:
            self._show_stats(by_level)
            return

        total = 0
        for level in sorted(by_level):
            if level not in spec.cefr_levels and not opts['force_level']:
                # Sicil, içeriği OLAN seviyeleri listeliyor. Yeni bir seviye
                # üretirken sıra önemli: önce içerik, sonra sicil. Sicile
                # erken eklemek seviyenin sayfasını boşken yayına açar.
                self.stdout.write(self.style.WARNING(
                    f'  {level}: sicildeki CEFR seviyelerinde yok — atlandı. '
                    '(Yeni seviye üretiyorsanız --force-level verin.)'
                ))
                continue

            items = by_level[level]
            if not items:
                self.stdout.write(f'  {level}: boş — atlandı.')
                continue

            path = out_dir / f'{level.lower()}.raw.json'
            body = json.dumps(items, ensure_ascii=False, indent=2) + '\n'

            if opts['check']:
                if path.exists():
                    existing = path.read_text(encoding='utf-8')
                    if existing == body:
                        self.stdout.write(f'  {level}: {len(items)} terim ✓')
                    else:
                        self.stdout.write(self.style.ERROR(
                            f'  {level}: dosya farklı ({len(items)} terim)'
                        ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  {level}: dosya yok ({len(items)} terim yazılacak)'
                    ))
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
            self.stdout.write(f'  {level}: {len(items)} terim → {path.name}')
            total += len(items)

        if not opts['check'] and not opts['stats']:
            self.stdout.write(self.style.SUCCESS(
                f'Bitti: {total} terim yazıldı → {out_dir}/'
            ))

    def _handle_flelex(self, opts):
        paths = opts['path']
        if not paths:
            raise CommandError('--path gerekli (FLELex TSV/CSV dosyası).')
        return _parse_flelex(paths[0])

    def _handle_goethe(self, opts):
        paths = opts['path']
        level = (opts.get('level') or '').upper()
        if not paths:
            raise CommandError('--path gerekli (Goethe Wortliste PDF).')
        if not level:
            raise CommandError('--level gerekli (A1, A2 veya B1).')

        entries = _parse_goethe_pdf(paths[0], level)
        for rank, entry in enumerate(entries, 1):
            entry['rank'] = rank

        self.stdout.write(f'  {level}: PDF\'den {len(entries)} giriş çıkarıldı.')
        return {level: entries}

    def _handle_wordfreq(self, target, spec, opts):
        levels_str = opts.get('levels') or ''
        levels = [l.strip().upper() for l in levels_str.split(',') if l.strip()]
        if not levels:
            levels = list(spec.cefr_levels)

        exclude = set()
        if opts['exclude_existing']:
            existing_dir = OUT_DIR / target
            if existing_dir.exists():
                for pattern in ('*.json', '*.raw.json'):
                    for f in existing_dir.glob(pattern):
                        try:
                            items = json.loads(f.read_text(encoding='utf-8'))
                            for item in items:
                                term = (item.get('term') or '').strip().lower()
                                if term:
                                    exclude.add(term)
                        except (json.JSONDecodeError, OSError):
                            pass
            if exclude:
                self.stdout.write(f'  {len(exclude)} mevcut terim dışlanıyor.')

        return _parse_wordfreq(target, levels, exclude_terms=exclude,
                               top_n=opts['top'])

    def _show_stats(self, by_level):
        total = 0
        for level in sorted(by_level):
            items = by_level[level]
            total += len(items)
            pos_counts = defaultdict(int)
            for item in items:
                pos = item.get('part_of_speech') or '(boş)'
                pos_counts[pos] += 1

            self.stdout.write(f'\n  {level}: {len(items)} terim')
            for pos, count in sorted(pos_counts.items(), key=lambda x: -x[1]):
                self.stdout.write(f'    {pos:15s} {count}')
            if items:
                self.stdout.write(
                    f'    ilk 5: {", ".join(i["term"] for i in items[:5])}'
                )
                self.stdout.write(
                    f'    son 5: {", ".join(i["term"] for i in items[-5:])}'
                )

        self.stdout.write(self.style.SUCCESS(f'\n  Toplam: {total} terim'))
