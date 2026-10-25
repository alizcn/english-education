"""İçerik üretim hattı: parça defteri, devam edebilirlik ve kalite kapısı.

Üretimin kendisi Claude çağırıyor; burada o çağrı mock'lanıyor. Test edilen
şey üretim KALİTESİ değil, hattın DAYANIKLILIĞI: oturum limiti nasıl
karşılanıyor, `--resume` doğru parçayı atlıyor mu, bozuk çıktı kaydediliyor mu.
"""

import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.content import morphology
from apps.content import terms as terms_index
from apps.content.management.commands.check_content import looks_like_definition
from apps.wordbank.models import BankWord, BankWordTranslation
from services import claude_client as claude

from .models import GenerationBatch
from .runner import BatchValidationError, plan_chunks, run_batches


def make_batch(chunk_index=0, terms=None, native='tr', **kw):
    return GenerationBatch.objects.create(
        kind=GenerationBatch.WORDBANK,
        target_language=kw.pop('target', 'en'),
        native_language=native,
        level=kw.pop('level', 'A1'),
        chunk_index=chunk_index,
        batch_size=kw.pop('batch_size', 2),
        input_payload={'terms': terms or [{'rank': 1, 'term': 'book'}]},
        **kw,
    )


class GenerationBatchTests(TestCase):
    def test_batch_key_is_unique(self):
        make_batch(chunk_index=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_batch(chunk_index=0)

    def test_mono_and_paired_batches_coexist(self):
        """Mono parça (hedef taraf) ile ana dil parçası ayrı satırlar."""
        make_batch(chunk_index=0, native='')
        make_batch(chunk_index=0, native='tr')
        self.assertEqual(GenerationBatch.objects.count(), 2)

    def test_exhausted_after_max_attempts(self):
        batch = make_batch(attempts=GenerationBatch.MAX_ATTEMPTS)
        self.assertTrue(batch.is_exhausted)

    def test_str_lists_the_scope(self):
        batch = make_batch(chunk_index=3)
        self.assertIn('en', str(batch))
        self.assertIn('A1', str(batch))
        self.assertIn('#3', str(batch))


class PlanChunksTests(TestCase):
    def test_chunks_are_contiguous_and_indexed(self):
        items = list(range(7))
        chunks = list(plan_chunks(items, 3))
        self.assertEqual([i for i, _c in chunks], [0, 1, 2])
        self.assertEqual([c for _i, c in chunks], [[0, 1, 2], [3, 4, 5], [6]])

    def test_empty_input_plans_nothing(self):
        self.assertEqual(list(plan_chunks([], 5)), [])


class RunBatchesTests(TestCase):
    def setUp(self):
        self.batches = [make_batch(chunk_index=i) for i in range(3)]
        self.queryset = GenerationBatch.objects.all()

    def test_all_batches_complete(self):
        done, failed, left, stopped = run_batches(
            self.queryset, lambda b: {'items': [{'term': 'x'}]}, workers=1,
        )
        self.assertEqual((done, failed, left, stopped), (3, 0, 0, None))
        self.assertEqual(
            GenerationBatch.objects.filter(status=GenerationBatch.DONE).count(), 3,
        )

    def test_output_is_persisted(self):
        run_batches(self.queryset, lambda b: {'items': [{'term': 'book'}]}, workers=1)
        batch = GenerationBatch.objects.first()
        self.assertEqual(batch.output['items'][0]['term'], 'book')
        self.assertIsNotNone(batch.finished_at)

    def test_session_limit_leaves_the_batch_pending(self):
        """Oturum limiti bir KALİTE hatası değil, KOTA olayı.

        Parça `failed` işaretlenmemeli ve deneme hakkı harcanmamalı — aksi
        halde üç kez limite takılan bir parça haksız yere "tükendi" sayılırdı.
        """
        error = claude.ClaudeClientError(
            'oturum doldu', retryable=False, reason='session_limit',
        )

        def produce(batch):
            raise error

        done, failed, left, stopped = run_batches(
            self.queryset, produce, workers=1,
        )
        self.assertEqual(stopped, 'session_limit')
        self.assertEqual(done, 0)
        self.assertEqual(failed, 0)
        batch = GenerationBatch.objects.get(pk=self.batches[0].pk)
        self.assertEqual(batch.status, GenerationBatch.PENDING)
        self.assertEqual(batch.attempts, 0, 'oturum limiti deneme harcamamalı')
        self.assertEqual(left, 3)

    def test_quality_failure_spends_an_attempt(self):
        def produce(batch):
            raise claude.ClaudeClientError('bozuk yanıt', reason='')

        done, failed, left, _stopped = run_batches(
            self.queryset, produce, workers=1,
        )
        self.assertEqual((done, failed), (0, 3))
        for batch in GenerationBatch.objects.all():
            self.assertEqual(batch.status, GenerationBatch.FAILED)
            self.assertEqual(batch.attempts, 1)

    def test_validation_failure_is_recorded(self):
        def validate(batch, output):
            raise BatchValidationError('terim eksik')

        done, failed, _left, _stopped = run_batches(
            self.queryset, lambda b: {'items': []}, validate=validate, workers=1,
        )
        self.assertEqual((done, failed), (0, 3))
        self.assertIn('terim eksik', GenerationBatch.objects.first().last_error)

    def test_one_failing_batch_does_not_stop_the_rest(self):
        def produce(batch):
            if batch.chunk_index == 1:
                raise claude.ClaudeClientError('tek parça patladı')
            return {'items': [{'term': 'x'}]}

        done, failed, _left, _stopped = run_batches(
            self.queryset, produce, workers=1,
        )
        self.assertEqual((done, failed), (2, 1))

    def test_exhausted_batches_are_not_retried(self):
        GenerationBatch.objects.update(
            status=GenerationBatch.FAILED,
            attempts=GenerationBatch.MAX_ATTEMPTS,
        )
        done, failed, left, _stopped = run_batches(
            self.queryset, lambda b: {'items': [{'term': 'x'}]}, workers=1,
        )
        self.assertEqual((done, failed, left), (0, 0, 0))

    def test_resume_only_runs_unfinished_batches(self):
        GenerationBatch.objects.filter(chunk_index=0).update(
            status=GenerationBatch.DONE,
        )
        seen = []

        def produce(batch):
            seen.append(batch.chunk_index)
            return {'items': [{'term': 'x'}]}

        done, _failed, _left, _stopped = run_batches(
            self.queryset, produce, workers=1,
        )
        self.assertEqual(done, 2)
        self.assertNotIn(0, seen)

    def test_running_batches_are_reset_when_interrupted(self):
        """Yarıda kesilen koşu parçaları RUNNING'de bırakmamalı."""
        error = claude.ClaudeClientError('dur', reason='session_limit')
        run_batches(self.queryset, lambda b: (_ for _ in ()).throw(error), workers=1)
        self.assertEqual(
            GenerationBatch.objects.filter(status=GenerationBatch.RUNNING).count(), 0,
        )


class EnrichWordbankCommandTests(TestCase):
    """Komutun planlama ve devam etme davranışı."""

    def _data_dir(self, terms, target='en', level='a1'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        lang_dir = Path(tmp.name) / target
        lang_dir.mkdir(parents=True)
        (lang_dir / f'{level}.raw.json').write_text(
            json.dumps([{'rank': i + 1, 'term': t} for i, t in enumerate(terms)]),
            encoding='utf-8',
        )
        return Path(tmp.name)

    def _run(self, data_dir, **opts):
        opts.setdefault('target', 'en')
        opts.setdefault('native', 'tr')
        opts.setdefault('level', 'A1')
        opts.setdefault('batch', 2)
        opts.setdefault('workers', 1)
        # Mock yerine komutun kendi `--data-dir` seçeneği: test gerçek kod
        # yolunu kullanıyor.
        return call_command(
            'enrich_wordbank', verbosity=0,
            stdout=io.StringIO(), stderr=io.StringIO(),
            data_dir=str(data_dir), **opts,
        )

    def _fake_entries(self, terms, **_kw):
        return [
            {'term': t, 'meaning': f'{t}-anlam', 'example': f'A {t}.',
             'example_translation': f'Bir {t}.', 'part_of_speech': 'noun',
             'extra': {}}
            for t in terms
        ]

    def test_batches_are_planned_from_the_source_list(self):
        data_dir = self._data_dir(['book', 'pen', 'cat'])
        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=self._fake_entries):
            try:
                self._run(data_dir)
            except SystemExit:
                pass
        self.assertEqual(GenerationBatch.objects.count(), 2)   # 3 terim / batch 2

    def test_results_are_stored_per_batch(self):
        data_dir = self._data_dir(['book', 'pen'])
        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=self._fake_entries):
            try:
                self._run(data_dir)
            except SystemExit:
                pass
        batch = GenerationBatch.objects.get()
        self.assertEqual(batch.status, GenerationBatch.DONE)
        self.assertEqual(len(batch.output['items']), 2)

    def test_changing_batch_size_is_rejected(self):
        """`--batch` değişimi tüm parça anahtarlarını kaydırır ve tamamlanmış
        işi kullanılamaz hâle getirir."""
        data_dir = self._data_dir(['book', 'pen', 'cat', 'dog'])
        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=self._fake_entries):
            try:
                self._run(data_dir, batch=2)
            except SystemExit:
                pass
            with self.assertRaises(CommandError):
                self._run(data_dir, batch=3)

    def test_replan_allows_a_new_batch_size(self):
        data_dir = self._data_dir(['book', 'pen', 'cat', 'dog'])
        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=self._fake_entries):
            try:
                self._run(data_dir, batch=2)
            except SystemExit:
                pass
            GenerationBatch.objects.update(status=GenerationBatch.PENDING)
            try:
                self._run(data_dir, batch=4, replan=True)
            except SystemExit:
                pass
        self.assertTrue(
            GenerationBatch.objects.filter(batch_size=4).exists(),
        )

    def test_model_drift_is_caught_by_validation(self):
        """Model terimi yeniden yazarsa yanlış kelimeye anlam yazılır."""
        data_dir = self._data_dir(['book', 'pen'])

        def drifted(terms, **_kw):
            return [{'term': 'BOOKS', 'meaning': 'kitaplar'}]

        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=drifted):
            try:
                self._run(data_dir)
            except SystemExit:
                pass
        batch = GenerationBatch.objects.get()
        self.assertEqual(batch.status, GenerationBatch.FAILED)
        self.assertIn('istenmeyen terim', batch.last_error)

    def test_oversized_field_is_caught(self):
        data_dir = self._data_dir(['book'])

        def oversized(terms, **_kw):
            return [{'term': 'book', 'meaning': 'x' * 500}]

        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=oversized):
            try:
                self._run(data_dir, batch=1)
            except SystemExit:
                pass
        self.assertIn('sınır 400', GenerationBatch.objects.get().last_error)

    def test_missing_term_is_caught(self):
        data_dir = self._data_dir(['book', 'pen'])

        def partial(terms, **_kw):
            return [{'term': 'book', 'meaning': 'kitap'}]

        with mock.patch.object(claude, 'generate_lexicon_entries',
                               side_effect=partial):
            try:
                self._run(data_dir)
            except SystemExit:
                pass
        self.assertIn('eksik', GenerationBatch.objects.get().last_error)


