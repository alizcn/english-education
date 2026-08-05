"""Landing sayfasındaki ürün görselini uygulamanın kendisinden üretir.

Neden bir komut: hero görseli gerçek arayüzün fotoğrafı. Arayüz değişip görsel
değişmezse pazarlama sayfası ürünü yanlış tanıtmaya başlar — sessizce eskiyen
bir varlık. Bu komut, görseli her seferinde aynı şekilde yeniden üretilebilir
kılar; tasarım değiştikten sonra tek satırla tazelenir.

Kullanım (uygulama ayakta olmalı):

    python manage.py make_hero_shot --base-url http://127.0.0.1:8000

Gösterim hesabı geçicidir: komut hesabı oluşturur, mütevazı ve tekrarlanabilir
bir ilerleme yazar, ekranı çeker ve hesabı **her koşulda** siler. Görselde
uydurulmuş bir kullanıcı sayısı ya da referans yoktur; yalnızca ürünün
kullanımdaki hâli görünür.

Gereksinim: playwright + pillow (yalnızca geliştirme ortamında).
"""
from datetime import timedelta
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

DEMO_USERNAME = '__hero_shot_demo__'
DEMO_PASSWORD = 'HeroShotOnly!2345'

# Son 7 günün çalışma ritmi. Sabit: görsel her üretimde aynı grafiği versin.
DAILY_MASTERED = [9, 14, 0, 18, 11, 22, 16]
PERSONAL_WORDS = [
    ('deployment', 'dağıtım, yayına alma', 'noun'),
    ('scalable', 'ölçeklenebilir', 'adjective'),
    ('bottleneck', 'darboğaz', 'noun'),
    ('trade-off', 'ödünleşim', 'noun'),
    ('rollback', 'geri alma', 'noun'),
    ('throughput', 'iş hacmi', 'noun'),
    ('idempotent', 'değişmez sonuçlu', 'adjective'),
    ('latency', 'gecikme', 'noun'),
    ('resilient', 'dayanıklı', 'adjective'),
    ('onboarding', 'işe/ürüne alıştırma', 'noun'),
    ('stakeholder', 'paydaş', 'noun'),
    ('mitigate', 'hafifletmek', 'verb'),
]


