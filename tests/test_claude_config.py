import unittest
import sys
from pathlib import Path

ROOT = Path('/root/apps/english-education')
sys.path.insert(0, str(ROOT))

import config.settings as settings


class ClaudeConfigTests(unittest.TestCase):
    def test_claude_settings_are_exposed(self):
        self.assertTrue(hasattr(settings, 'ANTHROPIC_API_KEY'))
        self.assertTrue(hasattr(settings, 'CLAUDE_MODEL'))
        self.assertTrue(hasattr(settings, 'CLAUDE_MAX_TOKENS'))


if __name__ == '__main__':
    unittest.main()
