"""Gramer konularını, anlatımlarını ve örneklerini veri dosyalarından yükler.

Dosya düzeni::

    apps/topics/data/<hedef_dil>/topics.json
    apps/topics/data/<hedef_dil>/explanations/<ana_dil>/<slug>.md

İÇERİK NEDEN PYTHON'DAN DOSYAYA TAŞINDI: eski sürüm 968 satırlık bir `TOPICS`
literal'i ve 373 satırlık bir `EXPLANATIONS_EN` sözlüğü taşıyordu. Dört hedef
dile çıkınca bu ~4.000 satır Python olurdu ve içerik gözden geçirilemez hâle
gelirdi. Markdown dosyaları ayrıca `git diff`te okunabiliyor.

ANLATIMLAR MARKDOWN: `##` başlık, `-` madde. Eski metinler ALL-CAPS başlık
konvansiyonunu kullanıyordu ve ayrıştırıcı onları SEZGİSEL olarak tanımaya
çalışıyordu — dilden bağımsız olamayan ve ölçümde %25-30 oranında başarısız
olan bir sezgi (bkz. `apps/topics/markup.py`). Taşıma sırasında 79 başlık
otomatik dönüştürüldü.

ÖRNEKLER SİLİNİP YENİDEN YARATILMIYOR: eski sürüm her çalıştırmada
`topic.examples.all().delete()` yapıyordu; bu, her container açılışında 324
satırın birincil anahtarını değiştiriyor, SQLite dosyasını şişiriyor ve
örneklere yabancı anahtar vermeyi imkânsız kılıyordu. Artık
`(topic, kind, order)` anahtarıyla upsert + hedefli budama var.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.topics.models import Topic, TopicExample, TopicExplanation
from services import languages

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / 'data'


class Command(BaseCommand):
    help = ('Gramer konularını, anlatımlarını ve örneklerini yükler '
            '(idempotent — anahtarlı upsert).')

    def add_arguments(self, parser):
        parser.add_argument('--target', default=None,
                            help='Hedef dil kodu. Verilmezse sicildeki tüm '
                                 'öğrenilebilir diller.')
        parser.add_argument('--data-dir', default=None,
                            help=f'Veri kökü (varsayılan: {DEFAULT_DATA_DIR}).')
        parser.add_argument('--reset', action='store_true',
                            help='Önce bu dilin tüm konularını sil.')
        parser.add_argument('--prune', action='store_true',
                            help='Dosyada olmayan konuları da sil.')

    def handle(self, *args, **opts):
        data_dir = Path(opts['data_dir']) if opts['data_dir'] else DEFAULT_DATA_DIR
        if not data_dir.exists():
            raise CommandError(f'veri dizini yok: {data_dir}')

        targets = ([opts['target']] if opts['target']
                   else list(languages.LEARNABLE_CODES))
        for target in targets:
            try:
                languages.get(target)
            except languages.UnknownLanguage:
                raise CommandError(f'sicilde olmayan dil: {target}')
            self._load_language(target, data_dir, opts)

    def _load_language(self, target, data_dir, opts):
        lang_dir = data_dir / target
        topics_path = lang_dir / 'topics.json'
        if not topics_path.exists():
            self.stdout.write(self.style.WARNING(
                f'{target}: {topics_path} yok — atlandı.'
            ))
            return

        specs = json.loads(topics_path.read_text(encoding='utf-8'))
        if not isinstance(specs, list):
            raise CommandError(f'{topics_path}: kök bir liste olmalı')

        if opts['reset']:
            deleted = Topic.objects.filter(language=target).delete()[0]
            self.stdout.write(self.style.WARNING(
                f'{target}: {deleted} mevcut kayıt silindi.'
            ))

        created = explanations = examples = pruned_examples = 0
        file_slugs = set()

        with transaction.atomic():
            for order, spec in enumerate(specs):
                slug = spec['slug']
                file_slugs.add(slug)
                topic, was_created = Topic.objects.update_or_create(
                    language=target, slug=slug,
                    defaults={'name': spec['name'],
                              'order': spec.get('order', order)},
                )
                created += was_created
                explanations += self._sync_explanations(topic, lang_dir, slug)
                added, pruned = self._sync_examples(topic, spec.get('examples', []))
                examples += added
                pruned_examples += pruned

            pruned_topics = 0
            if opts['prune']:
                stale = Topic.objects.filter(language=target).exclude(
                    slug__in=file_slugs,
                )
                pruned_topics = stale.count()
                if pruned_topics:
                    self.stdout.write(self.style.WARNING(
                        f'{target}: {pruned_topics} konu dosyada yok, siliniyor.'
                    ))
                    stale.delete()

        self.stdout.write(self.style.SUCCESS(
            f'{target}: {created} yeni konu, {explanations} anlatım, '
            f'{examples} örnek, {pruned_examples} budanan örnek.'
        ))

    def _sync_explanations(self, topic, lang_dir, slug):
        """Her ana dil için `explanations/<kod>/<slug>.md` okur."""
        synced = 0
        root = lang_dir / 'explanations'
        if not root.exists():
            return 0
        for native_dir in sorted(root.iterdir()):
            if not native_dir.is_dir():
                continue
            path = native_dir / f'{slug}.md'
            if not path.exists():
                continue
            body = path.read_text(encoding='utf-8').strip()
            if not body:
                continue
            TopicExplanation.objects.update_or_create(
                topic=topic, language=native_dir.name, defaults={'body': body},
            )
            synced += 1
        return synced

    @staticmethod
    def _sync_examples(topic, specs):
        """`(kind, order)` anahtarıyla upsert + fazlalık budama."""
        keys = set()
        added = 0
        for spec in specs:
            kind, order = spec['kind'], spec['order']
            keys.add((kind, order))
            TopicExample.objects.update_or_create(
                topic=topic, kind=kind, order=order,
                defaults={
                    'sentence': spec['sentence'],
                    'translations': spec.get('translations') or {},
                },
            )
            added += 1

        pruned = 0
        for example in topic.examples.all():
            if (example.kind, example.order) not in keys:
                example.delete()
                pruned += 1
        return added, pruned
