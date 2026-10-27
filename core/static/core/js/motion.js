/* ============================================================
   BHIMS MOTION — progressive enhancement
   ------------------------------------------------------------
   Adds `html.motion`, tags repeated surfaces for a scroll reveal,
   and gives same-site navigation a short fade. Nothing here is
   required for the page to work: with JS off, reduced motion, or
   no IntersectionObserver, every element renders exactly as it
   does today (Motion.css only hides elements under `html.motion`).
   One calm preset only — no intensity switch.

   To revert the motion layer: delete this file, Motion.css and
   their two tags in base.html.
   ============================================================ */
(function () {
    'use strict';

    var root = document.documentElement;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');

    if (!('IntersectionObserver' in window)) return;
    if (reduce && reduce.matches) return;

    /* Stagger between siblings that share a parent; the travel distance and
       duration live in Motion.css (`--m-reveal-dur`, `--m-reveal-dist`). */
    var STAGGER = 30;
    var STAGGER_CAP = 3;

    root.classList.add('motion');

    /* Surfaces that read as a stack of records get a reveal. The
       landing page keeps its own .reveal system, so those nodes are
       skipped here to avoid animating the same card twice. */
    var REVEAL = [
        '.page-header',
        '.stat-card',
        '.result-card:not(.reveal)',
        '.listing-card:not(.reveal)',
        '.inquiry-row',
        '.booking-row',
        '.room-card',
        '.profile-card',
        '.filter-card',
        '.admin-table-wrap',
        '.thread-header',
        '.thread-rate-panel',
        '.landing-feature-card',
        '.bhims-empty',
        '.booking-table-wrap',
        '.form-card',
        '.admin-page > .card',
        '.app-main > .app-content > .card'
    ].join(',');

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('m-in');
            observer.unobserve(entry.target);
        });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 });

    function tag() {
        var groups = new WeakMap();
        var nodes;

        try {
            nodes = document.querySelectorAll(REVEAL);
        } catch (err) {
            return;
        }

        Array.prototype.forEach.call(nodes, function (el) {
            if (el.dataset.motion === 'off') return;
            if (el.closest('.no-motion, .modal, .dropdown-menu, [aria-hidden="true"]')) return;

            /* Above-the-fold surfaces stay fully visible from the first
               paint: hiding them made a short page (System Settings) flash
               completely blank while the observer woke up. The page-level
               fade already covers arrival; the reveal is for what you
               scroll down to. */
            if (el.getBoundingClientRect().top < window.innerHeight * 0.92) return;

            el.classList.add('m-fade', 'm-reveal');

            /* Stagger siblings that share a parent (stat cards, inquiry
               rows, booking rows) but cap the delay so the last card is
               never noticeably late. */
            var parent = el.parentElement;
            var index = groups.get(parent) || 0;
            var delay = Math.min(index, STAGGER_CAP) * STAGGER;
            el.style.setProperty('--m-delay', delay + 'ms');
            groups.set(parent, index + 1);

            observer.observe(el);
        });

        /* Failsafe: if the observer never fires (browser quirk, element
           inside a zero-height container), show everything after 1.6s
           rather than leaving hidden content on the page. */
        window.setTimeout(function () {
            Array.prototype.forEach.call(document.querySelectorAll('.m-reveal:not(.m-in)'), function (el) {
                el.classList.add('m-in');
            });
        }, 700);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', tag);
    } else {
        tag();
    }

    /* ---------- Page-to-page fade ----------
       Only ordinary same-tab links are intercepted: no modified clicks,
       no downloads, no new tabs, no external hosts, no same-page hashes.
       The delay is short enough that a slow response never leaves the
       page fully invisible (Motion.css fades to 0.55, not 0). */
    var LEAVING = 'm-leaving';

    document.addEventListener('click', function (event) {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

        var link = event.target.closest ? event.target.closest('a') : null;
        if (!link) return;
        if (link.target && link.target !== '_self') return;
        if (link.hasAttribute('download') || link.dataset.motion === 'off') return;
        if (link.getAttribute('href') === null) return;

        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#') return;
        if (/^(mailto:|tel:|javascript:)/i.test(href)) return;

        var url;
        try {
            url = new URL(link.href, window.location.href);
        } catch (err) {
            return;
        }
        if (url.origin !== window.location.origin) return;
        if (url.hash && url.pathname === window.location.pathname &&
            url.search === window.location.search) return;

        event.preventDefault();
        document.body.classList.add(LEAVING);
        window.setTimeout(function () {
            window.location.href = url.href;
        }, 90);
    });

    /* Back/forward cache restores the DOM mid-fade; reset it. */
    window.addEventListener('pageshow', function () {
        document.body.classList.remove(LEAVING);
    });

    /* If the visitor flips the OS reduced-motion setting mid-session, stop
       animating rather than fighting the setting. */
    if (reduce && reduce.addEventListener) {
        reduce.addEventListener('change', function (event) {
            if (!event.matches) return;
            root.classList.remove('motion');
        });
    }
})();
