/* Kayspective Media — the whole JS budget: a scroll-state header, a mobile
 drawer, one reveal-on-scroll observer, progressive enhancement for the intake
 form, and city type-ahead. No dependencies, no analytics. Every feature
 degrades: with scripting off the page is fully visible, the form is an
 ordinary POST, and the city field is a plain text input. */
import { buildQueryUrl, toSuggestions } from './lib/photon.js';
import { sourcesFor, shouldAutoplay, controlLabel } from './lib/reelvideo.js';

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
  /* body carries it too: the sticky CTA sits outside this subtree and has to
     stand down while the drawer is over the page. */
  document.body.classList.toggle('nav-open', open);
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

/* ── selected-work reels upgrade to video when footage exists ────────────── */
(function setupReelVideo() {
  var figures = document.querySelectorAll('.reel[data-src]');
  if (!figures.length || !('IntersectionObserver' in window)) return;

  /* The still <picture> stays in the flow and keeps its intrinsic dimensions,
     so it goes on carrying the layout -- the clip is laid over it. That costs
     nothing, rules out a shift when the first frame paints, and leaves a real
     poster behind for any clip that never loads. */
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  var mayAutoplay = shouldAutoplay({ reduced: reduced, saveData: saveData });

  /* A rejected play() is ordinary -- a policy block, a clip still loading, a
     backgrounded tab. Fall back to the poster rather than insisting. */
  var playReel = function (reel) {
    reel.video.preload = 'auto';
    var p = reel.video.play();
    if (p && p.catch) p.catch(function () { reel.playing = false; reel.sync(); });
  };

  var upgrade = function (figure) {
    var sources = sourcesFor(figure.getAttribute('data-src'));
    var frame = figure.querySelector('picture');
    if (!sources.length || !frame) return null;

    var video = document.createElement('video');
    video.muted = true;            // property, not attribute: Safari checks this to allow autoplay
    video.loop = true;
    video.playsInline = true;
    video.preload = 'none';
    video.setAttribute('muted', '');
    video.setAttribute('loop', '');
    video.setAttribute('playsinline', '');
    video.setAttribute('aria-hidden', 'true');   // decorative; the figcaption names it
    video.tabIndex = -1;
    sources.forEach(function (s) {
      var el = document.createElement('source');
      el.src = s.src;
      el.type = s.type;
      video.appendChild(el);
    });

    var caption = figure.querySelector('figcaption');
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'reel-toggle';
    button.setAttribute('aria-label', controlLabel(false, caption && caption.textContent));

    var reel = { figure: figure, video: video, button: button, caption: caption,
                 wanted: mayAutoplay, playing: false, failed: false };

    var sync = function () {
      button.setAttribute('aria-label', controlLabel(reel.playing, caption && caption.textContent));
      button.setAttribute('aria-pressed', reel.playing ? 'false' : 'true');
      figure.classList.toggle('is-playing', reel.playing);
    };
    reel.sync = sync;

    video.addEventListener('playing', function () { reel.playing = true; sync(); });
    video.addEventListener('pause', function () { reel.playing = false; sync(); });
    video.addEventListener('error', function () {
      reel.failed = true;
      figure.classList.remove('has-video', 'is-playing');
      if (video.parentNode) video.parentNode.removeChild(video);
      if (button.parentNode) button.parentNode.removeChild(button);
    }, true);

    button.addEventListener('click', function () {
      reel.wanted = !reel.playing;       // an explicit choice outranks the observer
      if (reel.wanted) playReel(reel); else video.pause();
      sync();
    });

    frame.appendChild(video);
    figure.appendChild(button);
    figure.classList.add('has-video');
    sync();
    return reel;
  };

  var reels = Array.prototype.map.call(figures, upgrade).filter(Boolean);
  if (!reels.length) return;

  /* Play only what is actually on screen: four looping clips running off-screen
     burn phone battery and cellular data for an audience arriving from
     Instagram, and pausing on exit costs nothing.

     A quarter, tested against the ratio rather than left to isIntersecting. A
     9:16 reel is most of the viewport's height on both phone and desktop, so
     anything near a half is unreachable for much of the scroll -- and
     isIntersecting alone is true at a single visible pixel. */
  var VISIBLE_ENOUGH = 0.25;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var reel = reels.find(function (r) { return r.figure === entry.target; });
      if (!reel || reel.failed) return;
      if (entry.intersectionRatio >= VISIBLE_ENOUGH) {
        if (reel.wanted) playReel(reel);
      } else if (reel.playing) {
        reel.video.pause();
      }
    });
  }, { threshold: [0, VISIBLE_ENOUGH] });

  reels.forEach(function (r) { io.observe(r.figure); });

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) reels.forEach(function (r) { if (r.playing) r.video.pause(); });
  });
})();