class MorphologyNormalisationTests(TestCase):
    """Almanca `extra.auxiliary` mastar hâlinde tutulmak zorunda.

    Ölçüm: 1.850 fiilin 1.023'ünde model çekimli biçim yazmıştı (`hat` 892,
    `ist` 105). Alan "bu fiil Perfekt'i hangi yardımcı fiille kurar" sorusunu
    yanıtlıyor; `hat` yazmak öğrenciye yanlış bilgi vermek.
    """

    def test_conjugated_auxiliaries_become_infinitives(self):
        for raw, want in (('hat', 'haben'), ('habe', 'haben'),
                          ('ist', 'sein'), ('sind', 'sein'),
                          ('haben', 'haben'), ('sein', 'sein')):
            with self.subTest(raw=raw):
                out = morphology.normalise_extra('de', {'auxiliary': raw})
                self.assertEqual(out['auxiliary'], want)

    def test_both_auxiliaries_are_kept_as_a_pair(self):
        """Hareket fiilleri anlamına göre iki yardımcı fiil alabiliyor."""
        for raw in ('hat/ist', 'ist/hat', 'sein/haben'):
            with self.subTest(raw=raw):
                out = morphology.normalise_extra('de', {'auxiliary': raw})
                self.assertEqual(out['auxiliary'], 'haben/sein')

    def test_unrecognised_auxiliary_is_dropped_not_guessed(self):
        """`werden` Perfekt yardımcısı değil; yanlış morfoloji eksikten kötü."""
        for raw in ('werden', 'wird', 'sich erweisen', 'hat/kann'):
            with self.subTest(raw=raw):
                out = morphology.normalise_extra(
                    'de', {'auxiliary': raw, 'past_participle': 'x'},
                )
                self.assertNotIn('auxiliary', out)
                # Diğer alanlar korunuyor.
                self.assertEqual(out['past_participle'], 'x')

    def test_other_languages_pass_through_untouched(self):
        extra = {'gender': 'le', 'plural': 'les'}
        self.assertEqual(morphology.normalise_extra('fr', extra), extra)
        self.assertEqual(morphology.normalise_extra('de', {}), {})
        self.assertEqual(morphology.normalise_extra('de', None), {})


