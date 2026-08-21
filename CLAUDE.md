# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A single static landing page for Kayspective Media, a social content studio for luxury
hospitality founded by Kaylin "Kay" Mee in Austin, TX. **Live at
<https://kayspectivemedia.com>** on Cloudflare Pages (project `kayspective-media`).
`README.md` covers deployment and the design rationale; this file covers the parts that
are easy to break.

**Planned work lives in GitHub issues**, not in this file or the README —
`gh issue list`. They carry the rationale and the constraints each one has to respect.

Visitors arrive from Instagram and Facebook links, overwhelmingly on mobile browsers.
Prospects are hospitality founders and operators. Design for that audience.

## Commands

```sh
python3 -m http.server 8747                          # dev server — edit, refresh
python3 tools/build_assets.py                        # regenerate every derived asset
python3 -m unittest discover -s tests                # python suite (~0.6s, no deps)
node --test tests/*.test.mjs                          # intake + type-ahead (node's runner)
python3 -m unittest tests.test_markup                # one module
python3 -m unittest tests.test_markup.TestContentRules.test_current_employer_is_never_named

npx wrangler pages dev dist --port 8788 --compatibility-date=2025-01-01  # with Functions
python3 tools/build_site.py                          # assemble dist/ (the deploy output)
npx wrangler pages deploy dist --project-name kayspective-media --branch main
```

Deploys normally happen by pushing to `main` — `.github/workflows/deploy.yml` runs both
suites, builds `dist/`, and publishes. The commands above are the manual fallback.

`python3 -m http.server` is enough for everything except the contact form, which needs
the wrangler dev server to run the Function. `wrangler pages dev` serves stale HTML after
a rebuild even on a hard reload; add a cache-busting query (`/?cb=1`) when a change should
be visible and isn't.

There is no compile step, no package manager, and no linter — `tools/build_site.py`
only copies the shippable files into `dist/`. Tests are stdlib `unittest`
(Pillow and numpy are needed only for the asset-pipeline module, which the build already
requires). They cover colour maths, generated-asset geometry, and markup/link/contrast
invariants — everything that does **not** require a renderer. Layout, focus order, and
Lighthouse still need the browser pass described under Verification.

## Architecture

Three hand-written files do all the work — `index.html`, `styles.css`, `main.js` — with no
framework and no runtime dependencies. Fonts are self-hosted variable WOFF2 (one file per
family covers weights 300–500).

**Two third parties.** Cloudflare Turnstile loads on sight for the form's bot check;
Photon is called by the city type-ahead once someone types into that field. Fonts and
imagery are self-hosted. A test pins the subresource allowlist to those two, so adding
a third is a decision rather than drift.

`main.js` is an ES module (`<script type="module">`), so it can import `lib/photon.js`.
Modules are deferred by default — do not re-add a `defer` attribute.

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

### Tests

`tests/` is stdlib `unittest`, split by what it can prove without a renderer:

| Module | Owns |
|---|---|
| `test_design_tokens.py` | palette values, WCAG contrast matrix, CSS hygiene |
| `test_markup.py` | asset paths, image dimensions, links, metadata, content rules |
| `test_asset_pipeline.py` | colour maths, mask behaviour, generated-asset geometry |
| `validate.test.mjs` | intake validation, header injection, email body assembly |
| `photon.test.mjs` | type-ahead URL building, label formatting, dedup |
| `reelvideo.test.mjs` | reel source expansion, the local-only rule, autoplay gating |

Two conventions worth keeping:

- **Content rules are executable.** "Never name the employer" and "no invented clients"
  are tests, not comments, because they are liability constraints rather than style.
- **When you add an asset, section, or outbound link, extend the invariant rather than
  the fixture list.** The tests walk the DOM and `PANELS`, so new items are covered
  automatically — that only holds if you keep assertions general.
- **Never normalise inside a comparison the test exists to police.** The support-option
  drift test folded the curly apostrophe onto a straight one before comparing, so it
  passed while every enquiry choosing the first option was refused. Compare raw; put any
  tolerance in the code under test, where it is visible.

Several tests encode a bug that already shipped once (declared image dimensions
disagreeing with the file, the private `/edit` form URL, HSV blending fringing hair
green). Treat a failure as a real regression before assuming the test is stale.

### The intake form

The only server-side code. `functions/api/intake.js` is a Cloudflare Pages Function that
validates a submission, emails Kay via Resend, and sends the enquirer a confirmation.
**Nothing is persisted** — it is a delivery pipe, not a CRM.

- `functions/api/_lib/validate.js` is deliberately free of Workers APIs so it can be
  unit-tested under plain node. Keep it that way.
- `_routes.json` restricts Function invocation to `/api/intake` alone, so every other
  path is served statically and the helper module is unreachable.
