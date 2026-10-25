"""Çeviri kataloglarının sağlık kapısı.

Projede CI yok, bu yüzden katalog kayması ancak elle koşulan bir kapıyla
yakalanıyor. Bu komut deploy öncesi çalıştırılır ve şunları arar:

* **Bayat katalog** — kaynakta olup katalogda olmayan string. `locale/en`
  bir kez altı ay boyunca donmuştu: `POT-Creation-Date` sabit kaldığı için
  yirmi dokuz string hiç çıkarılmamıştı ve İngilizce arayüzde Türkçe
  görünüyorlardı.
* **Fuzzy girdi** — gettext bunları YOK SAYAR, yani çeviri varmış gibi
  görünürken metin msgid'e düşer. Üstelik `msgmerge` benzer bir girdiden
  yanlış çeviri kopyalayabiliyor; bir keresinde "Şifreyi sıfırla" için
  "Reset %(level)s" yazmıştı — msgid'de olmayan bir yer tutucuyla.
* **Eksik çeviri** — yayında olan bir arayüz dilinde boş msgstr. Türkçe için
  bu normaldir (kaynak metinler Türkçe, katalog bilinçli no-op), diğer diller
  için hata.
* **Yer tutucu uyumsuzluğu** — msgid ile msgstr'ın `%(ad)s` / `{ad}`
  kümeleri farklıysa çalışma anında metin bozulur ya da istisna fırlar.
* **Literal yüzde işareti** — `{% trans %}` içindeki `%`, makemessages
  tarafından `%%` olarak çıkarılıyor ama çalışma anında arama tek `%` ile
  yapılıyor; o msgid hiç eşleşmiyor. Böyle bir string kalıcı olarak
  çevrilemez durumdadır, `{ad}` kalıbına geçmek gerekir.

Çıkış kodu: sorun varsa 1 (CommandError), yoksa 0.
"""

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from services import languages

# Kaynak metinler Türkçe yazıldığı için TR katalogunda boş msgstr beklenen
# durum: Django msgid'e düşüyor ve doğru Türkçe metni gösteriyor.
NO_OP_CATALOGS = {'tr'}

_PY_PLACEHOLDER = re.compile(r'%\((\w+)\)[sd]')
_BRACE_PLACEHOLDER = re.compile(r'\{(\w+)\}')
_DOUBLE_PERCENT = re.compile(r'%%\(\w+\)[sd]')


def _parse(path: Path):
    """.po dosyasını (msgctxt, msgid, msgstr, flags, satır) kayıtlarına ayırır."""
    entries = []
    block, start = [], 0
    for lineno, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if raw.strip():
            if not block:
                start = lineno
            block.append(raw)
            continue
        if block:
            entries.append(_entry(block, start))
            block = []
    if block:
        entries.append(_entry(block, start))
    return [e for e in entries if e and e['msgid']]


def _entry(lines, lineno):
    flags, parts, current = [], {'msgctxt': [], 'msgid': [], 'msgstr': []}, None
    for line in lines:
        if line.startswith('#,'):
            flags += [f.strip() for f in line[2:].split(',')]
            continue
        if line.startswith('#'):
            continue
        for key in ('msgctxt', 'msgid_plural', 'msgid', 'msgstr'):
            if line.startswith(key + ' '):
                current = 'msgid' if key == 'msgid_plural' else key
                parts[current].append(_unquote(line[len(key) + 1:]))
                break
        else:
            if line.startswith('"') and current:
                parts[current].append(_unquote(line))
            elif line.startswith('msgstr['):
                current = 'msgstr'
                parts[current].append(_unquote(line.split(']', 1)[1].strip()))
    return {
        'msgctxt': ''.join(parts['msgctxt']),
        'msgid': ''.join(parts['msgid']),
        'msgstr': ''.join(parts['msgstr']),
        'flags': flags,
        'line': lineno,
    }


def _unquote(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')


class Command(BaseCommand):
    help = 'Çeviri kataloglarını bayatlık, fuzzy ve eksik çeviri için denetler.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict-empty', action='store_true',
            help='Türkçe katalogdaki boş çevirileri de hata say (no-op katalog '
                 'olduğu için varsayılan kapalı).',
        )

    def handle(self, *args, **opts):
        problems = []
        checked = 0

        for spec in languages.UI_LANGUAGES:
            path = Path(settings.LOCALE_PATHS[0]) / spec.code / 'LC_MESSAGES' / 'django.po'
            if not path.exists():
                problems.append(f'{spec.code}: katalog yok ({path})')
                continue

            entries = _parse(path)
            checked += len(entries)
            no_op = spec.code in NO_OP_CATALOGS and not opts['strict_empty']

            empty = fuzzy = 0
            for e in entries:
                where = f"{spec.code}:{e['line']}"
                label = e['msgid'][:60].replace('\n', ' ')

                if 'fuzzy' in e['flags']:
                    fuzzy += 1
                    problems.append(
                        f'{where}: FUZZY — gettext bunu yok sayar, metin '
                        f'çevrilmemiş görünür: "{label}"'
                    )

                if not e['msgstr'].strip():
                    empty += 1
                    if not no_op:
                        problems.append(f'{where}: boş çeviri: "{label}"')
                    continue

                for name, pattern in (('%()s', _PY_PLACEHOLDER), ('{}', _BRACE_PLACEHOLDER)):
                    want = set(pattern.findall(e['msgid']))
                    got = set(pattern.findall(e['msgstr']))
                    if want != got:
                        problems.append(
                            f'{where}: {name} yer tutucu uyumsuzluğu '
                            f'{sorted(want)} != {sorted(got)}: "{label}"'
                        )

            # Literal % sorunu kaynak taraflı: her katalogda aynı, bir kez bildir.
            if spec.code == settings.LANGUAGE_CODE:
                for e in entries:
                    if _DOUBLE_PERCENT.search(e['msgid']):
                        problems.append(
                            f"{spec.code}:{e['line']}: msgid literal '%%' içeriyor — "
                            f"çalışma anında arama tek '%' ile yapıldığı için bu "
                            f"string HİÇ eşleşmez. `{{ad}}` kalıbına geçir: "
                            f'"{e["msgid"][:50]}"'
                        )

            note = ' (no-op katalog, boşlar beklenen)' if no_op else ''
            self.stdout.write(
                f'{spec.code}: {len(entries)} girdi, {empty} boş{note}, {fuzzy} fuzzy'
            )

        if problems:
            self.stdout.write('')
            for p in problems:
                self.stdout.write(self.style.ERROR(f'  {p}'))
            raise CommandError(
                f'{len(problems)} katalog sorunu bulundu. '
                "Düzelt ya da `makemessages -l tr -l en --no-obsolete` koş."
            )

        self.stdout.write(self.style.SUCCESS(
            f'Kataloglar temiz ({checked} girdi, {len(languages.UI_LANGUAGES)} dil).'
        ))