class DefinitionHeuristicTests(TestCase):
    """`check_content`in "karşılık değil tanım" sezgiseli.

    Yakalanması gereken gerçek hata eski C2 verisiydi: İngilizce tanımın
    makine çevirisi karşılık olarak yazılmıştı. YakalanMAMASI gereken şey
    İngilizce fiil karşılığı — `to drive in` mastarla yazılır ve doğrudur.
    Eski kural `^to\\s` ile Fransızca B2'de 1033 sağlam kaydı işaretliyordu.
    """

    def test_translated_definitions_are_flagged(self):
        for meaning in (
            'Devam ediyor; uzun süre devam ediyor.',
            'Güçlü ve sağlıklı; fiziksel olarak uygun.',
            'the act of running away',
            'a person who teaches',
        ):
            with self.subTest(meaning=meaning):
                self.assertTrue(looks_like_definition(meaning))

    def test_real_glosses_are_not_flagged(self):
        for meaning in (
            'to drive in; to push down; to break down (a door)',
            'kalıcı, değişmez',
            'içeri doğru itmek, çakmak, kırmak',
            'dauernd, bleibend, andauernd',
            'bir bölgeyi yönetmekle görevli kamu görevlisi',
            'kitap',
            '',
        ):
            with self.subTest(meaning=meaning):
                self.assertFalse(looks_like_definition(meaning))

    def test_short_capitalised_gloss_is_not_a_sentence(self):
        """Cümle kuralı en az üç kelime istiyor: `Ev.` bir tanım değil."""
        self.assertFalse(looks_like_definition('Ev.'))


