"""Üretim defterini repo JSON dosyalarına döker.

İki adımlı akışın ikinci yarısı: `enrich_wordbank` yavaş ve kırılgan (dakikalar
süren Claude çağrıları, oturum limiti), bu komut hızlı ve DETERMİNİSTİK. Böylece
üretimi tekrar koşmadan dosyayı yeniden üretebiliyor ve çıktıyı `git diff` ile
gözden geçirebiliyoruz.

Determinizm şart: anahtar sırası sabit, kayıtlar `rank`e göre sıralı, dosya
`\\n` ile bitiyor. Aksi halde her dışa aktarma sahte bir diff üretir ve gerçek
değişikliği gizler.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.content import morphology
from apps.content import terms as terms_index
from apps.content.models import GenerationBatch
from apps.wordbank.models import BankWord
from services import languages

WORDBANK_DIR = Path(__file__).resolve().parents[3] / 'wordbank' / 'data'
TOPICS_DIR = Path(__file__).resolve().parents[3] / 'topics' / 'data'
SEEDS_DIR = Path(__file__).resolve().parents[3] / 'quizzes' / 'seeds'

#: Kayıt içindeki anahtar sırası — diff gürültüsünü önler.
FIELD_ORDER = ('rank', 'term', 'part_of_speech', 'example', 'extra', 'translations')


def _db_records(target, level):
    """Mevcut DB satırlarını dışa aktarma kayıt biçiminde döndürür.

    Üretim defteri dışa aktarmanın TEK kaynağı olamaz: bazı veri hiçbir
    `GenerationBatch` tarafından üretilmedi ama DB'de duruyor —

    * İngilizce'nin Türkçe karşılıkları eski `turkish`/`example_tr`
      sütunlarından migration ile geldi (6.217 satır), hiç Claude çağrısı
      görmedi.
    * DOĞRULAMA düzeltmelerinde payload'dan çıkarılan terimler (modelin
      karıştırdığı ya da reddettiği kelimeler) hâlâ DB'de.

    Bu satırlar yalnızca parça çıktısından yazıldığında dosyadan SESSİZCE
    düşüyordu; `load_wordbank` sonra onları DB'den de silerdi. O yüzden taban
    DB, üstüne taze parça çıktısı biniyor.
    """
    records = {}
    words = (
        BankWord.objects
        .filter(language=target, level=level)
        .prefetch_related('translations')
    )
    for word in words:
        translations = {}
        for row in word.translations.all():
            meaning = (row.meaning or '').strip()
            if not meaning:
                continue
            translations[row.language] = {
                'meaning': meaning,
                'example_translation': (row.example_translation or '').strip(),
            }
        records[word.rank] = {
            'rank': word.rank,
            'term': word.term,
            'part_of_speech': word.part_of_speech or '',
            'example': word.example or '',
            # DB satırı da normalizasyondan geçiyor: taban DB olduğu için
            # aksi halde eski çekimli `auxiliary` değerleri geri gelirdi.
            'extra': morphology.normalise_extra(target, word.extra),
            'translations': translations,
        }
    return records


def _merge_wordbank(target, level, *, db_fallback=True):
    """Mono ve ana dil parçalarını tek kayıt listesine birleştirir.

    Mono parçalar (`native_language=''`) hedef dildeki örnek cümleyi ve
    morfolojiyi taşıyor; ana dil parçaları anlamı ve cümlenin çevirisini.

    Anahtar `rank`tır (term değil): aynı terim farklı anlamlarla birden çok
    rank'ta gelebilir (EN'de çok anlamlı kelimeler). Her rank ayrı BankWord
    satırı, dolayısıyla her biri kendi çevirisini almalı.

    `db_fallback` ile mevcut DB satırları taban alınır (`_db_records`); parça
    çıktısı üzerine yazar, yani taze üretim her zaman kazanır.
    """
    by_rank = _db_records(target, level) if db_fallback else {}

    batches = GenerationBatch.objects.filter(
        kind=GenerationBatch.WORDBANK, target_language=target, level=level,
        status=GenerationBatch.DONE,
    ).order_by('native_language', 'chunk_index')

    for batch in batches:
        # Payload terimi → tüm rank'lar (çok anlamlı kelimeler için liste).
        # Anahtar PAYLOAD terimi; modelin döndürdüğü biçim `terms.resolve` ile
        # ona bağlanıyor — doğrulayıcı da aynı dizini kullanıyor, yoksa parça
        # `done` olur ama kayıt dosyaya hiç yazılmaz.
        payload = batch.input_payload.get('terms', [])
        index = terms_index.build_index(payload)
        term_to_ranks: dict = {}
        for entry in payload:
            term_to_ranks.setdefault(entry['term'].strip(), []).append(
                entry['rank']
            )

        for item in (batch.output or {}).get('items', []):
            term = terms_index.resolve(item.get('term'), index)
            if not term:
                continue
            ranks_for_term = term_to_ranks.get(term)
            if not ranks_for_term:
                continue

            # Aynı çeviriyi bu terimdeki tüm rank'lara uygula.
            for rank in ranks_for_term:
                record = by_rank.setdefault(rank, {
                    'rank': rank,
                    'term': term,
                    'part_of_speech': '',
                    'example': '',
                    'extra': {},
                    'translations': {},
                })

                if not batch.native_language:
                    record['part_of_speech'] = (
                        item.get('part_of_speech') or record['part_of_speech']
                    )
                    record['example'] = item.get('example') or record['example']
                    extra = morphology.normalise_extra(
                        target, item.get('extra'),
                    )
                    if extra:
                        record['extra'] = extra
                else:
                    meaning = (item.get('meaning') or '').strip()
                    if meaning:
                        record['translations'][batch.native_language] = {
                            'meaning': meaning,
                            'example_translation': (
                                item.get('example_translation') or ''
                            ).strip(),
                        }
                    if not record['example'] and item.get('example'):
                        record['example'] = item['example']
                    if not record['part_of_speech'] and item.get('part_of_speech'):
                        record['part_of_speech'] = item['part_of_speech']

    records = sorted(by_rank.values(), key=lambda r: r['rank'])
    # Anahtar sırasını sabitle.
    return [
        {field: record[field] for field in FIELD_ORDER if field in record}
        for record in records
    ]


class Command(BaseCommand):
    help = 'Üretim defterini repo JSON dosyalarına döker.'

    def add_arguments(self, parser):
        parser.add_argument('--kind', default='wordbank',
                            choices=['wordbank', 'topics', 'quiz'],
                            help='Dışa aktarılacak içerik türü.')
        parser.add_argument('--target', required=True, help='Hedef dil kodu.')
        parser.add_argument('--level', default=None, help='Yalnızca bu seviye.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Yazmadan ne olacağını göster.')
        parser.add_argument('--no-db-fallback', action='store_true',
                            help='Yalnızca üretim parçalarından yaz; DB\'de '
                                 'olup parçası olmayan satırları DIŞARIDA '
                                 'bırak (ham listeden çıkarılmış satırları '
                                 'temizlemek için).')

    def handle(self, *args, **opts):
        target = opts['target']
        try:
            spec = languages.get(target)
        except languages.UnknownLanguage:
            raise CommandError(f'sicilde olmayan dil: {target}')

        if opts['kind'] == 'topics':
            return self._export_topics(target, opts)
        if opts['kind'] == 'quiz':
            return self._export_quiz(target, opts)

        levels = [opts['level'].upper()] if opts['level'] else list(spec.cefr_levels)
        out_dir = WORDBANK_DIR / target
        total = 0

        for level in levels:
            records = _merge_wordbank(
                target, level, db_fallback=not opts['no_db_fallback'],
            )
            if not records:
                self.stdout.write(f'{target}/{level}: dışa aktarılacak parça yok.')
                continue

            # Hiçbir dilde karşılığı olmayan kayıt DOSYAYA YAZILMIYOR:
            # `load_wordbank` onu zaten atlıyor, yani dosyada durması
            # gözden geçirilebilir artefakta ölü satır eklemekten başka bir
            # şey yapmıyor ve `--check` kapısını kalıcı olarak "FARK"ta
            # tutuyordu. Terim ham kaynak listesinde duruyor, dolayısıyla
            # ileride `--repair` ile geri getirilebilir.
            missing = [r['term'] for r in records if not r['translations']]
            if missing:
                records = [r for r in records if r['translations']]
                self.stdout.write(self.style.WARNING(
                    f'{target}/{level}: {len(missing)} kayıt hiçbir dilde '
                    f'karşılık almadı (örnek: {missing[:3]}) — dosyaya '
                    'yazılmadı.'
                ))

            # DB'den az satır yazmak sessiz veri kaybı demek: `load_wordbank`
            # dosyayı doğruluk kaynağı sayıyor. 6 ay fark edilmeyen hata buydu.
            db_count = BankWord.objects.filter(
                language=target, level=level,
            ).count()
            if db_count > len(records):
                self.stdout.write(self.style.WARNING(
                    f'{target}/{level}: DB\'de {db_count} satır var, dosyaya '
                    f'{len(records)} yazılıyor — {db_count - len(records)} '
                    'satır düşüyor.'
                ))

            path = out_dir / f'{level.lower()}.json'
            body = json.dumps(records, ensure_ascii=False, indent=2) + '\n'

            if opts['dry_run']:
                self.stdout.write(
                    f'{target}/{level}: {len(records)} kayıt -> {path} (yazılmadı)'
                )
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
            self.stdout.write(f'{target}/{level}: {len(records)} kayıt -> {path}')
            total += len(records)

        if not opts['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Bitti. {total} kayıt yazıldı. '
                f'Şimdi: manage.py load_wordbank --target {target} --check'
            ))

    # --------------------------------------------------------------- konular

    def _export_topics(self, target, opts):
        """Anlatımları `.md`, örnekleri `topics.json` içine yazar.

        `topics.json` elle yazılan slug/ad/sıra alanlarını KORUYOR; yalnızca
        `examples` alanı üretimden geliyor.
        """
        topics_path = TOPICS_DIR / target / 'topics.json'
        if not topics_path.exists():
            raise CommandError(f'{topics_path} yok. Konu listesi elle yazılır.')
        topics = json.loads(topics_path.read_text(encoding='utf-8'))

        wrote_md = 0
        for batch in GenerationBatch.objects.filter(
            kind=GenerationBatch.TOPIC_EXPLANATION, target_language=target,
            status=GenerationBatch.DONE,
        ):
            body = ((batch.output or {}).get('body') or '').strip()
            if not body:
                continue
            path = (TOPICS_DIR / target / 'explanations'
                    / batch.native_language / f'{batch.topic_slug}.md')
            if opts['dry_run']:
                self.stdout.write(f'  {path} ({len(body)} karakter, yazılmadı)')
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body + '\n', encoding='utf-8')
            wrote_md += 1

        examples = {
            b.topic_slug: (b.output or {}).get('items') or []
            for b in GenerationBatch.objects.filter(
                kind=GenerationBatch.TOPIC_EXAMPLES, target_language=target,
                status=GenerationBatch.DONE,
            )
        }
        filled = 0
        for topic in topics:
            items = examples.get(topic.get('slug'))
            if not items:
                continue
            # `(kind, order)` TopicExample'ın benzersizlik anahtarı; sıra
            # türe göre yeniden numaralandırılıyor.
            rows, counters = [], {}
            for item in items:
                kind = item.get('kind')
                order = counters.get(kind, 0)
                counters[kind] = order + 1
                rows.append({
                    'kind': kind, 'order': order,
                    'sentence': item.get('sentence', ''),
                    'translations': item.get('translations') or {},
                })
            topic['examples'] = rows
            filled += 1

        if opts['dry_run']:
            self.stdout.write(
                f'{target}: {filled} konuya örnek, {len(examples)} örnek kümesi '
                '(yazılmadı)'
            )
            return

        topics_path.write_text(
            json.dumps(topics, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        self.stdout.write(self.style.SUCCESS(
            f'{target}: {wrote_md} anlatım dosyası, {filled} konuya örnek '
            f'-> {topics_path}\n'
            f'Şimdi: manage.py seed_topics --target {target}'
        ))

    # ------------------------------------------------------------------ quiz

    def _export_quiz(self, target, opts):
        """Soruları `seeds/<hedef>/mono|<ana>/<slug>.json` dosyalarına yazar."""
        batches = GenerationBatch.objects.filter(
            kind=GenerationBatch.QUIZ_SEED, target_language=target,
            status=GenerationBatch.DONE,
        )
        if not batches.exists():
            self.stdout.write(f'{target}: dışa aktarılacak quiz parçası yok.')
            return

        written = 0
        total_items = 0
        for batch in batches:
            items = (batch.output or {}).get('items') or []
            if not items:
                continue
            bucket = batch.native_language or 'mono'
            path = SEEDS_DIR / target / bucket / f'{batch.topic_slug}.json'
            body = json.dumps(items, ensure_ascii=False, indent=2) + '\n'
            if opts['dry_run']:
                self.stdout.write(
                    f'  {path} ({len(items)} soru, yazılmadı)'
                )
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
            written += 1
            total_items += len(items)

        if opts['dry_run']:
            return
        self.stdout.write(self.style.SUCCESS(
            f'{target}: {written} dosya, {total_items} soru yazıldı.\n'
            f'Şimdi: manage.py validate_quiz_seeds --target {target}'
        ))
