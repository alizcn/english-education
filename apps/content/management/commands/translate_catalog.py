"""Boş `.po` girdilerini Claude ile çevirir — DEVAM EDEBİLİR.

Niçin gerekli: msgid'ler Türkçe (kabul edilen borç — 605 string + 657 şablon
referansını İngilizce'ye çevirmek kapsam dışıydı). Yeni bir arayüz dili
eklemek bu yüzden "Türkçe'den çevir" işi oluyor ve elle 642 string yazmak
günler alır.

Yalnızca **boş** `msgstr` doldurulur; mevcut çeviriye ve `fuzzy` işaretine
dokunulmaz — elle düzeltilmiş bir metni model yeniden yazarsa gözden geçirme
emeği çöpe gider. `--overwrite-fuzzy` ile fuzzy girdiler de tazelenebilir.

Biçim kuralları (ölçülmüş iki tuzağa karşı):

* `%(ad)s` ve `{ad}` yer tutucuları birebir korunur. Eksik ya da uydurma
  yer tutucu çalışma anında `KeyError`/bozuk metin demek, bu yüzden
  doğrulama onu reddediyor.
* `%` tek başına geçtiğinde gettext onu biçim dizgesi sanıyor; msgid'de
  olmayan bir `%` eklenmesi de reddediliyor.

Kullanım::

    manage.py translate_catalog --lang fr --batch 25
    manage.py translate_catalog --lang de --status
"""

import re
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from services import claude_client as claude
from services import languages

#: `%(ad)s`, `%s`, `%d` ve `{ad}` — korunması gereken her şey.
_PLACEHOLDER = re.compile(r'%\([^)]*\)[sdifr]|%[sdifr]|\{[^{}]*\}')

DEFAULT_BATCH = 25


def _locale_paths():
    """`settings.LOCALE_PATHS` ya da proje kökündeki `locale/`."""
    paths = [Path(p) for p in getattr(settings, 'LOCALE_PATHS', ())]
    if paths:
        return paths
    return [Path(settings.BASE_DIR) / 'locale']


def _catalog_path(lang):
    for root in _locale_paths():
        path = root / lang / 'LC_MESSAGES' / 'django.po'
        if path.exists():
            return path
    return None


def placeholders(text):
    return sorted(_PLACEHOLDER.findall(text or ''))


