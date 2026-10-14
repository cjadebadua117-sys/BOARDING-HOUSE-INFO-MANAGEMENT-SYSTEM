/* ============================================================================
   BHIMS · the sweeping auth deck (student portal, landlord portal)
   ----------------------------------------------------------------------------
   Paired with core/static/core/css/auth-deck.css. A page names its own two
   halves in the markup — data-sheet / data-invite / data-alt-mode — so the same
   script drives the student deck (sign in ⇄ create account) and the landlord
   deck (sign in ⇄ how to get an account). Four jobs:

     1. trade the two halves when an invitation's button is pressed;
     2. keep the URL honest — ?mode=<the alt half> — so the half that is not
        sign-in can still be linked, reloaded and bookmarked;
     3. leave the document describing what is actually on screen: the parked
        sheet goes `hidden`, the parked invitation goes aria-hidden + inert and
        out of the tab order, and focus follows the form that arrived;
     4. the long registration form's own two hints: the K-12 grade-level row
        and the password strength meter.

   The sweep is skipped — one frame instead of 1.15s of travel — under
   prefers-reduced-motion, and under the 900px breakpoint where the stylesheet
   moves the invitations into a band above the sheets and there is nowhere to
   travel to. Both media queries are read at click time, so rotating a phone or
   changing the OS setting takes effect on the next press.

   EVERYTHING here is enhancement. With no JavaScript the server's
   initial_mode still decides which sheet is open, both forms still post, and
   the page is simply the sign-in half with an inert invitation button.
   ==========================================================================*/