- Secrets (`RESEND_API_KEY`, `INTAKE_TO`, `INTAKE_FROM`, optional `TURNSTILE_SECRET`)
  are Pages secrets in production and `.dev.vars` locally — see `.dev.vars.example`.
  With none set, the Function returns a 503 telling the visitor to email instead, so
  local development runs without credentials. **Leave it that way.** The 503 is not a
  gap to be filled in — it is what stops a local test mailing Kay's real inbox. Never
  put `RESEND_API_KEY` in `.dev.vars`, and never offer to; the key in `.planning/` is
  for production, and a form that validates but does not deliver is the correct local
  state. **Secrets only reach a new
  deployment** — redeploy after changing one, or the running version keeps the old value.
- **Turnstile is a managed widget in `interaction-only` mode.** It renders at zero
  height for an ordinary visitor and only becomes a checkbox when Cloudflare's risk
  signals ask for one — anything that makes it show for everyone is a regression, and a
  test pins the mode. Cloudflare's development sitekeys always pass, so a test also
  fails if one is left in the markup.
- **The form requires JavaScript.** A post without a Turnstile token is refused and
  lands on `/thank-you/?error=verify`.
- Resend's API key is send-only, so it cannot list domains or read logs — a failed
  `api.resend.com/domains` call means the key is scoped correctly, not broken.
- **The form is still a real `<form>` that POSTs and redirects** to `/thank-you/`;
  `main.js` only intercepts to avoid the reload. A delivery failure redirects to
  `/thank-you/?error=1`, which must never thank someone whose enquiry did not arrive.
  Turnstile tokens are single-use, so the fetch path resets the widget on any failure —
  without that, a second attempt after a validation error posts a spent token.
- Bots that trip the honeypot get the same response shape as success and nothing is
  sent, so they learn nothing.
- The `<option>` list and `SUPPORT_LEVELS` in the validator must stay identical — a
  drift silently rejects real submissions, and a test enforces it.

Local dev with the Function needs wrangler rather than `http.server` — see Commands.
Point it at `dist/`, not the repo root: `_routes.json` only exists there, so serving `.`
runs Functions on every path and re-exposes `tools/`, `tests/`, and `assets/src/`.

### City type-ahead

`lib/photon.js` holds the pure logic (URL building, label formatting, dedup) so it is
testable under node; `main.js` owns the DOM and ARIA. Results are biased toward Austin,
so "aus" surfaces Austin, Texas ahead of Aus, Namibia — a bias, not a filter.

- Photon is a free community service with no key. Keep requests debounced (280 ms),
  cached per query, aborted on each keystroke, and gated behind a two-character minimum.
- **Nominatim is not an alternative** — its usage policy forbids autocomplete outright.
- The field is optional and must never block submission: every failure path, including a
  dead API, silently closes the list and leaves an ordinary text input.
- Native `autocomplete="address-level2"` stays in the markup and JS switches it to `off`
  only after upgrading the field, so a no-JS visitor still gets browser address autofill
  and nobody ever sees two dropdowns at once.

**`<p>` accepts phrasing content only.** The listbox is a `<ul>`, so the field wrappers
are `<div>`, not `<p>` — authoring it inside a paragraph makes every browser close the
paragraph early, which moves the listbox out of its positioned wrapper and drops it at
the foot of the page. A test enforces this across all three pages.

### Placeholder vs. real imagery

The hero, the four 9:16 reel frames, and the divider band are **brand-tinted marble, not
photographs of venues**. They are deliberate placeholders. Every slot is a real `<picture>`
element at a fixed aspect ratio, so real work drops in as a file swap with no layout
change. Do not describe them to the user as finished art direction.

### The reel slots upgrade to video

`lib/reelvideo.js` holds the pure logic, `setupReelVideo` in `main.js` owns the DOM —
the same split as the type-ahead. A slot stays a still until its `<figure class="reel">`
carries `data-src="assets/video/reel-N"`: **the stem, no extension**, since `sourcesFor()`
appends `.webm` and `.mp4`. No slot is activated yet (see the issues).

- The `<picture>` is never replaced. It keeps carrying the layout and serves as the
  poster, so there is no shift when the first frame paints and a clip that fails to load
  leaves the still standing. Never trade a slot's `<img>` for a bare `<video>`.
- **Stems are local-only, enforced in `sourcesFor()`.** The subresource tests pin
  `<link>`, `<script>`, `<img>` and the hosts named in JS and CSS; none of them walks a
  `<video>`, so that guard has nowhere else to live.
- Plays at a quarter on screen, tested against `intersectionRatio` rather than
  `isIntersecting`. A 9:16 reel is most of the viewport's height on both phone and
  desktop, so a half is unreachable for much of the scroll — and `isIntersecting` alone
  is true at one visible pixel.
- A per-reel pause control is required, not decorative: WCAG 2.2.2 covers anything moving
  past five seconds. An explicit pause outranks the observer and survives scrolling away.
- `preload="none"` until playback is actually wanted, so a reduced-motion or data-saver
  visitor fetches no video bytes at all.
