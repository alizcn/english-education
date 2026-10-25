"""Konu başına seed quiz sorularını Claude ile üretir — DEVAM EDEBİLİR.

Çıktı: `GenerationBatch` satırları; `export_content --kind quiz` onları
repo dosyalarına döküyor:

* ``apps/quizzes/seeds/<hedef>/mono/<slug>.json``   — `fill_blank` + `multiple_choice`
* ``apps/quizzes/seeds/<hedef>/<ana>/<slug>.json``  — `translate_to_*`

**Mono/çift ayrımı üretimi %33 azaltıyor.** `fill_blank` ve `multiple_choice`
soruları tamamen hedef dilde; ana dilden bağımsız oldukları için hedef dil
başına bir kez üretiliyor. Yalnızca çeviri soruları ana dil başına değişiyor.

Kullanım (oturum limitine dayanıklı)::

    until manage.py generate_quiz_seeds --target de --workers 3; do
      [ $? -eq 75 ] && sleep 1800 || break
    done
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.content.models import GenerationBatch
from apps.content.runner import (
    EXIT_TEMPFAIL, BatchValidationError, run_batches,
)
from apps.topics.models import Topic
from services import claude_client as claude
from services import languages

from apps.quizzes.management.commands.validate_quiz_seeds import MIN_PER_TOPIC

from .generate_topic_content import read_topics

#: Konu başına istenen soru sayısı (mono + çeviri birleşerek kullanıcıya
#: gidiyor).
MONO_QUESTIONS = 20
PAIR_QUESTIONS = 20

#: Parça başına KABUL edilen en düşük sayı. İstenenin yüzdesi DEĞİL, gerçek
#: değişmezden türetiliyor: `validate_quiz_seeds` konu başına en az
#: `MIN_PER_TOPIC` soru istiyor ve mono kovası her ana dile ekleniyor, yani
#: çeviri kovasının taşıması gereken asgari miktar aradaki fark.
#:
#: Ölçüm: model daraltılmış bir konuda ("conditional-1") 20 YİNELENMEYEN
#: çeviri cümlesi üretmiyor, 10-14 veriyor. Eşik istenenin %60'ı (12) iken
#: parçalar kalite sorunu olmadan başarısız sayılıyordu. Eşiği aşağı çekmek
#: kapıyı gevşetmek değil, kapıyı doğru değişmeze bağlamak.
MIN_PAIR_QUESTIONS = max(MIN_PER_TOPIC - MONO_QUESTIONS, 1)
MIN_MONO_QUESTIONS = int(MONO_QUESTIONS * 0.6)

MONO_TYPES = {'fill_blank', 'multiple_choice'}
PAIR_TYPES = {'translate_to_native', 'translate_to_target'}

#: Parça başına farklı odak — verilmezse parçalar aynı soruyu üretiyor.
MONO_FOCUS = 'gap-fill and multiple-choice recognition of the form'
PAIR_FOCUS = 'translation in both directions'


class Command(BaseCommand):
    help = 'Konu başına seed quiz soruları üretir (devam edebilir).'

    def add_arguments(self, parser):
        parser.add_argument('--target', required=True, help='Hedef dil kodu.')
        parser.add_argument('--native', default=None,
                            help='Yalnızca bu ana dil için çeviri soruları. '
                                 'Verilmezse yayındaki tüm arayüz dilleri.')
        parser.add_argument('--slug', default=None, help='Yalnızca bu konu.')
        parser.add_argument('--kind', default='all',
                            choices=['all', 'mono', 'pair'],
                            help='Yalnızca mono ya da çeviri soruları.')
        parser.add_argument('--workers', type=int, default=None)
        parser.add_argument('--model', default=None)
        parser.add_argument('--effort', default=None)
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--max-runtime', type=int, default=None)
        parser.add_argument('--status', action='store_true')

    def handle(self, *args, **opts):
        target = opts['target']
        try:
            spec = languages.get(target)
        except languages.UnknownLanguage as e:
            raise CommandError(str(e))
        if not spec.is_learnable:
            raise CommandError(f'{target} öğrenilebilir dil değil.')

        self.topics = read_topics(target)
        if not self.topics:
            raise CommandError(f'{target}: topics.json yok ya da boş.')
        if opts['slug']:
            self.topics = [t for t in self.topics if t['slug'] == opts['slug']]
            if not self.topics:
                raise CommandError(f'{opts["slug"]}: topics.json içinde yok.')

        natives = ([opts['native']] if opts['native']
                   else [c for c in languages.ALL_CODES if c != target])
        for code in natives:
            try:
                languages.get(code)
            except languages.UnknownLanguage as e:
                raise CommandError(str(e))

        if opts['status']:
            return self._report(target)

        # Anlatım ve örnekler prompt'a bağlam olarak giriyor; konu
        # yüklenmemişse DB'den okunamaz, o yüzden önce oradan deniyoruz.
        self.context = self._load_context(target)

        self._plan(target, natives, opts)

        queryset = GenerationBatch.objects.filter(
            kind=GenerationBatch.QUIZ_SEED, target_language=target,
            topic_slug__in=[t['slug'] for t in self.topics],
        )
        if opts['kind'] == 'mono':
            queryset = queryset.filter(native_language='')
        elif opts['kind'] == 'pair':
            queryset = queryset.exclude(native_language='')
        if opts['native']:
            queryset = queryset.filter(native_language=opts['native'])

        overrides = {}
        if opts['model']:
            overrides['CLAUDE_MODEL'] = opts['model']
        if opts['effort']:
            overrides['CLAUDE_REASONING_EFFORT'] = opts['effort']

        with claude.options(**overrides):
            done, failed, left, stopped = run_batches(
                queryset, self._produce,
                validate=self._validate,
                workers=opts['workers'],
                max_runtime=opts['max_runtime'],
                stdout=self.stdout,
            )

        self.stdout.write(self.style.SUCCESS(
            f'{target} quiz seed: {done} parça bitti, {failed} başarısız, '
            f'{left} kaldı.'
        ))

        if stopped == 'session_limit':
            self.stdout.write(self.style.WARNING(
                'Oturum limiti. Parçalar kayıtlı; komutu sonra tekrar koşun. '
                f'(çıkış {EXIT_TEMPFAIL})'
            ))
            sys.exit(EXIT_TEMPFAIL)
        if left:
            sys.exit(EXIT_TEMPFAIL)

    # --------------------------------------------------------------- bağlam

    def _load_context(self, target):
        """Her konu için (anlatım, örnek cümleler) — prompt bağlamı.

        Üretilmiş parçalardan okunuyor; konu henüz DB'ye yüklenmemiş olabilir.
        """
        context = {}
        explanations = GenerationBatch.objects.filter(
            kind=GenerationBatch.TOPIC_EXPLANATION, target_language=target,
            status=GenerationBatch.DONE,
        )
        by_slug = {}
        for batch in explanations:
            # Hedef dilin kendi dilindeki anlatımı en iyi bağlam; yoksa
            # herhangi biri iş görüyor (soru üretimi hedef dilde).
            current = by_slug.get(batch.topic_slug)
            better = batch.native_language == target
            if current is None or better:
                by_slug[batch.topic_slug] = (batch.output or {}).get('body', '')

        examples = GenerationBatch.objects.filter(
            kind=GenerationBatch.TOPIC_EXAMPLES, target_language=target,
            status=GenerationBatch.DONE,
        )
        sentences = {
            b.topic_slug: [i.get('sentence', '')
                           for i in (b.output or {}).get('items') or []]
            for b in examples
        }

        # DB'de yüklü konular da bağlam verebilir (İngilizce hattı böyle).
        for topic in Topic.objects.filter(language=target):
            if topic.slug not in by_slug:
                body = topic.explanation_for(target)[0] if hasattr(
                    topic, 'explanation_for') else ''
                if body:
                    by_slug[topic.slug] = body
            if topic.slug not in sentences:
                sentences[topic.slug] = [
                    e.sentence for e in topic.examples.all()[:8]
                ]

        for topic in self.topics:
            context[topic['slug']] = (
                by_slug.get(topic['slug'], ''),
                sentences.get(topic['slug'], []),
            )
        return context

    # ------------------------------------------------------------------ plan

    def _plan(self, target, natives, opts):
        rows = []
        planned = 0
        for topic in self.topics:
            if opts['limit'] is not None and planned >= opts['limit']:
                break
            payload = {'slug': topic['slug'], 'name': topic['name']}
            if opts['kind'] in ('all', 'mono'):
                rows.append(GenerationBatch(
                    kind=GenerationBatch.QUIZ_SEED,
                    target_language=target, native_language='',
                    topic_slug=topic['slug'], chunk_index=0,
                    batch_size=MONO_QUESTIONS, input_payload=payload,
                ))
            if opts['kind'] in ('all', 'pair'):
                for native in natives:
                    rows.append(GenerationBatch(
                        kind=GenerationBatch.QUIZ_SEED,
                        target_language=target, native_language=native,
                        topic_slug=topic['slug'], chunk_index=0,
                        batch_size=PAIR_QUESTIONS, input_payload=payload,
                    ))
            planned += 1
        if rows:
            created = GenerationBatch.objects.bulk_create(
                rows, ignore_conflicts=True,
            )
            self.stdout.write(f'{len(created)} parça planlandı (mevcutlar atlandı).')

    # -------------------------------------------------------------- üretici

    def _produce(self, batch):
        payload = batch.input_payload
        explanation, sentences = self.context.get(payload['slug'], ('', []))
        mono = not batch.native_language

        if mono:
            # Mono taraf: ana dil soruya girmiyor ama prompt öğrenen profilini
            # kuruyor; varsayılan arayüz dilini ana dil sayıyoruz.
            native = next(c for c in languages.ALL_CODES
                          if c != batch.target_language)
            n, focus = MONO_QUESTIONS, MONO_FOCUS
        else:
            native = batch.native_language
            n, focus = PAIR_QUESTIONS, PAIR_FOCUS

        pair = languages.pair(batch.target_language, native)
        items = claude.generate_topic_quiz(
            payload['name'], explanation, sentences, n=n, focus=focus,
            pair=pair,
        )
        allowed = MONO_TYPES if mono else PAIR_TYPES
        items = [i for i in items
                 if isinstance(i, dict) and i.get('question_type') in allowed]
        return {'items': items}

    # ------------------------------------------------------------ doğrulama

    @staticmethod
    def _validate(batch, output):
        items = (output or {}).get('items') or []
        mono = not batch.native_language
        allowed = MONO_TYPES if mono else PAIR_TYPES
        floor = MIN_MONO_QUESTIONS if mono else MIN_PAIR_QUESTIONS

        # Model istenen tipin dışına çıkınca filtre onları atıyor; kalan sayı
        # çok düşükse soru üretimi başarısız sayılmalı, yarım dosya yazılmasın.
        if len(items) < floor:
            raise BatchValidationError(
                f'{len(items)} geçerli soru, en az {floor} '
                f'bekleniyor (istenen tipler: {sorted(allowed)})'
            )

        seen = set()
        for item in items:
            qtype = item.get('question_type')
            prompt = (item.get('prompt') or '').strip()
            answer = (item.get('correct_answer') or '').strip()
            choices = item.get('choices')
            if qtype not in allowed:
                raise BatchValidationError(f'beklenmeyen tip: {qtype!r}')
            if not prompt or not answer:
                raise BatchValidationError('promptsuz ya da cevapsız soru')
            key = prompt.lower()
            if key in seen:
                raise BatchValidationError(f'yinelenen soru: {prompt[:40]}')
            seen.add(key)

            if qtype == 'multiple_choice':
                if not isinstance(choices, list) or len(choices) != 4:
                    raise BatchValidationError(
                        f'{prompt[:30]!r}: çoktan seçmeli tam 4 şık olmalı'
                    )
                if any(not str(c).strip() for c in choices):
                    raise BatchValidationError(f'{prompt[:30]!r}: boş şık')
                if answer not in choices:
                    raise BatchValidationError(
                        f'{prompt[:30]!r}: doğru cevap şıklar arasında yok'
                    )
            elif choices is not None:
                raise BatchValidationError(
                    f'{prompt[:30]!r}: {qtype} için choices null olmalı'
                )

            if qtype == 'fill_blank' and '___' not in prompt:
                raise BatchValidationError(
                    f'{prompt[:30]!r}: fill_blank "___" içermeli'
                )

    # --------------------------------------------------------------- rapor

    def _report(self, target):
        rows = GenerationBatch.objects.filter(
            kind=GenerationBatch.QUIZ_SEED, target_language=target,
        )
        if not rows.exists():
            self.stdout.write('Hiç parça planlanmamış.')
            return
        mono = rows.filter(native_language='')
        pair = rows.exclude(native_language='')
        for label, sub in (('mono', mono), ('çeviri', pair)):
            total = sub.count()
            if not total:
                continue
            done = sub.filter(status=GenerationBatch.DONE).count()
            self.stdout.write(f'{target} quiz {label}: {done}/{total}')
        stuck = rows.filter(
            status=GenerationBatch.FAILED,
            attempts__gte=GenerationBatch.MAX_ATTEMPTS,
        )
        if stuck.exists():
            self.stdout.write(self.style.WARNING(
                f'{stuck.count()} parça deneme hakkını tüketti:'
            ))
            for batch in stuck[:5]:
                self.stdout.write(f'  {batch}: {batch.last_error[:100]}')
