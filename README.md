# Kayspective Media — landing page

Static one-page site for Kayspective Media, a social content studio for luxury
hospitality (spas, restaurants, hotels) founded by Kaylin "Kay" Mee in Austin, TX.

**Tagline:** *Content with perspective*

**Review preview:** <https://edswangren.github.io/kayspective-media/>
Served from `main` by GitHub Pages, and rebuilt on every push. It carries a
`noindex, nofollow` tag and a canonical pointing at `kayspectivemedia.com`, both
scoped by hostname — so the preview can never compete with the real domain in
search, and both switch themselves off automatically once the site is served from
the production domain. Nothing to remember to undo at launch.

No framework, no build step, no dependencies at runtime. Three files do the work:
`index.html`, `styles.css`, `main.js`. Everything else is an asset.

---

## Running it locally

```sh
python3 -m http.server 8747
# → http://localhost:8747
```

That's the whole dev loop. Edit a file, refresh.

## Deploying (not done yet)

Cloudflare Pages, when you're ready:

1. Connect this repo.
2. **Build command:** *(leave empty)* · **Output directory:** `/`
3. Attach `kayspectivemedia.com` in the Pages project.

Since the domain is registered in the same Cloudflare account, DNS is one click —
no nameserver changes. Canonical URLs, OG tags, and `sitemap.xml` already point at
`https://kayspectivemedia.com/`, so nothing needs editing at deploy time.
`_headers` sets long-lived caching for `/assets/*` and basic security headers.

---

## Design

The logo is cream, gold foil, and blush marble. Rendering the *page* in those same
proportions reads bridal rather than luxury, so the emphasis is inverted: a quiet
cream ground, near-black serif type, and gold restricted to hairlines, small-caps
eyebrows, and rules. Nothing is allowed to out-saturate the logo. Blush appears
exactly once, as the closing CTA wash.

**Type:** Cormorant Garamond (display) + Jost (UI). Both self-hosted variable fonts —
one 37 KB and one 26 KB file covering weights 300–500. The page makes **zero external
network requests**.

**Palette** — Kay's four brand colors, plus derived neutrals her palette doesn't specify:

| Token | Value | Role |
|---|---|---|
| `--cream` | `#F8EEE4` | brand · page ground |
| `--blush` | `#F3D2C0` | brand · CTA wash |
| `--gold` | `#C19359` | brand · hairlines, rules |
| `--gold-deep` | `#AB7937` | brand · large display accents |
| `--gold-text` | `#89602A` | derived · small gold text |
| `--cream-lift` `--sand` `--blush-deep` | | derived surfaces |
| `--ink` `--ink-soft` | `#2B231C` `#62533F` | derived · body text |

> `--gold-text` exists because Kay's deep gold is 3.1:1 on cream — correct for rules
> and large type, but below the 4.5:1 that small text needs. It's the same hue taken
> down in value until it passes on both cream and sand.

---

## Provisional copy

Every block of body copy is placeholder text written to the right length and rhythm
for its slot — real sentences, never lorem, so the page reads finished. Each is
wrapped in `<!-- COPY: provisional -->` / `<!-- /COPY -->` in `index.html`.

Text blocks are sized by character measure — `--measure` (62ch) on the About paragraphs,
per-section `ch` values elsewhere — not by the specific words, so rewriting copy never
means touching CSS.

| Section | Notes |
|---|---|
| Hero | Eyebrow, H1 (the tagline), subcopy |
| Positioning statement | One sentence |
| Services | Three cards — Content Production / Social Management / Strategy & Direction |
| Selected work | Captions + the "newly launched" note |
| Process | Four steps |
| About | **Needs Kay's review before launch.** Written from her real background; her current employer is deliberately not named. Whether to keep Austin, the sales-to-content story, etc. is her call. |
| CTA | Headline, sub, button label |

**No invented client names or fabricated case studies** anywhere — a real liability on
a live business site. The work section says "full portfolio available on request".

---

## Assets

`tools/build_assets.py` regenerates everything derived from source images:

```sh
python3 tools/build_assets.py
```

It needs `Pillow` and `numpy`, and runs only at build time — the deployed site never
executes Python. It produces the circular logo marks, favicon, apple-touch-icon, the
1200×630 OG card, the marble texture panels, and Kay's portrait.

**Placeholders to replace with real photography:** the hero, the four 9:16 reel
frames, and the divider band are brand-tinted marble, not photographs of venues. Drop
replacements into `assets/img/` at the same filenames and aspect ratios. See
`assets/CREDITS.md` for the table, licensing, and the source of every image.

The founder portrait is a **real photograph**, cropped to 4:5 with its cool rose studio
backdrop recoloured into the brand blush (masked so her skin, hair, and jewellery are
untouched). To restore the original backdrop, delete the `recolour_backdrop(...)` call
in `build_portrait()`.

---

## Verified

Checked locally, at 390 / 768 / 1440:

- Lighthouse **100 / 100 / 100** — accessibility, best practices, SEO
- Every text/background pair meets WCAG AA (4.5:1 body, 3:1 large) — audited in-page
- Zero external network requests, zero console errors
- All 14 tab stops have a visible focus ring; skip link first
- Full content renders **without JavaScript** and under `prefers-reduced-motion`
- Intake form and Instagram links resolve 200
