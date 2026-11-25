// WebPulse UI helpers (2026 redesign): mobile navigation drawer + masked secret (API key) reveal/copy.
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // ---- Mobile navigation drawer ----
        var body = document.body;
        document.querySelectorAll('[data-wp-nav-open]').forEach(function (btn) {
            btn.addEventListener('click', function () { body.classList.add('wp-nav-open'); });
        });
        document.querySelectorAll('[data-wp-nav-close]').forEach(function (el) {
            el.addEventListener('click', function () { body.classList.remove('wp-nav-open'); });
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') body.classList.remove('wp-nav-open');
        });

        // ---- Masked secrets: <div class="wp-secret" data-secret="..."> ----
        document.querySelectorAll('.wp-secret').forEach(function (box) {
            var value = box.getAttribute('data-secret') || '';
            var out = box.querySelector('.wp-secret-value');
            var reveal = box.querySelector('[data-wp-secret-reveal]');
            var copy = box.querySelector('[data-wp-secret-copy]');
            var masked = '•'.repeat(Math.min(Math.max(value.length, 8), 32));
            var shown = false;

            function render() {
                out.textContent = shown ? value : masked;
                box.classList.toggle('is-revealed', shown);
                if (reveal) {
                    reveal.setAttribute('aria-pressed', shown ? 'true' : 'false');
                    reveal.querySelector('span').textContent = shown ? (reveal.dataset.hideLabel || 'Hide') : (reveal.dataset.showLabel || 'Reveal');
                }
            }
            render();

            if (reveal) reveal.addEventListener('click', function () { shown = !shown; render(); });

            if (copy) copy.addEventListener('click', function () {
                var done = function () {
                    var label = copy.querySelector('span');
                    var original = label.textContent;
                    label.textContent = copy.dataset.copiedLabel || 'Copied';
                    copy.classList.add('is-copied');
                    setTimeout(function () { label.textContent = original; copy.classList.remove('is-copied'); }, 1800);
                };
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(value).then(done);
                } else {
                    // http:// on a LAN address has no Clipboard API - fall back to a temporary selection
                    var ta = document.createElement('textarea');
                    ta.value = value;
                    ta.setAttribute('readonly', '');
                    ta.style.position = 'fixed';
                    ta.style.opacity = '0';
                    document.body.appendChild(ta);
                    ta.select();
                    try { document.execCommand('copy'); done(); } finally { document.body.removeChild(ta); }
                }
            });
        });
    });
})();
