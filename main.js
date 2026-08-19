/* Kayspective Media — the whole JS budget: a scroll-state header, a mobile
   drawer, one reveal-on-scroll observer, and progressive enhancement for the
   intake form. No dependencies, no analytics. Every feature degrades: with
   scripting off the page is fully visible and the form is an ordinary POST. */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── header gains a background once the hero scrolls away ────────────────── */
  var header = document.getElementById('site-header');
  var onScroll = function () {
    header.classList.toggle('is-scrolled', window.scrollY > 24);
  };
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ── mobile drawer ───────────────────────────────────────────────────────── */
  var toggle = document.getElementById('nav-toggle');
  var nav = document.getElementById('nav');
  var setNav = function (open) {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
  };
  toggle.addEventListener('click', function () {
    setNav(toggle.getAttribute('aria-expanded') !== 'true');
  });
  nav.addEventListener('click', function (e) {
    if (e.target.tagName === 'A') setNav(false);
  });
  addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setNav(false);
  });

  /* ── reveal on scroll, staggered by position within the parent ───────────── */
  (function setupReveals() {
    var items = document.querySelectorAll('.reveal');

    if (reduced || !('IntersectionObserver' in window)) {
      items.forEach(function (el) { el.classList.add('is-in'); });
      return;
    }

    var show = function (el) {
      var siblings = Array.prototype.filter.call(el.parentNode.children, function (n) {
        return n.classList.contains('reveal');
      });
      el.style.setProperty('--d', Math.min(siblings.indexOf(el), 5) * 90 + 'ms');
      el.classList.add('is-in');
    };

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        show(entry.target);
        io.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.05 });
    items.forEach(function (el) { io.observe(el); });

    /* Safety sweep. The negative bottom rootMargin creates a dead zone at the
       foot of the viewport; anything sitting in it when the document is already
       scrolled to its limit would never intersect and would stay invisible
       forever -- which is exactly where the closing CTA lands. This reveals
       anything genuinely on screen, ignoring the margin. */
    var ticking = false;
    var sweep = function () {
      ticking = false;
      document.querySelectorAll('.reveal:not(.is-in)').forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.top < innerHeight && r.bottom > 0) { show(el); io.unobserve(el); }
      });
    };
    addEventListener('scroll', function () {
      if (!ticking) { ticking = true; requestAnimationFrame(sweep); }
    }, { passive: true });
    addEventListener('resize', sweep, { passive: true });
    addEventListener('load', sweep);
  })();

  /* ── intake form ─────────────────────────────────────────────────────────── */
  (function setupIntake() {
    var form = document.getElementById('intake');
    if (!form) return;

    var status = document.getElementById('intake-status');
    var submit = document.getElementById('intake-submit');
    var FIELDS = ['business', 'name', 'email', 'support'];
    var FALLBACK = 'Please email kayspectivemedia@gmail.com.';

    var setError = function (name, message) {
      var input = form.elements[name];
      var slot = document.getElementById('e-' + name);
      if (!input || !slot) return;
      input.setAttribute('aria-invalid', message ? 'true' : 'false');
      slot.textContent = message || '';
      slot.hidden = !message;
      if (message) input.setAttribute('aria-describedby', slot.id);
      else input.removeAttribute('aria-describedby');
    };

    var clearErrors = function () {
      FIELDS.forEach(function (n) { setError(n, ''); });
      status.hidden = true;
      status.removeAttribute('data-state');
    };

    var say = function (message, state) {
      status.textContent = message;
      status.hidden = false;
      status.setAttribute('data-state', state);
    };

    /* Replace the form outright on success: leaving a filled-in form on screen
       invites a duplicate submission. */
    var succeed = function () {
      var done = document.createElement('div');
      done.className = 'form-done';
      done.setAttribute('tabindex', '-1');
      done.innerHTML =
        '<h3>Thank you.</h3><p>I&rsquo;ve got your details and I&rsquo;ll come back to you ' +
        'personally, usually within two business days.</p>';
      form.replaceWith(done);
      done.focus();
    };

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clearErrors();

      form.setAttribute('data-sending', '');
      submit.disabled = true;
      var original = submit.textContent;
      submit.textContent = 'Sending…';

      var restore = function () {
        form.removeAttribute('data-sending');
        submit.disabled = false;
        submit.textContent = original;
      };

      fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'Accept': 'application/json', 'X-Requested-With': 'fetch' }
      })
        .then(function (res) {
          return res.json().catch(function () { return { ok: res.ok }; });
        })
        .then(function (body) {
          if (body.ok) return succeed();
          restore();
          if (body.errors) {
            Object.keys(body.errors).forEach(function (k) { setError(k, body.errors[k]); });
            var first = form.querySelector('[aria-invalid="true"]');
            if (first) first.focus();
            say('Please check the highlighted fields.', 'error');
          } else {
            say(body.message || 'Something went wrong. ' + FALLBACK, 'error');
          }
        })
        .catch(function () {
          restore();
          say('Could not reach the server. ' + FALLBACK, 'error');
        });
    });
  })();
})();
