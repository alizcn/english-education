import json
import urllib.parse
import urllib.request

from django.conf import settings


def verify_turnstile(token: str, ip: str = '') -> bool:
    """Cloudflare Turnstile token'ını doğrular.

    Key ayarlanmamışsa (geliştirme ortamı) her zaman True döner.
    Cloudflare'e erişilemezse de True döner — meşru kullanıcıyı engellemek
    bot trafiği kabul etmekten daha kötü.
    """
    if not getattr(settings, 'TURNSTILE_SECRET_KEY', ''):
        return True
    if not token:
        return False
    data = urllib.parse.urlencode({
        'secret': settings.TURNSTILE_SECRET_KEY,
        'response': token,
        'remoteip': ip,
    }).encode()
    try:
        req = urllib.request.Request(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data=data,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        return bool(result.get('success'))
    except Exception:
        return True
