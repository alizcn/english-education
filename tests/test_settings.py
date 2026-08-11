import os
import sys
from pathlib import Path
import unittest

ROOT = Path('/root/apps/english-education')
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from config import settings as app_settings


class AllowedHostsTests(unittest.TestCase):
    def test_site_url_host_is_allowed(self):
        self.assertIn('levelenai.com', app_settings.get_allowed_hosts())