class Command(BaseCommand):
    help = 'Landing hero görselini (açık + koyu) çalışan uygulamadan üretir.'

    def add_arguments(self, parser):
        parser.add_argument('--base-url', default='http://127.0.0.1:8000',
                            help='Çalışan uygulamanın adresi.')
        parser.add_argument('--width', type=int, default=1184)
        parser.add_argument('--height', type=int, default=700)
        parser.add_argument('--scroll', type=int, default=210,
                            help='Kadraja haftalık grafiği almak için kaydırma miktarı.')

    def handle(self, *args, **opts):
        try:
            from playwright.sync_api import sync_playwright
            from PIL import Image
        except ImportError as exc:
            raise CommandError(
                'playwright ve pillow gerekli: pip install playwright pillow '
                '&& playwright install chromium'
            ) from exc

        from django.conf import settings
        out_dir = settings.BASE_DIR / 'static' / 'img'
        out_dir.mkdir(parents=True, exist_ok=True)

        user = self._seed()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                for theme, filename in (('light', 'hero-panel.webp'),
                                        ('dark', 'hero-panel-dark.webp')):
                    self._capture(browser, Image, theme, out_dir / filename, opts)
                browser.close()
        finally:
            # Gösterim hesabı hiçbir koşulda geride kalmamalı.
            user.delete()
            self.stdout.write(self.style.SUCCESS('Gösterim hesabı silindi.'))

    # ---------------------------------------------------------------- veri
    def _seed(self):
        from apps.accounts.models import UserLevel
        from apps.topics.models import Topic, TopicCompletion
        from apps.vocabulary.models import Word
        from apps.quizzes.models import QuizSession
        from apps.wordbank.models import BankWord, BankProgress

        User = get_user_model()
        User.objects.filter(username=DEMO_USERNAME).delete()
        user = User.objects.create_user(username=DEMO_USERNAME, password=DEMO_PASSWORD)

        rng = random.Random(7)
        today = timezone.now().date()
        words = list(BankWord.objects.filter(level='A1').order_by('rank')[:140])
        if not words:
            raise CommandError('Kelime bankası boş — önce load_wordbank çalıştır.')

        i = 0
        for offset, count in enumerate(DAILY_MASTERED):
            day = today - timedelta(days=len(DAILY_MASTERED) - 1 - offset)
            for _ in range(count):
                if i >= len(words):
                    break
                progress = BankProgress.objects.create(
                    user=user, word=words[i], mastered=True, correct_count=1)
                # last_answered_at auto_now: grafiği kurmak için update() şart.
                BankProgress.objects.filter(pk=progress.pk).update(
                    last_answered_at=timezone.make_aware(
                        timezone.datetime.combine(day, timezone.datetime.min.time())
                    ) + timedelta(hours=19, minutes=rng.randint(0, 50))
                )
                i += 1
        for word in words[i:i + 7]:
            BankProgress.objects.create(user=user, word=word, mastered=False, wrong_count=1)

        for topic in Topic.objects.all()[:6]:
            TopicCompletion.objects.create(user=user, topic=topic)

        for english, turkish, pos in PERSONAL_WORDS:
            Word.objects.create(user=user, english=english, turkish=turkish,
                                part_of_speech=pos, mastered=True,
                                times_asked=2, times_correct=2)

        for idx, (topic, correct) in enumerate(zip(Topic.objects.all()[:3], (9, 8, 10))):
            session = QuizSession.objects.create(
                user=user, kind='topic', topic=topic,
                total_questions=10, correct_count=correct, wrong_count=10 - correct)
            QuizSession.objects.filter(pk=session.pk).update(
                finished_at=timezone.now() - timedelta(days=idx + 1, hours=2))

        level, _ = UserLevel.objects.get_or_create(user=user)
        level.current_level, level.score = 'A2', 180
        level.save()

        self.stdout.write('Gösterim verisi hazır.')
        return user

    # ------------------------------------------------------------- görüntü
    def _capture(self, browser, Image, theme, out_path, opts):
        base = opts['base_url'].rstrip('/')
        width, height = opts['width'], opts['height']
        ctx = browser.new_context(viewport={'width': width, 'height': height + 60},
                                  device_scale_factor=2)
        ctx.add_init_script(
            "try{localStorage.setItem('levelenai-theme','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        page.goto(f'{base}/accounts/login/')
        page.fill('input[name=username]', DEMO_USERNAME)
        page.fill('input[name=password]', DEMO_PASSWORD)
        page.click('form:has(input[name=password]) button[type=submit], '
                   'form:has(input[name=password]) input[type=submit]')
        page.wait_for_load_state('networkidle')
        page.goto(base + '/', wait_until='networkidle')
        # PWA bandı ve alt bilgi ürün görselinde gürültü.
        page.evaluate("""() => {
            const b = document.querySelector('.install-banner'); if (b) b.remove();
            const f = document.querySelector('.app-footer'); if (f) f.remove();
        }""")
        page.wait_for_timeout(1700)
        page.evaluate(f'window.scrollTo(0, {opts["scroll"]})')
        page.wait_for_timeout(600)

        tmp = out_path.with_suffix('.png')
        page.screenshot(path=str(tmp),
                        clip={'x': 0, 'y': 0, 'width': width, 'height': height})
        image = Image.open(tmp).convert('RGB')
        image.save(out_path, 'WEBP', quality=86, method=6)
        tmp.unlink()
        ctx.close()
        size_kb = out_path.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(
            f'{out_path.name}: {image.size[0]}x{image.size[1]}, {size_kb} KB'))
