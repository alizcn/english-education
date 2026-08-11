import asyncio
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path('/root/apps/english-education')
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.test import override_settings

from services import claude_client


class ExtractJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(claude_client._extract_json('{"items": [1]}'), {'items': [1]})

    def test_fenced_json(self):
        text = 'İşte sonuç:\n```json\n{"items": [{"english": "cat"}]}\n```\nUmarım işine yarar.'
        self.assertEqual(claude_client._extract_json(text), {'items': [{'english': 'cat'}]})

    def test_json_embedded_in_prose(self):
        self.assertEqual(claude_client._extract_json('Sure! {"ok": true} done'), {'ok': True})

    def test_unparseable_raises_client_error(self):
        with self.assertRaises(claude_client.ClaudeClientError) as ctx:
            claude_client._extract_json('bugün JSON yok')
        self.assertTrue(ctx.exception.retryable)


class ModelParamsTests(unittest.TestCase):
    @override_settings(CLAUDE_MODEL='claude-opus-5', CLAUDE_REASONING_EFFORT='medium', CLAUDE_THINKING='adaptive')
    def test_defaults(self):
        self.assertEqual(
            claude_client._model_params(),
            {'model': 'claude-opus-5', 'thinking': {'type': 'adaptive'}, 'output_config': {'effort': 'medium'}},
        )

    @override_settings(CLAUDE_MODEL='claude-sonnet-4-5', CLAUDE_REASONING_EFFORT='', CLAUDE_THINKING='')
    def test_empty_settings_omit_params(self):
        self.assertEqual(claude_client._model_params(), {'model': 'claude-sonnet-4-5'})

    @override_settings(CLAUDE_MODEL='claude-opus-5', CLAUDE_REASONING_EFFORT='max', CLAUDE_THINKING='disabled')
    def test_effort_capped_when_thinking_disabled(self):
        self.assertEqual(claude_client._model_params()['output_config'], {'effort': 'high'})

    @override_settings(CLAUDE_MODEL='claude-opus-5', CLAUDE_REASONING_EFFORT='turbo', CLAUDE_THINKING='adaptive')
    def test_unknown_effort_falls_back(self):
        self.assertEqual(claude_client._model_params()['output_config'], {'effort': 'medium'})


class SystemPromptGuardTests(unittest.TestCase):
    @override_settings(CLAUDE_THINKING='disabled')
    def test_guard_added_when_thinking_disabled(self):
        # Opus 5 düşünme kapalıyken iç etiket sızdırabiliyor; koruma eklenmeli.
        self.assertIn('internal or system XML tags', claude_client._system_prompt('temel'))
        self.assertTrue(claude_client._system_prompt('temel').startswith('temel'))

    @override_settings(CLAUDE_THINKING='adaptive')
    def test_guard_omitted_when_thinking_on(self):
        self.assertEqual(claude_client._system_prompt('temel'), 'temel')


