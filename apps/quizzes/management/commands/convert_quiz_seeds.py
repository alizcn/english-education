"""Eski düz seed dosyalarını yeni enum'a ve yeni düzene taşır — TEK SEFERLİK.

İki iş birden:

**1. Soru tipi enum'u.** Eski isimler dil çiftini gömüyordu::

    translate_en_tr  ->  translate_to_native   (hedef dilde sor, ana dilde cevapla)
    translate_tr_en  ->  translate_to_target   (ana dilde sor, hedef dilde cevapla)

Eşleme yöne bakılarak kuruldu, isme değil: `translate_en_tr` İngilizce
prompt + Türkçe cevap taşıyor, yani hedef dilden ana dile çeviri.
Dil çifti artık `QuizSession.target_language`/`native_language` alanlarında;
enum sabit dört değer.

**2. Dizin düzeni.** ``seeds/<slug>.json`` tek dosyada hem çeviri hem de
hedef-dil-içi soruları tutuyordu::

    seeds/<hedef>/mono/<slug>.json   fill_blank + multiple_choice (ana dilden bağımsız)
    seeds/<hedef>/<ana>/<slug>.json  translate_to_*               (ana dil başına)

Ayrım üretimi %33 azaltıyor: mono sorular hedef dil başına BİR KEZ
üretiliyor, her ana dile aynı dosyadan ekleniyor (`seed_quizzes` birleştiriyor).

`--check` ile yazmadan ne olacağı görülür. Eski dosyalar `--prune` verilmezse
yerinde bırakılır; `seed_quizzes` iç içe düzen varsa onu tercih ettiği için
ikisi bir arada sorun çıkarmıyor.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from services import languages

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / 'seeds'

#: Yöne göre eşleme — isme göre değil.
TYPE_MAP = {
    'translate_en_tr': 'translate_to_native',
    'translate_tr_en': 'translate_to_target',
}

MONO_TYPES = {'fill_blank', 'multiple_choice'}
PAIR_TYPES = set(TYPE_MAP.values())


class Command(BaseCommand):
    help = 'Eski düz seed dosyalarını yeni enum ve düzene taşır.'

    def add_arguments(self, parser):
        parser.add_argument('--target', default='en',
                            help='Dosyaların hedef dili (varsayılan en).')
        parser.add_argument('--native', default='tr',
                            help='Çeviri sorularının ana dili (varsayılan tr).')
        parser.add_argument('--seeds-dir', default=None)
        parser.add_argument('--check', action='store_true',
                            help='Yazmadan raporla.')
        parser.add_argument('--prune', action='store_true',
                            help='Dönüştürülen eski düz dosyaları sil.')

    def handle(self, *args, **opts):
        seeds_dir = (Path(opts['seeds_dir']) if opts['seeds_dir']
                     else SEEDS_DIR)
        target, native = opts['target'], opts['native']
        for code in (target, native):
            try:
                languages.get(code)
            except languages.UnknownLanguage:
                raise CommandError(f'sicilde olmayan dil: {code}')
        if target == native:
            raise CommandError('hedef ve ana dil aynı olamaz')

        flat = sorted(seeds_dir.glob('*.json'))
        if not flat:
            self.stdout.write('Dönüştürülecek düz dosya yok.')
            return

        mono_dir = seeds_dir / target / 'mono'
        pair_dir = seeds_dir / target / native

        converted = unknown = 0
        wrote_mono = wrote_pair = 0
        for path in flat:
            items = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(items, list):
                self.stdout.write(self.style.WARNING(
                    f'{path.name}: kök öğe liste değil — atlandı.'
                ))
                continue

            mono, pair = [], []
            for item in items:
                if not isinstance(item, dict):
                    continue
                qtype = item.get('question_type')
                if qtype in TYPE_MAP:
                    item = dict(item, question_type=TYPE_MAP[qtype])
                    converted += 1
                    qtype = item['question_type']
                if qtype in MONO_TYPES:
                    mono.append(item)
                elif qtype in PAIR_TYPES:
                    pair.append(item)
                else:
                    unknown += 1
                    self.stdout.write(self.style.WARNING(
                        f'{path.name}: bilinmeyen tip {qtype!r} — atlandı.'
                    ))

            if opts['check']:
                self.stdout.write(
                    f'{path.stem}: {len(mono)} mono -> {mono_dir.name}/, '
                    f'{len(pair)} çeviri -> {pair_dir.name}/'
                )
                continue

            if mono:
                mono_dir.mkdir(parents=True, exist_ok=True)
                (mono_dir / path.name).write_text(
                    json.dumps(mono, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8',
                )
                wrote_mono += 1
            if pair:
                pair_dir.mkdir(parents=True, exist_ok=True)
                (pair_dir / path.name).write_text(
                    json.dumps(pair, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8',
                )
                wrote_pair += 1
            if opts['prune']:
                path.unlink()

        if opts['check']:
            self.stdout.write(
                f'{len(flat)} dosya, {converted} soru tipi dönüşecek, '
                f'{unknown} bilinmeyen tip.'
            )
            return

        self.stdout.write(self.style.SUCCESS(
            f'{len(flat)} dosya işlendi: {converted} soru tipi dönüştürüldü, '
            f'{wrote_mono} mono + {wrote_pair} çeviri dosyası yazıldı'
            f'{", eski dosyalar silindi" if opts["prune"] else ""}.\n'
            f'Şimdi: manage.py validate_quiz_seeds --target {target}'
        ))