(function () {
    'use strict';

    var deck = document.querySelector('.auth-deck');
    if (!deck) return;

    /* Must match --deck-sweep in the stylesheet: the sheet that leaves is only
       taken out of the document once the curve has finished crossing. */
    var SWEEP_MS = 1150;
    var FOCUS_MS = SWEEP_MS + 80;

    var sheets = {};
    var invites = {};
    Array.prototype.forEach.call(deck.querySelectorAll('[data-sheet]'), function (el) {
        sheets[el.getAttribute('data-sheet')] = el;
    });
    Array.prototype.forEach.call(deck.querySelectorAll('[data-invite]'), function (el) {
        invites[el.getAttribute('data-invite')] = el;
    });

    /* "signin" is always one half; the other is whatever the page calls it —
       the student deck's registration half, the landlord deck's account panel. */
    var ALT = deck.getAttribute('data-alt-mode') || 'signup';

    var narrow = window.matchMedia('(max-width: 900px)');
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

    function currentMode() {
        var mode = deck.getAttribute('data-mode');
        return sheets[mode] ? mode : 'signin';
    }

    function other(mode) {
        return mode === 'signin' ? ALT : 'signin';
    }

    function sweeps() {
        return !narrow.matches && !reduced.matches;
    }

    /* A parked invitation is still in the document — it has merely ridden off
       the canvas — so it has to be taken out of the reading order and out of
       the tab order by hand. `inert` is the modern way and a missing support
       is ignored; the tabindex covers the one control inside it either way. */
    function parkInvite(invite, parked) {
        if (!invite) return;
        invite.setAttribute('aria-hidden', parked ? 'true' : 'false');
        var btn = invite.querySelector('.auth-deck-cta');
        if (btn) {
            if (parked) { btn.setAttribute('tabindex', '-1'); }
            else { btn.removeAttribute('tabindex'); }
        }
        if (parked) { invite.setAttribute('inert', ''); }
        else { invite.removeAttribute('inert'); }
    }

    /* Focus the first real control of the sheet that just arrived. On a phone
       the sheet sits under the coloured band, so its top is brought into view
       rather than trusting it to be under the thumb already. */
    function focusArrival(mode) {
        var sheet = sheets[mode];
        if (!sheet) return;
        var field = sheet.querySelector('input:not([type="hidden"]), select');
        if (field) {
            try { field.focus({ preventScroll: true }); } catch (e) { field.focus(); }
        } else {
            /* A half with no fields at all — the landlord account panel — hands
               focus to its first control, and to the panel itself if it has none. */
            var control = sheet.querySelector('a, button');
            if (control) {
                try { control.focus({ preventScroll: true }); } catch (e2) { control.focus(); }
            } else {
                sheet.setAttribute('tabindex', '-1');
                sheet.focus();
            }
        }
        if (narrow.matches && sheet.scrollIntoView) {
            sheet.scrollIntoView({ behavior: reduced.matches ? 'auto' : 'smooth', block: 'start' });
        }
    }

    /* The sheet that is still fading out, if a sweep is in flight. */
    var leaving = null;

    function setMode(next, options) {
        options = options || {};
        var previous = currentMode();
        if (next === previous || !sheets[next]) return;

        var incoming = sheets[next];
        var outgoing = sheets[previous];
        var animate = options.animate !== false && sweeps();

        /* Pressing the other CTA mid-sweep must not leave two sheets
           half-swapped: whatever is still on its way out leaves now. */
        if (leaving) {
            window.clearTimeout(leaving.timer);
            if (leaving.sheet) leaving.sheet.hidden = true;
            leaving = null;
        }

        /* Unhiding the registration sheet normally grows the deck — and the
           page with it — in the same frame the sweep starts, which would yank
           the form column while it is still travelling. So the deck is pinned
           at the height it had and eased to the new one over the same 900ms
           the sheets take to cross. */
        var pinned = deck.offsetHeight;

        incoming.hidden = false;
        incoming.removeAttribute('aria-hidden');
        deck.setAttribute('data-mode', next);

        if (animate && deck.animate) {
            var settled = deck.offsetHeight;
            if (settled !== pinned) {
                deck.style.height = pinned + 'px';
                deck.style.minHeight = pinned + 'px';
                var grow = deck.animate(
                    [{ height: pinned + 'px' }, { height: settled + 'px' }],
                    { duration: 900, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
                );
                var release = function () {
                    deck.style.height = '';
                    deck.style.minHeight = '';
                };
                grow.onfinish = release;
                grow.oncancel = release;
            }
        }

        if (outgoing) {
            outgoing.setAttribute('aria-hidden', 'true');
            if (animate) {
                var sheet = outgoing;
                var timer = window.setTimeout(function () {
                    sheet.hidden = true;
                    if (leaving && leaving.timer === timer) leaving = null;
                }, SWEEP_MS);
                leaving = { sheet: sheet, timer: timer };
            } else {
                outgoing.hidden = true;
            }
        }

        /* Exactly one invitation is live per mode — the one that is NOT the
           mode you are in ("New here?" while signing in). The other rides off
           the canvas on the side its half sits on, so it goes aria-hidden +
           inert + out of the tab order. Same pairing as the stylesheet's
           transforms, and the same pairing the load-time block below sets. */
        parkInvite(invites[next], true);
        parkInvite(invites[other(next)], false);

        try {
            var url = new URL(window.location.href);
            if (next === ALT) { url.searchParams.set('mode', ALT); }
            else { url.searchParams.delete('mode'); }
            window.history.replaceState({}, '', url);
        } catch (e) { /* older browsers: the swap itself still works */ }

        if (options.focus === false) return;
        if (animate) { window.setTimeout(function () { focusArrival(next); }, FOCUS_MS); }
        else { focusArrival(next); }
    }

    /* Each CTA is a real link to the page that renders the half it names —
       which is what happens when this script does not run — and a plain press
       is intercepted so the halves trade in place instead of reloading.
       Modified presses (new tab, download, bookmark) are left alone. */
    Array.prototype.forEach.call(deck.querySelectorAll('[data-goto]'), function (cta) {
        cta.addEventListener('click', function (event) {
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            setMode(cta.getAttribute('data-goto'), { animate: true });
        });
    });

    /* A ?mode=signup link opens the registration half. The views already render
       that half for such a URL, so this is the fallback for a URL that changed
       after the server had spoken (a cached page, a hand-edited address): the
       swap lands in place rather than sweeping there after a flash of the
       sign-in form, and nothing steals focus on load. */
    var requested = null;
    try { requested = new URL(window.location.href).searchParams.get('mode'); }
    catch (e) { /* older browsers: the server's initial_mode stands */ }

    if (requested === ALT && currentMode() !== ALT) {
        deck.setAttribute('data-instant', '');
        setMode(ALT, { animate: false, focus: false });
        /* Two frames: one to lay the deck out in its new position, one to hand
           the transitions back for every press after this one. */
        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () { deck.removeAttribute('data-instant'); });
        });
    }

    /* Match the server's first paint: whichever half is parked in the markup
       is parked for assistive technology too. */
    parkInvite(invites[currentMode()], true);
    parkInvite(invites[other(currentMode())], false);

    /* ── K-12 is the only program that asks for a grade level ─────────────── */
    var programSel = document.querySelector('select[name="program"]');
    var customRow = document.querySelector('[id$="program_custom_wrap"]');
    if (programSel && customRow) {
        var syncCustom = function () {
            var input = customRow.querySelector('input');
            customRow.hidden = !(programSel.value === 'K12' || (input && input.value) || customRow.querySelector('.field-msg'));
        };
        programSel.addEventListener('change', syncCustom);
        syncCustom();
    }

    /* ── The strength meter is a hint only; the server validators still rule ─ */
    var pwd = document.querySelector('input[name="password1"]');
    var meter = document.getElementById('pwdMeter');
    if (pwd && meter) {
        var LABELS = ['Strength', 'Weak', 'Fair', 'Good', 'Strong'];
        pwd.addEventListener('input', function () {
            var value = pwd.value;
            var score = 0;
            if (value.length >= 8) score++;
            if (value.length >= 12) score++;
            if (/[A-Z]/.test(value) && /[a-z]/.test(value) && /\d/.test(value)) score++;
            if (/[^A-Za-z0-9]/.test(value)) score++;
            if (!value) score = 0;
            meter.dataset.score = score;
            meter.querySelector('.pwd-label').textContent = LABELS[score];
        });
    }
})();
