(function () {
    'use strict';

    var header = document.querySelector('.site-header');

    function onScroll() {
        if (!header) return;
        header.classList.toggle('is-scrolled', window.scrollY > 8);
    }

    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    function markMissingImages(root) {
        (root || document).querySelectorAll('img[data-fallback]').forEach(function (img) {
            function markMissing() {
                var frame = img.closest('.media-frame');
                if (frame) frame.classList.add('is-missing');
            }

            img.addEventListener('error', markMissing, { once: true });
            if (img.complete && img.naturalWidth === 0) markMissing();
        });
    }

    markMissingImages(document);

    function bindPasswordToggles(root) {
        (root || document).querySelectorAll('[data-password-toggle]').forEach(function (button) {
            if (button.dataset.bound) return;
            button.dataset.bound = 'true';
            button.addEventListener('click', function () {
                var target = document.getElementById(button.getAttribute('data-password-toggle'));
                if (!target) return;
                var showing = target.type === 'text';
                target.type = showing ? 'password' : 'text';
                button.textContent = showing ? 'Show' : 'Hide';
                button.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
                target.focus();
            });
        });
    }

    bindPasswordToggles(document);

    function bindAddToCart(root) {
        (root || document).querySelectorAll('form[data-add-to-cart]').forEach(function (form) {
            if (form.dataset.bound) return;
            form.dataset.bound = 'true';
            form.addEventListener('submit', function () {
                var button = form.querySelector('button[type="submit"]');
                if (!button) return;
                button.classList.add('is-loading');
                button.setAttribute('aria-busy', 'true');
            });
        });
    }

    bindAddToCart(document);

    function initToasts(root) {
        (root || document).querySelectorAll('.app-toast').forEach(function (toast) {
            if (toast.dataset.bound) return;
            toast.dataset.bound = 'true';
            var close = toast.querySelector('.app-toast__close');
            var timer = window.setTimeout(function () {
                toast.remove();
            }, 5200);
            if (close) {
                close.addEventListener('click', function () {
                    window.clearTimeout(timer);
                    toast.remove();
                });
            }
        });
    }

    initToasts(document);

    document.addEventListener('click', function (event) {
        var suggestions = document.getElementById('suggestions');
        if (!suggestions) return;
        if (!event.target.closest('.search-box')) {
            suggestions.innerHTML = '';
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        var suggestions = document.getElementById('suggestions');
        if (suggestions) suggestions.innerHTML = '';
    });

    document.addEventListener('htmx:afterSwap', function (event) {
        markMissingImages(event.detail.target || document);
        bindPasswordToggles(event.detail.target || document);
        bindAddToCart(event.detail.target || document);
    });

    window.addEventListener('pageshow', function () {
        document.querySelectorAll('.is-loading').forEach(function (element) {
            element.classList.remove('is-loading');
            element.removeAttribute('aria-busy');
        });
    });

    document.querySelectorAll('#mobileMenu .nav-pill, #mobileMenu .dropdown-item').forEach(function (link) {
        link.addEventListener('click', function () {
            var menu = document.getElementById('mobileMenu');
            if (!menu || !menu.classList.contains('show')) return;
            var toggler = document.querySelector('[data-bs-target="#mobileMenu"]');
            if (toggler && window.bootstrap) {
                window.bootstrap.Collapse.getOrCreateInstance(menu).hide();
            }
        });
    });
})();
