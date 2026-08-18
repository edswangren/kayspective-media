/* Kayspective Media — the entire JS budget: a scroll-state header, a mobile
   drawer, and one reveal-on-scroll observer. No dependencies, no analytics. */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* header gains a background once the hero starts scrolling away */
  var header = document.getElementById('site-header');
  var onScroll = function () {
    header.classList.toggle('is-scrolled', window.scrollY > 24);
  };
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* mobile drawer */
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

  /* reveal on scroll, staggered by position within the parent */
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

  /* Safety sweep. The negative bottom rootMargin above creates a dead zone at
     the foot of the viewport; anything sitting in it when the document is
     already scrolled to its limit would never intersect and would stay
     invisible forever -- which is exactly where the closing CTA lands. This
     reveals anything genuinely on screen, ignoring the margin. */
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