/* ── sticky call to action on small screens ──────────────────────────────── */
(function setupStickyCta() {
  /* Below the nav breakpoint the header's "Start a project" button is inside
     the collapsed drawer, so the hero button is the only call to action on the
     page -- and it scrolls away in the first swipe. This puts one back within
     reach for the whole middle of the document, and stands down once the form
     itself is on screen. */
  var bar = document.getElementById('sticky-cta');
  var hero = document.querySelector('.hero');
  var contact = document.getElementById('contact');
  if (!bar || !hero || !contact || !('IntersectionObserver' in window)) return;

  var past = { hero: false, contact: false };
  var apply = function () {
    bar.classList.toggle('is-up', past.hero && !past.contact);
  };

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.target === hero) past.hero = !entry.isIntersecting;
      if (entry.target === contact) past.contact = entry.isIntersecting;
    });
    apply();
  }, { threshold: 0 });

  io.observe(hero);
  io.observe(contact);
})();

/* ── CTAs that arrive at the form with an answer already chosen ──────────── */
(function setupSupportShortcut() {
  /* Keyed off a data attribute rather than the option's text: that text has to
     match SUPPORT_LEVELS on the server character for character, so nothing else
     should be holding a second copy of it. */
  var select = document.getElementById('f-support');
  if (!select) return;
  document.querySelectorAll('a[data-support]').forEach(function (link) {
    link.addEventListener('click', function () {
      var opt = select.querySelector('option[data-key="' + link.dataset.support + '"]');
      if (opt) select.value = opt.value;
    });
  });
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
      /* Turnstile tokens are single-use: without a reset, a second attempt after
         a validation error would send a spent token and be refused. */
      if (window.turnstile) window.turnstile.reset();
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

/* ── city type-ahead ───────────────────────────────────────────────────────
   Upgrades the plain city input into an ARIA combobox backed by Photon. Every
   failure path falls back to the input behaving as ordinary free text — the
   field is optional and must never block a submission. */
(function setupCitySuggest() {
  const input = document.getElementById('f-city');
  const list = document.getElementById('city-list');
  if (!input || !list || !('fetch' in window) || !('AbortController' in window)) return;

  /* Our listbox and the browser's own address dropdown would otherwise stack on
     top of each other. Native autofill stays in the markup for the no-JS case. */
  input.setAttribute('autocomplete', 'off');
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-expanded', 'false');
  input.setAttribute('aria-controls', 'city-list');
  input.setAttribute('aria-autocomplete', 'list');

  const live = document.createElement('span');
  live.className = 'visually-hidden';
  live.setAttribute('role', 'status');
  live.setAttribute('aria-live', 'polite');
  input.parentNode.appendChild(live);

  const cache = new Map();          // query -> suggestions, so retyping is free
  let controller = null;
  let timer = null;
  let options = [];
  let active = -1;

  const close = function () {
    list.hidden = true;
    list.innerHTML = '';
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    options = [];
    active = -1;
  };

  const setActive = function (index) {
    if (!options.length) return;
    active = (index + options.length) % options.length;
    options.forEach(function (el, i) {
      el.setAttribute('aria-selected', String(i === active));
    });
    input.setAttribute('aria-activedescendant', options[active].id);
    options[active].scrollIntoView({ block: 'nearest' });
  };

  const choose = function (label) {
    input.value = label;
    close();
    input.focus();
  };

  const render = function (suggestions) {
    if (!suggestions.length) return close();
    list.innerHTML = '';
    options = suggestions.map(function (s, i) {
      const li = document.createElement('li');
      li.className = 'combo-option';
      li.id = 'city-opt-' + i;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', 'false');
      li.textContent = s.label;
      // mousedown, not click: blur would close the list before click fires
      li.addEventListener('mousedown', function (e) { e.preventDefault(); choose(s.label); });
      list.appendChild(li);
      return li;
    });
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    active = -1;
    live.textContent = suggestions.length + (suggestions.length === 1 ? ' suggestion' : ' suggestions');
  };

  const search = function (query) {
    const url = buildQueryUrl(query);
    if (!url) return close();

    if (cache.has(query)) return render(cache.get(query));

    if (controller) controller.abort();
    controller = new AbortController();

    fetch(url, { signal: controller.signal })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error(res.status)); })
      .then(function (payload) {
        const suggestions = toSuggestions(payload);
        cache.set(query, suggestions);
        // the field may have moved on while the request was in flight
        if (input.value.trim() === query) render(suggestions);
      })
      .catch(function (err) {
        // AbortError is expected on every keystroke; anything else just means
        // no suggestions this time. The field still works as free text.
        if (err.name !== 'AbortError') close();
      });
  };

  input.addEventListener('input', function () {
    const query = input.value.trim();
    clearTimeout(timer);
    if (query.length < 2) return close();
    timer = setTimeout(function () { search(query); }, 280);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') return close();
    if (list.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
    else if (e.key === 'Enter' && active > -1) { e.preventDefault(); choose(options[active].textContent); }
    else if (e.key === 'Tab') close();
  });

  input.addEventListener('blur', function () { setTimeout(close, 120); });
  document.addEventListener('click', function (e) {
    if (e.target !== input && !list.contains(e.target)) close();
  });
})();