class Command(BaseCommand):
    help = 'Boş .po girdilerini Claude ile çevirir.'

    def add_arguments(self, parser):
        parser.add_argument('--lang', required=True,
                            help='Hedef katalog dili (fr, de, …).')
        parser.add_argument('--source', default='tr',
                            help='msgid dili (varsayılan tr).')
        parser.add_argument('--batch', type=int, default=DEFAULT_BATCH,
                            help=f'Çağrı başına string (varsayılan {DEFAULT_BATCH}).')
        parser.add_argument('--limit', type=int, default=None,
                            help='En çok bu kadar parça işle.')
        parser.add_argument('--overwrite-fuzzy', action='store_true',
                            help='Fuzzy girdileri de yeniden çevir.')
        parser.add_argument('--model', default=None)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--status', action='store_true')

    def handle(self, *args, **opts):
        try:
            import polib
        except ModuleNotFoundError:
            raise CommandError(
                'polib gerekiyor: requirements.txt içinde, image yeniden '
                'kurulmalı (docker compose build).'
            )

        lang = opts['lang']
        try:
            spec = languages.get(lang)
            source = languages.get(opts['source'])
        except languages.UnknownLanguage as e:
            raise CommandError(str(e))

        path = _catalog_path(lang)
        if path is None:
            raise CommandError(
                f'{lang} katalogu yok. Önce: manage.py makemessages -l {lang}'
            )

        catalog = polib.pofile(str(path), wrapwidth=0)
        pending = [
            entry for entry in catalog
            if not entry.obsolete and (
                not entry.msgstr
                or (opts['overwrite_fuzzy'] and 'fuzzy' in entry.flags)
            )
        ]

        if opts['status'] or opts['dry_run']:
            live = [e for e in catalog if not e.obsolete]
            fuzzy = [e for e in live if 'fuzzy' in e.flags]
            # FUZZY ÇEVRİLİ SAYILMIYOR: gettext fuzzy girdiyi çalışma anında
            # YOK SAYIYOR, yani kullanıcı msgid'i (Türkçe) görüyor. Bu rapor
            # eskiden fuzzy'yi dolu kabul ediyordu ve `makemessages`in
            # benzerlik eşleştirmesiyle kopyaladığı bayat çeviriler yüzünden
            # katalogu %100 gösteriyordu — ölçülmüş: 39 Almanca girdide
            # `%(lang)s` yer tutucusu düşmüştü ve sayfa Türkçe çıkıyordu.
            usable = [e for e in live if e.msgstr and 'fuzzy' not in e.flags]
            self.stdout.write(
                f'{lang}: {len(usable)}/{len(live)} kullanılabilir, '
                f'{len(live) - len(usable)} eksik '
                f'({len(fuzzy)} fuzzy — gettext bunları yok sayıyor, '
                '--overwrite-fuzzy ile tazelenir).'
            )
            if opts['dry_run'] and pending:
                for entry in pending[:5]:
                    self.stdout.write(f'  - {entry.msgid[:70]}')
            return

        if not pending:
            self.stdout.write(self.style.SUCCESS(f'{lang}: eksik girdi yok.'))
            return

        overrides = {'CLAUDE_MODEL': opts['model']} if opts['model'] else {}
        chunks = [pending[i:i + opts['batch']]
                  for i in range(0, len(pending), opts['batch'])]
        if opts['limit'] is not None:
            chunks = chunks[:opts['limit']]

        filled = skipped = failed_chunks = 0
        with claude.options(**overrides):
            for index, chunk in enumerate(chunks, 1):
                self.stdout.write(
                    f'[{index}/{len(chunks)}] {len(chunk)} string çevriliyor…'
                )
                try:
                    results = claude.translate_ui_strings(
                        [e.msgid for e in chunk],
                        source_name=source.english_name,
                        target_name=spec.english_name,
                    )
                except claude.ClaudeClientError as exc:
                    if exc.reason == 'session_limit':
                        self.stdout.write(self.style.WARNING(
                            'Oturum limiti. Yazılanlar kaydedildi; komutu '
                            'sonra tekrar koşun.'
                        ))
                        catalog.save(str(path))
                        sys.exit(75)
                    # Tek bozuk yanıt bütün koşuyu ÖLDÜRMEMELİ: ölçülmüş
                    # hata, modelin uzun bir HTML'li dizgede JSON'u yarıda
                    # kesmesiydi ve `CommandError` yeniden deneme döngüsünü
                    # de kırıyordu (`until` yalnızca 75'te bekliyor). Parça
                    # atlanıyor, kalanı devam ediyor ve komut sonunda 75 ile
                    # çıkıp döngüye "tekrar koş" diyor — girdiler hâlâ boş
                    # olduğu için bir sonraki turda yine sıraya giriyorlar.
                    self.stdout.write(self.style.WARNING(
                        f'  parça atlandı ({exc}) — sonraki turda tekrar '
                        'denenecek.'
                    ))
                    failed_chunks += 1
                    continue

                for entry in chunk:
                    value = (results.get(entry.msgid) or '').strip()
                    if not value:
                        skipped += 1
                        continue
                    problem = self._check(entry.msgid, value)
                    if problem:
                        self.stdout.write(self.style.WARNING(
                            f'  atlandı ({problem}): {entry.msgid[:50]}'
                        ))
                        skipped += 1
                        continue
                    entry.msgstr = value
                    # Model çevirisi gözden geçirilmedi; fuzzy işaretlemek
                    # gettext'in onu YOK SAYMASI demek olurdu, o yüzden
                    # işaret konmuyor. Gözden geçirme ayrı bir adım.
                    if 'fuzzy' in entry.flags:
                        entry.flags.remove('fuzzy')
                    filled += 1

                catalog.save(str(path))

        self.stdout.write(self.style.SUCCESS(
            f'{lang}: {filled} girdi çevrildi, {skipped} atlandı -> {path}\n'
            f'Şimdi: manage.py compilemessages -l {lang}'
        ))
        if failed_chunks:
            self.stdout.write(self.style.WARNING(
                f'{failed_chunks} parça bozuk yanıt yüzünden atlandı; '
                f'komut 75 ile çıkıyor ki devam döngüsü tekrar koşsun.'
            ))
            sys.exit(75)

    @staticmethod
    def _check(msgid, msgstr):
        """Biçim bozukluklarını yakalar; sorun varsa açıklama döner."""
        want, got = placeholders(msgid), placeholders(msgstr)
        if want != got:
            missing = sorted(set(want) - set(got))
            extra = sorted(set(got) - set(want))
            parts = []
            if missing:
                parts.append(f'eksik {missing}')
            if extra:
                parts.append(f'fazla {extra}')
            return 'yer tutucu ' + ', '.join(parts or ['sırası farklı'])
        # Yer tutucu dışında kalan tek `%` gettext'i biçim dizgesi sanmaya
        # itiyor ve çalışma anında metin bozuluyor.
        bare_id = _PLACEHOLDER.sub('', msgid).count('%')
        bare_str = _PLACEHOLDER.sub('', msgstr).count('%')
        if bare_str > bare_id:
            return 'msgid\'de olmayan % işareti'
        return ''
