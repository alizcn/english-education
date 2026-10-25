(function () {
    'use strict';
    var doc = document.documentElement;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var finePointer = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    // Hero başlığı kelime kelime: her kelime kendi maskesinin altından yükselir.
    var title = document.querySelector('.l-hero-title');
    if (title && !reduce) {
        var wi = 0;
        var wrap = function (content) {
            var outer = document.createElement('span');
            outer.className = 'w';
            var inner = document.createElement('span');
            inner.style.setProperty('--wi', wi++);
            inner.appendChild(content);
            outer.appendChild(inner);
            return outer;
        };
        Array.prototype.slice.call(title.childNodes).forEach(function (node) {
            if (node.nodeType === 3) {
                var parts = node.nodeValue.split(/(\s+)/);
                var frag = document.createDocumentFragment();
                parts.forEach(function (p) {
                    if (!p) return;
                    frag.appendChild(/^\s+$/.test(p) ? document.createTextNode(' ') : wrap(document.createTextNode(p)));
                });
                title.replaceChild(frag, node);
            } else if (node.nodeType === 1) {
                title.replaceChild(wrap(node.cloneNode(true)), node);
            }
        });
        title.classList.add('is-split');
    }

    // Izgara çocuklarına sıra indeksi: CSS gecikmesi --i ile hesaplanıyor.
    document.querySelectorAll('.reveal, .compare-grid').forEach(function (grid) {
        Array.prototype.forEach.call(grid.children, function (child, i) {
            child.style.setProperty('--i', i);
        });
    });

    // Kaydırınca belirme
    var targets = document.querySelectorAll('.reveal, .fade-up, .l-steps');
    if ('IntersectionObserver' in window && !reduce) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    e.target.classList.add('is-visible');
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
        targets.forEach(function (el) { io.observe(el); });
    } else {
        targets.forEach(function (el) { el.classList.add('is-visible'); });
    }

    // Sayılar sıfırdan sayarak gelir ("6.000+", "1,250", "42" gibi)
    function countUp(el) {
        var node = null;
        for (var i = 0; i < el.childNodes.length; i++) {
            var n = el.childNodes[i];
            if (n.nodeType === 3 && /\d/.test(n.nodeValue)) { node = n; break; }
        }
        if (!node) return;
        var raw = node.nodeValue;
        var m = raw.match(/^(\s*)([\d.,]+)(.*)$/s);
        if (!m) return;
        var sep = /\d[.,]\d{3}\b/.test(m[2]) ? m[2].replace(/\d/g, '').charAt(0) : '';
        var target = parseInt(m[2].replace(/[.,]/g, ''), 10);
        if (!target || target < 3) return;
        var dur = Math.min(1600, 600 + target * 4);
        var start = null;
        function fmt(v) {
            var s = String(v);
            return sep ? s.replace(/\B(?=(\d{3})+(?!\d))/g, sep) : s;
        }
        function step(ts) {
            if (!start) start = ts;
            var p = Math.min(1, (ts - start) / dur);
            var eased = 1 - Math.pow(1 - p, 4);
            node.nodeValue = m[1] + fmt(Math.round(target * eased)) + m[3];
            if (p < 1) requestAnimationFrame(step);
        }
        node.nodeValue = m[1] + fmt(0) + m[3];
        requestAnimationFrame(step);
    }
    var counters = document.querySelectorAll('.l-metric-value, .stat-tile-value, [data-count]');
    if (counters.length && !reduce && 'IntersectionObserver' in window) {
        var cio = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) { countUp(e.target); cio.unobserve(e.target); }
            });
        }, { threshold: 0.5 });
        counters.forEach(function (el) { cio.observe(el); });
    }

    // İmleci izleyen kart ışığı
    if (finePointer && !reduce) {
        var spotSel = '.l-feature-card, .audience-card, .pub-card, .feature-card, .stat-tile, .l-step, .reason-card, .compare-card, .action-card, .capability, .l-metric';
        document.querySelectorAll(spotSel).forEach(function (el) { el.classList.add('spot'); });
        document.addEventListener('pointermove', function (e) {
            var card = e.target.closest && e.target.closest('.spot');
            if (!card) return;
            var r = card.getBoundingClientRect();
            card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
            card.style.setProperty('--my', (e.clientY - r.top) + 'px');
        }, { passive: true });
    }

    // Mıknatıs butonlar: imlece doğru en fazla 10px eğilir
    if (finePointer && !reduce) {
        document.querySelectorAll('.landing-btn-primary, .landing-btn-ghost').forEach(function (btn) {
            btn.classList.add('magnetic');
            btn.addEventListener('pointermove', function (e) {
                var r = btn.getBoundingClientRect();
                var dx = (e.clientX - r.left - r.width / 2) * 0.25;
                var dy = (e.clientY - r.top - r.height / 2) * 0.35;
                btn.style.setProperty('--mgx', Math.max(-10, Math.min(10, dx)) + 'px');
                btn.style.setProperty('--mgy', Math.max(-8, Math.min(8, dy)) + 'px');
            });
            btn.addEventListener('pointerleave', function () {
                btn.style.setProperty('--mgx', '0px');
                btn.style.setProperty('--mgy', '0px');
            });
        });
    }

    // Konfeti
    function confetti(x, y, count) {
        if (reduce) return;
        var cs = getComputedStyle(doc);
        var colors = ['--primary-600', '--accent', '--success-fill', '--f-interview', '--f-vocabulary', '--f-quiz']
            .map(function (v) { return cs.getPropertyValue(v).trim() || '#06B6D4'; });
        for (var i = 0; i < count; i++) {
            var b = document.createElement('span');
            b.className = 'confetti-bit';
            b.style.left = x + 'px';
            b.style.top = y + 'px';
            b.style.background = colors[i % colors.length];
            b.style.setProperty('--dx', (Math.random() * 360 - 180) + 'px');
            b.style.setProperty('--up', (-80 - Math.random() * 160) + 'px');
            b.style.setProperty('--dy', (120 + Math.random() * 220) + 'px');
            b.style.setProperty('--rot', (Math.random() * 900 - 450) + 'deg');
            b.style.animationDelay = (Math.random() * 0.08) + 's';
            if (i % 3 === 0) { b.style.width = '7px'; b.style.height = '7px'; b.style.borderRadius = '50%'; }
            b.addEventListener('animationend', function () { this.remove(); });
            document.body.appendChild(b);
        }
    }

    // Canlı kelime quizi (landing)
    var quiz = document.querySelector('[data-quiz]');
    var dataEl = document.getElementById('showcase-data');
    if (quiz && dataEl) {
        var pool = [];
        try { pool = JSON.parse(dataEl.textContent) || []; } catch (err) { pool = []; }
        var ROUNDS = 5;
        var $ = function (sel) { return quiz.querySelector(sel); };
        var flip = $('.flip'), term = $('.quiz-demo__term'), lvl = $('.quiz-demo__lvl'),
            opts = $('.quiz-demo__options'), fb = $('.quiz-demo__feedback'), next = $('.quiz-demo__next'),
            scoreEl = $('.quiz-demo__score'), ex = $('.quiz-demo__ex'), exTr = $('.quiz-demo__ex-tr'),
            end = $('.quiz-demo__end'), finalNum = $('.quiz-demo__final-num'),
            dots = quiz.querySelectorAll('.quiz-demo__dots i');
        var rounds = [], idx = 0, score = 0;
        var shuffle = function (a) {
            a = a.slice();
            for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
            return a;
        };
        var norm = function (s) { return String(s).toLocaleLowerCase().trim(); };

        function build() {
            var picked = shuffle(pool).slice(0, ROUNDS);
            rounds = picked.map(function (w) {
                var seen = {}; seen[norm(w.meaning)] = 1;
                var distractors = [];
                shuffle(pool).some(function (o) {
                    if (o.term !== w.term && !seen[norm(o.meaning)]) { seen[norm(o.meaning)] = 1; distractors.push(o.meaning); }
                    return distractors.length === 2;
                });
                return { word: w, options: shuffle([w.meaning].concat(distractors)) };
            });
            idx = 0; score = 0;
            dots.forEach(function (d) { d.className = ''; });
            end.hidden = true;
        }

        function render() {
            var r = rounds[idx];
            flip.classList.remove('is-flipped');
            lvl.textContent = r.word.level;
            lvl.className = 'word-pill__lvl quiz-demo__lvl lvl-' + r.word.level.toLowerCase();
            term.textContent = r.word.term;
            if (r.word.lang) { term.lang = r.word.lang; ex.lang = r.word.lang; }
            term.classList.remove('is-in'); void term.offsetWidth; term.classList.add('is-in');
            ex.textContent = r.word.example || '';
            exTr.textContent = r.word.example_translation || r.word.meaning;
            opts.innerHTML = '';
            r.options.forEach(function (m, i) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'quiz-opt';
                b.style.setProperty('--oi', i);
                var k = document.createElement('span');
                k.className = 'quiz-opt__key';
                k.textContent = 'ABC'.charAt(i);
                b.appendChild(k);
                b.appendChild(document.createTextNode(m));
                b.dataset.meaning = m;
                b.addEventListener('click', function () { answer(b); });
                opts.appendChild(b);
            });
            fb.textContent = ''; fb.className = 'quiz-demo__feedback';
            next.hidden = true;
            dots.forEach(function (d, i) { d.classList.toggle('is-current', i === idx); });
            scoreEl.textContent = score + '/' + ROUNDS;
        }

        function answer(btn) {
            var r = rounds[idx];
            var right = btn.dataset.meaning === r.word.meaning;
            opts.querySelectorAll('.quiz-opt').forEach(function (b) {
                b.disabled = true;
                if (b.dataset.meaning === r.word.meaning) b.classList.add('is-right');
                else if (b !== btn) b.classList.add('is-dim');
            });
            dots[idx].classList.remove('is-current');
            if (right) {
                score++;
                var rect = btn.getBoundingClientRect();
                confetti(rect.left + rect.width / 2, rect.top + rect.height / 2, 28);
                fb.textContent = quiz.dataset.correct; fb.classList.add('is-right');
                dots[idx].classList.add('is-right');
            } else {
                btn.classList.add('is-wrong');
                fb.textContent = quiz.dataset.wrong; fb.classList.add('is-wrong');
                dots[idx].classList.add('is-wrong');
            }
            scoreEl.textContent = score + '/' + ROUNDS;
            setTimeout(function () { flip.classList.add('is-flipped'); }, 420);
            next.textContent = (idx === ROUNDS - 1 ? quiz.dataset.finish : quiz.dataset.next) + ' →';
            next.hidden = false;
        }

        next.addEventListener('click', function () {
            idx++;
            if (idx < ROUNDS) { render(); return; }
            end.hidden = false;
            finalNum.textContent = score;
            if (score >= 3) {
                var rect = quiz.getBoundingClientRect();
                confetti(rect.left + rect.width / 2, rect.top + rect.height * 0.35, 70);
            }
        });
        quiz.querySelector('.quiz-demo__replay').addEventListener('click', function () { build(); render(); });

        if (pool.length >= ROUNDS + 2) { build(); render(); }
        else quiz.closest('section').hidden = true;
    }

    // Kaydırma: menü gölgesi, ilerleme çubuğu, ürün görselinin eğimi
    var shot = document.querySelector('.hero-shot__frame');
    var bar = null;
    if (document.querySelector('.landing-nav')) {
        bar = document.createElement('div');
        bar.className = 'scroll-progress';
        bar.setAttribute('aria-hidden', 'true');
        document.body.appendChild(bar);
    }
    if (shot && !reduce) shot.style.setProperty('--tilt', '1');

    var ticking = false;
    function onScroll() {
        ticking = false;
        var y = window.scrollY || doc.scrollTop;
        doc.classList.toggle('is-scrolled', y > 8);
        if (bar) {
            var max = doc.scrollHeight - window.innerHeight;
            bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, y / max) : 0) + ')';
        }
        if (shot && !reduce) {
            var r = shot.getBoundingClientRect();
            var vh = window.innerHeight;
            var p = Math.max(0, Math.min(1, (r.top - vh * 0.25) / (vh * 0.6)));
            shot.style.setProperty('--tilt', p.toFixed(3));
        }
    }
    window.addEventListener('scroll', function () {
        if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
    }, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    onScroll();
})();