class TermIndexTests(TestCase):
    """Model çıktısının payload terimine bağlanması (`apps/content/terms.py`).

    Ölçülmüş kayıp: Fransızca'da model `épisode` yerine `episode` döndürüyordu,
    birebir karşılaştırma bütün parçayı reddediyordu ve parçayı kurtarmak için
    terim payload'dan çıkarılınca `é`/`ô`/`î` ile başlayan 77 gerçek kelime
    kalıcı olarak kayboldu.
    """

    def test_accent_drift_still_matches(self):
        index = terms_index.build_index([{'term': 'épisode', 'rank': 1}])
        self.assertEqual(terms_index.resolve('episode', index), 'épisode')
        self.assertEqual(terms_index.resolve('ÉPISODE', index), 'épisode')

    def test_payload_spelling_is_canonical(self):
        """Dönen kanonik biçim modelin yazdığı değil payload terimi."""
        index = terms_index.build_index([{'term': 'Épisode', 'rank': 1}])
        self.assertEqual(terms_index.resolve('episode', index), 'Épisode')

    def test_ambiguous_folding_is_rejected(self):
        """`yok` ve `yök` ayrı kelimeler — katlama ikisini birleştirmemeli.

        Türkçe'de ölçülen sapma buydu; toleransı körlemesine uygulamak
        yanlış kelimeye anlam yazmak olurdu. İki terim aynı katlanmış biçme
        düşerse yalnızca BİREBİR eşleşme kabul ediliyor.
        """
        index = terms_index.build_index([
            {'term': 'yok', 'rank': 1}, {'term': 'yök', 'rank': 2},
        ])
        self.assertEqual(terms_index.resolve('yok', index), 'yok')
        self.assertEqual(terms_index.resolve('yök', index), 'yök')
        # Büyük harf ve boşluk sapması hâlâ birebir eşleşiyor.
        self.assertEqual(terms_index.resolve(' YoK ', index), 'yok')

    def test_unknown_term_is_rejected(self):
        index = terms_index.build_index([{'term': 'book', 'rank': 1}])
        self.assertIsNone(terms_index.resolve('pen', index))
        self.assertIsNone(terms_index.resolve('', index))

    def test_sharp_s_is_not_folded_to_ss(self):
        """`Straße`/`strasse` ayrımı korunuyor: tahmin etmek yerine reddet."""
        index = terms_index.build_index([{'term': 'Straße', 'rank': 1}])
        self.assertEqual(terms_index.resolve('Straße', index), 'Straße')
        self.assertIsNone(terms_index.resolve('strasse', index))