- `tools/build_site.py` fails the build if neither variant of a stem exists.

### Conversion surfaces

- **The sticky CTA is not decoration.** Below 900px the header's "Start a project" button
  is inside the collapsed drawer, so between the hero and the form a phone has no call to
  action at all. It rises once the hero leaves, stands down at the form and while the
  drawer is open, and is `display: none` above the breakpoint where the nav button is
  already visible.
- **The audit section has to stay on the sand ground.** Its stars knock the hairline out
  with a solid `--sand` swatch — the same trick `.step` uses — and show as rectangles
  sitting on the rule against anything else.
- **CTAs that pre-select a support level key off `data-key`, never the option text.**
  That text has to match `SUPPORT_LEVELS` character for character, so nothing else may
  hold a second copy of it.

## Things that will bite you

**Turnstile cannot be exercised through browser automation.** Chrome under CDP is exactly
what it flags: the widget appears (proving it renders) and then refuses every scripted
click, so the happy path is unreachable that way. Use the dummy keys in
`.dev.vars.example` locally, or the preview deployment — it has `TURNSTILE_SECRET` but no
Resend key, so a real submission stopping at the 503 "not configured yet" proves the token
verified. A human in an ordinary browser sees no widget at all.

**`--gold-text` vs `--gold-deep`.** Kay's brand deep gold (`#AB7937`) is 3.1:1 on cream —
correct for rules, borders, and large display type, but **below WCAG AA for small text**.
`--gold-text` (`#89602A`) is the same hue darkened until it passes on both cream and sand.
Use `--gold-text` for anything under 24px. Neither passes on the blush CTA band, which is
why the closing email link keeps `--ink` and only moves its underline on hover.

**The `js` class gates the landing page's content.** An inline script in `<head>` of
`index.html` — the only page with `.reveal` elements — adds `.js` to `<html>`, and only
`.js .reveal` is hidden. Without it the reveal animations would leave the whole page
invisible when JS fails. Do not move the hidden state onto bare `.reveal`.

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

**The `noindex` and canonical are hostname-scoped.** Preview deployments carry
`noindex, nofollow`; both the tag and the canonical resolve to the live values whenever
the hostname is `kayspectivemedia.com`.

## Operations

- Cloudflare account is **kayspectivemedia@gmail.com** (`601c9bd446100addb50b674d9740600c`),
  Pages project `kayspective-media`. `wrangler whoami` confirms which account a session
  is authenticated as — worth checking, since the OAuth flow silently uses whichever
  Cloudflare account the default browser is already signed into.
- **Wrangler's OAuth has no DNS scope at all** (`zone:read` is the only zone permission
  it offers). DNS changes need either the dashboard or an API token with
  `Zone → DNS → Edit`. Do not waste time trying to re-scope a wrangler login.
- DNS: apex and `www` are proxied CNAMEs to `kayspective-media.pages.dev`. Resend sends
  from the domain via DKIM/SPF/MX on `send`, all DNS-only (grey cloud).
- The Resend key lives in `.planning/resend-api-key`, which is gitignored and **not in
  the repo** — a fresh clone will not have it. Retrieve it from Resend or the user.
- **Pages secrets are per-environment.** `wrangler pages secret put` targets production;
  preview needs `--env preview` set separately, and `secret list --env preview` shows what
  it actually has (currently `TURNSTILE_SECRET` only).
- Wrangler's OAuth token carries `challenge-widgets.write`, so Turnstile widgets can be
  created straight from the API (`POST /accounts/{id}/challenges/widgets`) — no dashboard.
- A deploy uploads `dist/`, not the repo root, so `tools/`, `tests/`, and `assets/src/`
  are not publicly reachable. `tools/build_site.py` is an allowlist — a new asset
  has to be named there or the build fails on the reference check.
- **The Pages project is Direct Upload**, so CI deploys with wrangler rather than
  Cloudflare's GitHub integration. It authenticates with `CLOUDFLARE_API_TOKEN`
  (`Account -> Cloudflare Pages -> Edit`) and `CLOUDFLARE_ACCOUNT_ID`, both GitHub
  repository secrets. Runtime secrets stay Pages-side.

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

- Lighthouse — 100 across accessibility, best practices, and SEO **on the live domain**.
  **SEO reads 69 off-production**: the hostname guard applies `noindex` anywhere but
  `kayspectivemedia.com`, failing `is-crawlable`. Locally, only accessibility and best
  practices can regress.
- Contrast: every text/background pair at 4.5:1 (3:1 for large type), audited against the
  *rendered* colors rather than assumed from tokens
- Zero external requests, zero console errors, no horizontal scroll
- Renders fully with the `js` class removed, and under `prefers-reduced-motion`

Run `python3 -m unittest discover -s tests` first — it catches broken asset paths, wrong
declared image dimensions, contrast regressions, and content-rule violations in half a
second, without launching anything.
