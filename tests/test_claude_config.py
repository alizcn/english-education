import unittest
import sys
from pathlib import Path

ROOT = Path('/root/apps/english-education')
sys.path.insert(0, str(ROOT))

import config.settings as settings


class ClaudeConfigTests(unittest.TestCase):
    def test_claude_settings_are_exposed(self):
        for name in (
            'ANTHROPIC_API_KEY',
            'CLAUDE_MODEL',
            'CLAUDE_MAX_TOKENS',
            'CLAUDE_CHAT_MAX_TOKENS',
            'CLAUDE_REASONING_EFFORT',
            'CLAUDE_THINKING',
            'CLAUDE_MAX_RETRIES',
        ):
            self.assertTrue(hasattr(settings, name), name)

    def test_token_budgets_leave_room_for_thinking(self):
        # Düşünme blokları da max_tokens'tan harcanıyor; küçük bir tavan
        # uzun JSON yanıtlarını yarıda kestirir.
        self.assertGreaterEqual(settings.CLAUDE_MAX_TOKENS, 8000)
        self.assertGreaterEqual(settings.CLAUDE_CHAT_MAX_TOKENS, 1000)


if __name__ == '__main__':
    unittest.main()
