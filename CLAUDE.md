# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A single static landing page for Kayspective Media, a social content studio for luxury
hospitality founded by Kaylin "Kay" Mee in Austin, TX. `README.md` covers deployment and
the design rationale; this file covers the parts that are easy to break.

## Commands

```sh
python3 -m http.server 8747                          # dev server — edit, refresh
python3 tools/build_assets.py                        # regenerate every derived asset
python3 -m unittest discover -s tests                # full suite (~0.5s, no deps)
python3 -m unittest tests.test_markup                # one module
python3 -m unittest tests.test_markup.TestContentRules.test_current_employer_is_never_named
```

There is no build step, no package manager, and no linter. Tests are stdlib `unittest`
(Pillow and numpy are needed only for the asset-pipeline module, which the build already
requires). They cover colour maths, generated-asset geometry, and markup/link/contrast
invariants — everything that does **not** require a renderer. Layout, focus order, and
Lighthouse still need the browser pass described under Verification.

## Architecture

Three hand-written files do all the work — `index.html`, `styles.css`, `main.js` — with no
framework and no runtime dependencies. The page makes **zero external network requests**;
fonts are self-hosted variable WOFF2 (one file per family covers weights 300–500). Keep it
that way: adding a CDN link or an npm dependency changes the nature of the project.

### Assets are generated, not authored

Everything in `assets/img/`, plus the logo marks, favicon, apple-touch-icon, and `og.jpg`,
is **output** of `tools/build_assets.py`. Editing those files by hand gets silently
clobbered on the next build. Change the script, then re-run it.

Inputs live in `assets/src/` (Kay's original portrait) and `assets/logo.jpg`. The marble
panels are derived from one CC0 source fetched to `/tmp` on first run, mapped onto a
two-color brand ramp per entry in the `PANELS` list. `assets/CREDITS.md` is the authority
on licensing and on which slots are placeholders.

The founder portrait is a **real photograph**. Its cool rose studio backdrop is recolored
into the brand blush via a border-connected flood-fill mask, so her skin, hair, and
jewellery are untouched. Compositing happens in RGB, never HSV — interpolating hue across
the feathered edge fringes her hair green.

### Placeholder vs. real imagery

The hero, the four 9:16 reel frames, and the divider band are **brand-tinted marble, not
photographs of venues**. They are deliberate placeholders. Every slot is a real `<picture>`
element at a fixed aspect ratio, so real work drops in as a file swap with no layout
change. Do not describe them to the user as finished art direction.

## Things that will bite you

**`--gold-text` vs `--gold-deep`.** Kay's brand deep gold (`#AB7937`) is 3.1:1 on cream —
correct for rules, borders, and large display type, but **below WCAG AA for small text**.
`--gold-text` (`#89602A`) is the same hue darkened until it passes on both cream and sand.
Use `--gold-text` for anything under 24px. Neither passes on the blush CTA band, which is
why the closing email link keeps `--ink` and only moves its underline on hover.

**The `js` class gates all content.** An inline script in `<head>` adds `.js` to
`<html>`, and only `.js .reveal` is hidden. Without it the reveal animations would leave
the entire page invisible when JS fails. Do not move the hidden state onto bare `.reveal`.

**Do not remove the sweep in `main.js`.** The reveal observer's negative bottom
`rootMargin` creates a dead zone at the foot of the viewport. Elements sitting in it when
the document is already scrolled to its limit never intersect — which is exactly where the
closing CTA button and email link land. The rAF-throttled `sweep()` reveals anything
genuinely on screen and is what makes the primary conversion elements appear at all.

**Reveal stagger reads sibling order,** so a `.reveal` element inherits its delay from its
position among `.reveal` siblings in the same parent (capped at 5).

**`hero` and `band` are CSS backgrounds, not `<picture>`,** so `srcset` cannot reach them.
Their small-screen `@half` variants are switched manually in a `max-width: 700px` block.
If you add another CSS-background image, wire its half-size variant the same way.

**Testing reveals via scripted scrolling gives false negatives.** Teleporting the scroll
position outruns the IntersectionObserver, and reading `opacity` mid-transition (700ms plus
up to 450ms of stagger) reports elements as hidden that are actually fading in. Scroll at a
human pace and wait ~2.5s before asserting.

**`.nojekyll` is required.** GitHub Pages runs Jekyll by default, which silently strips
files beginning with an underscore — it would eat `_headers`.

**The `noindex` and canonical are hostname-scoped on purpose.** The review preview carries
`noindex, nofollow`; both it and the canonical switch themselves off automatically once the
site is served from `kayspectivemedia.com`. This is not a bug and needs no cleanup at
launch.

## Content rules

These are correctness constraints on a live business site, not style preferences.

- **Never name Kay's current employer.** Her background there is what makes the About copy
  credible, but naming it implies portfolio rights and endorsement she may not have.
- **No invented client names, testimonials, or case studies.** The work section says "full
  portfolio available on request" instead.
- All body copy is provisional, wrapped in `<!-- COPY: provisional -->` / `<!-- /COPY -->`
  and indexed in `README.md`. Text blocks are sized by character measure — `--measure`
  (62ch) on the About paragraphs, per-section `ch` values elsewhere — not by the specific
  words, so rewriting copy should never require touching CSS.
- The About section still needs Kay's factual sign-off before the production domain goes
  live.

## Verification

Before calling visual or accessibility work done, check in a real browser at 390 / 768 /
1440 (Chrome DevTools MCP is available):

- Lighthouse — currently 100 for accessibility, best practices, and SEO on desktop and
  mobile; treat any regression as a bug
- Contrast: every text/background pair at 4.5:1 (3:1 for large type), audited against the
  *rendered* colors rather than assumed from tokens
- Zero external requests, zero console errors, no horizontal scroll
- Renders fully with the `js` class removed, and under `prefers-reduced-motion`

Run `python3 -m unittest discover -s tests` first — it catches broken asset paths, wrong
declared image dimensions, contrast regressions, and content-rule violations in half a
second, without launching anything.
