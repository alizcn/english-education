import unittest

from config import settings as app_settings


class AllowedHostsTests(unittest.TestCase):
    def test_site_url_host_is_allowed(self):
        self.assertIn('levelenai.com', app_settings.get_allowed_hosts())