class ExportContentTests(TestCase):
    """Defterden repo dosyasına dökme — mono ve ana dil parçaları birleşiyor."""

    def _export(self, out_dir, **opts):
        opts.setdefault('target', 'en')
        with mock.patch(
            'apps.content.management.commands.export_content.WORDBANK_DIR', out_dir,
        ):
            call_command('export_content', verbosity=0,
                         stdout=io.StringIO(), stderr=io.StringIO(), **opts)

    def test_mono_and_native_batches_merge_into_one_record(self):
        terms = [{'rank': 1, 'term': 'book'}]
        make_batch(chunk_index=0, native='', terms=terms,
                   status=GenerationBatch.DONE,
                   output={'items': [{'term': 'book', 'example': 'A book.',
                                      'part_of_speech': 'noun',
                                      'extra': {'gender': 'das'}}]})
        make_batch(chunk_index=0, native='tr', terms=terms,
                   status=GenerationBatch.DONE,
                   output={'items': [{'term': 'book', 'meaning': 'kitap',
                                      'example_translation': 'Bir kitap.'}]})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1')

        records = json.loads((out / 'en' / 'a1.json').read_text(encoding='utf-8'))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['term'], 'book')
        self.assertEqual(record['example'], 'A book.')
        self.assertEqual(record['extra'], {'gender': 'das'})
        self.assertEqual(record['translations']['tr']['meaning'], 'kitap')

    def test_multiple_native_languages_land_side_by_side(self):
        terms = [{'rank': 1, 'term': 'book'}]
        for native, meaning in (('tr', 'kitap'), ('fr', 'livre')):
            make_batch(chunk_index=0, native=native, terms=terms,
                       status=GenerationBatch.DONE,
                       output={'items': [{'term': 'book', 'meaning': meaning}]})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1')
        record = json.loads((out / 'en' / 'a1.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(set(record['translations']), {'tr', 'fr'})

    def test_export_is_deterministic(self):
        """Aynı defterden iki dışa aktarma birebir aynı dosyayı üretmeli;
        aksi halde her koşu sahte bir diff yaratır."""
        make_batch(chunk_index=0, native='tr',
                   terms=[{'rank': 2, 'term': 'pen'}, {'rank': 1, 'term': 'book'}],
                   status=GenerationBatch.DONE,
                   output={'items': [{'term': 'pen', 'meaning': 'kalem'},
                                     {'term': 'book', 'meaning': 'kitap'}]})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1')
        first = (out / 'en' / 'a1.json').read_text(encoding='utf-8')
        self._export(out, level='A1')
        second = (out / 'en' / 'a1.json').read_text(encoding='utf-8')
        self.assertEqual(first, second)
        # rank sırası korunuyor
        records = json.loads(first)
        self.assertEqual([r['rank'] for r in records], [1, 2])

    def test_unfinished_batches_are_not_exported(self):
        make_batch(chunk_index=0, native='tr', status=GenerationBatch.PENDING,
                   output={'items': [{'term': 'book', 'meaning': 'kitap'}]})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1')
        self.assertFalse((out / 'en' / 'a1.json').exists())

    # --------------------------------------------- DB tabanı (veri kaybı kapısı)

    def test_rows_without_a_batch_survive_the_export(self):
        """Parçası olmayan DB satırı dosyadan DÜŞMEMELİ.

        Ölçülmüş hata: İngilizce'nin Türkçe karşılıkları eski sütunlardan
        migration ile geldi, hiç `GenerationBatch` görmedi. Dışa aktarma
        yalnızca parça çıktısından yazdığı için dosyada 6.217 satır oluyordu
        (DB'de 6.218) VE 6.217 kaydın tamamı Türkçe karşılığını kaybediyordu;
        `load_wordbank` sonra onları DB'den de silerdi.
        """
        word = BankWord.objects.create(language='en', level='A1', rank=1,
                                       term='password', example='Change it.')
        BankWordTranslation.objects.create(word=word, language='tr',
                                           meaning='şifre',
                                           example_translation='Değiştir.')
        # Bu seviyede BAŞKA bir terim için parça var; `password`un yok.
        make_batch(chunk_index=0, native='tr', terms=[{'rank': 2, 'term': 'book'}],
                   status=GenerationBatch.DONE,
                   output={'items': [{'term': 'book', 'meaning': 'kitap'}]})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1')

        records = json.loads((out / 'en' / 'a1.json').read_text(encoding='utf-8'))
        by_rank = {r['rank']: r for r in records}
        self.assertEqual(set(by_rank), {1, 2})
        self.assertEqual(by_rank[1]['term'], 'password')
        self.assertEqual(by_rank[1]['translations']['tr']['meaning'], 'şifre')

    def test_fresh_batch_output_overrides_the_db_row(self):
        """Taze üretim kazanıyor — yoksa yeniden üretim hiçbir şey değiştirmez."""
        word = BankWord.objects.create(language='en', level='A1', rank=1,
                                       term='abiding')
        BankWordTranslation.objects.create(
            word=word, language='tr',
            meaning='Devam ediyor; uzun süre devam ediyor.',
        )
        make_batch(chunk_index=0, native='tr', terms=[{'rank': 1, 'term': 'abiding'}],
                   status=GenerationBatch.DONE,
                   output={'items': [{'term': 'abiding',
                                      'meaning': 'kalıcı, sürekli'}]})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1')

        record = json.loads((out / 'en' / 'a1.json').read_text(encoding='utf-8'))[0]
        self.assertEqual(record['translations']['tr']['meaning'],
                         'kalıcı, sürekli')

    def test_no_db_fallback_writes_only_batch_output(self):
        """Ham listeden çıkarılmış satırları temizlemenin yolu."""
        BankWord.objects.create(language='en', level='A1', rank=1, term='stale')
        make_batch(chunk_index=0, native='tr', terms=[{'rank': 2, 'term': 'book'}],
                   status=GenerationBatch.DONE,
                   output={'items': [{'term': 'book', 'meaning': 'kitap'}]})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        self._export(out, level='A1', no_db_fallback=True)

        records = json.loads((out / 'en' / 'a1.json').read_text(encoding='utf-8'))
        self.assertEqual([r['rank'] for r in records], [2])