class RetryTests(unittest.TestCase):
    @override_settings(CLAUDE_MAX_RETRIES=3)
    def test_retries_until_success(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise claude_client.ClaudeClientError('geçici')
            return 'ok'

        with mock.patch.object(claude_client.time, 'sleep'):
            self.assertEqual(claude_client._with_retry(flaky), 'ok')
        self.assertEqual(len(calls), 3)

    @override_settings(CLAUDE_MAX_RETRIES=3)
    def test_non_retryable_fails_immediately(self):
        calls = []

        def refused():
            calls.append(1)
            raise claude_client.ClaudeClientError('reddedildi', retryable=False)

        with mock.patch.object(claude_client.time, 'sleep'):
            with self.assertRaises(claude_client.ClaudeClientError):
                claude_client._with_retry(refused)
        self.assertEqual(len(calls), 1)

    @override_settings(CLAUDE_MAX_RETRIES=2)
    def test_raises_after_last_attempt(self):
        def always_fails():
            raise claude_client.ClaudeClientError('olmadı')

        with mock.patch.object(claude_client.time, 'sleep'):
            with self.assertRaises(claude_client.ClaudeClientError):
                claude_client._with_retry(always_fails)


class TransportDispatchTests(unittest.TestCase):
    def _dispatch(self):
        with mock.patch.object(claude_client, '_generate_api', return_value='api') as api, \
             mock.patch.object(claude_client, '_generate_cli', return_value='cli') as cli:
            result = claude_client._generate('sys', [{'role': 'user', 'content': 'hi'}], 100)
        return result, api, cli

    @override_settings(CLAUDE_AUTH_MODE='cli')
    def test_cli_mode(self):
        result, api, cli = self._dispatch()
        self.assertEqual(result, 'cli')
        api.assert_not_called()
        cli.assert_called_once()

    @override_settings(CLAUDE_AUTH_MODE='api')
    def test_api_mode(self):
        result, api, cli = self._dispatch()
        self.assertEqual(result, 'api')
        cli.assert_not_called()

    @override_settings(CLAUDE_AUTH_MODE='sacma')
    def test_unknown_mode_falls_back_to_cli(self):
        result, _api, _cli = self._dispatch()
        self.assertEqual(result, 'cli')


class CliTransportTests(unittest.TestCase):
    def test_single_user_message_passed_through(self):
        self.assertEqual(
            claude_client._flatten_messages([{'role': 'user', 'content': 'merhaba'}]),
            'merhaba',
        )

    def test_history_becomes_transcript(self):
        prompt = claude_client._flatten_messages([
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'},
            {'role': 'user', 'content': 'how are you'},
        ])
        self.assertIn('User: hi', prompt)
        self.assertIn('Assistant: hello', prompt)
        self.assertTrue(prompt.startswith(claude_client._TRANSCRIPT_HEADER))

    @override_settings(CLAUDE_REASONING_EFFORT='xhigh')
    def test_xhigh_effort_downgraded_for_cli(self):
        # Claude Code CLI 'xhigh' seviyesini tanımıyor.
        self.assertEqual(claude_client._cli_effort(), 'high')

    @override_settings(CLAUDE_REASONING_EFFORT='')
    def test_empty_effort_omitted(self):
        self.assertIsNone(claude_client._cli_effort())

    @override_settings(CLAUDE_CLI_TIMEOUT=1)
    def test_timeout_is_not_retried(self):
        # Üretim dakikalar sürüyor; ikinci deneme worker'ı bir o kadar daha bloke eder.
        async def _hang(system, prompt):
            await asyncio.sleep(5)

        with mock.patch.object(claude_client, '_cli_query', _hang):
            with self.assertRaises(claude_client.ClaudeClientError) as ctx:
                claude_client._generate_cli('sys', [{'role': 'user', 'content': 'hi'}], 100)
        self.assertFalse(ctx.exception.retryable)

    @override_settings(CLAUDE_CLI_TIMEOUT=30)
    def test_text_returned_from_cli(self):
        async def _ok(system, prompt):
            return '{"items": []}'

        with mock.patch.object(claude_client, '_cli_query', _ok):
            out = claude_client._generate_cli('sys', [{'role': 'user', 'content': 'hi'}], 100)
        self.assertEqual(out, '{"items": []}')


class ParallelMapTests(unittest.TestCase):
    """Parçalı üretimin taşıyıcısı: bitenler beklemeden akmalı, hata turu düşürmemeli."""

    def test_results_carry_their_index(self):
        out = list(claude_client.parallel_map(lambda x: x * 2, [1, 2, 3]))
        self.assertEqual(
            sorted((i, r) for i, r, _e in out),
            [(0, 2), (1, 4), (2, 6)],
        )
        self.assertTrue(all(e is None for _i, _r, e in out))

    def test_runs_concurrently(self):
        # Seri koşsaydı 5 x 0.2s = 1s sürerdi; paralelde bir uykuluk sürmeli.
        def slow(_):
            time.sleep(0.2)
            return 'ok'

        start = time.monotonic()
        out = list(claude_client.parallel_map(slow, list(range(5))))
        elapsed = time.monotonic() - start
        self.assertEqual(len(out), 5)
        self.assertLess(elapsed, 0.6, f'paralel çalışmıyor: {elapsed:.2f}s')

    def test_one_failure_does_not_kill_the_batch(self):
        def flaky(x):
            if x == 2:
                raise claude_client.ClaudeClientError('bu parça patladı')
            return x

        out = list(claude_client.parallel_map(flaky, [1, 2, 3]))
        errors = [e for _i, _r, e in out if e is not None]
        ok = [r for _i, r, e in out if e is None]
        self.assertEqual(len(errors), 1)
        self.assertEqual(sorted(ok), [1, 3])

    def test_empty_input_yields_nothing(self):
        self.assertEqual(list(claude_client.parallel_map(lambda x: x, [])), [])


class ApiTransportTests(unittest.TestCase):
    """_generate_api'nin stop_reason ve hata eşlemesi — ağa çıkmadan."""

    def _fake_response(self, stop_reason='end_turn', text='{"items": []}'):
        block = mock.Mock(type='text', text=text)
        return mock.Mock(content=[block], stop_reason=stop_reason, usage=None, model='claude-opus-5')

    def _patch_client(self, resp=None, error=None):
        stream_cm = mock.MagicMock()
        if error is not None:
            stream_cm.__enter__.side_effect = error
        else:
            stream_cm.__enter__.return_value.get_final_message.return_value = resp
        fake = mock.Mock()
        fake.messages.stream.return_value = stream_cm
        return mock.patch.object(claude_client, 'client', return_value=fake)

    @override_settings(CLAUDE_MODEL='claude-opus-5', CLAUDE_REASONING_EFFORT='medium', CLAUDE_THINKING='adaptive')
    def test_refusal_is_not_retryable(self):
        with self._patch_client(self._fake_response(stop_reason='refusal')):
            with self.assertRaises(claude_client.ClaudeClientError) as ctx:
                claude_client._generate_api('sys', [{'role': 'user', 'content': 'hi'}], 100)
        self.assertFalse(ctx.exception.retryable)

    @override_settings(CLAUDE_MODEL='claude-opus-5', CLAUDE_REASONING_EFFORT='medium', CLAUDE_THINKING='adaptive')
    def test_text_blocks_are_joined(self):
        with self._patch_client(self._fake_response(text='{"items": [1]}')):
            text = claude_client._generate_api('sys', [{'role': 'user', 'content': 'hi'}], 100)
        self.assertEqual(text, '{"items": [1]}')

    @override_settings(CLAUDE_MODEL='claude-opus-5', CLAUDE_REASONING_EFFORT='medium', CLAUDE_THINKING='adaptive')
    def test_temperature_is_not_sent(self):
        # Opus 5 ve sonrası temperature parametresini reddediyor.
        fake_client = mock.Mock()
        stream_cm = mock.MagicMock()
        stream_cm.__enter__.return_value.get_final_message.return_value = self._fake_response()
        fake_client.messages.stream.return_value = stream_cm
        with mock.patch.object(claude_client, 'client', return_value=fake_client):
            claude_client._generate_api('sys', [{'role': 'user', 'content': 'hi'}], 100)
        kwargs = fake_client.messages.stream.call_args.kwargs
        self.assertNotIn('temperature', kwargs)
        self.assertEqual(kwargs['thinking'], {'type': 'adaptive'})
        self.assertEqual(kwargs['output_config'], {'effort': 'medium'})


if __name__ == '__main__':
    unittest.main()
