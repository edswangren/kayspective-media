# Kayspective Media — landing page

Static one-page site for Kayspective Media, a social content studio for luxury
hospitality (spas, restaurants, hotels) founded by Kaylin "Kay" Mee in Austin, TX.

**Tagline:** *Content with perspective*

**Live:** <https://kayspectivemedia.com> — Cloudflare Pages, project `kayspective-media`.

No framework, no runtime dependencies, and no compile step — the deploy build only
copies the shippable files into `dist/`. Three files do the work:
`index.html`, `styles.css`, `main.js`, plus one Pages Function for the contact form.

Non-production hostnames (localhost, `*.pages.dev`) serve a `noindex, nofollow` tag and
a canonical pointing at the real domain, scoped by hostname. Both switch themselves off
on `kayspectivemedia.com`, so previews can never compete with it in search and there is
nothing to remember to undo.

---

## Running it locally

```sh
python3 -m http.server 8747
# → http://localhost:8747
```

That's the whole dev loop. Edit a file, refresh.

## Tests

```sh
python3 -m unittest discover -s tests   # markup, tokens, asset pipeline
node --test tests/*.test.mjs            # intake form validation
```

(`node --test tests/` does not work — node reads a bare directory as a module path.)

No dependencies to install, under a second. 106 checks covering the colour maths behind
the generated imagery, the geometry of every produced asset, intake-form validation, and
markup invariants — local asset paths resolve, declared image dimensions match the files,
external links carry `rel="noopener"`, the intake link is the public form rather than the
private editor, WCAG AA contrast holds for every token pair, and the content rules below
are not violated.

They deliberately stop where a renderer is required; layout and Lighthouse are covered by
the browser pass.

## Deploying

Push to `main`. `.github/workflows/deploy.yml` runs both test suites, builds `dist/`,
and publishes it to Cloudflare Pages; a pull request deploys to its own preview URL
instead. By hand, when you need it:

```sh
python3 tools/build_site.py                                            # -> dist/
npx wrangler pages deploy dist --project-name kayspective-media --branch main
```

`tools/build_site.py` copies out the shippable subset — about 1 MB of the repo's 13 —
leaving behind `tools/`, `tests/`, and the source imagery in `assets/src/`. It is an
allowlist, so a file added to the repo is not published until it is named there, and
the build fails if a page references something the allowlist did not copy.

`functions/` stays at the repo root rather than moving into `dist/`: Cloudflare
requires it outside the static output directory, and wrangler picks it up from the
working directory. `_headers` sets long-lived caching for `/assets/*` plus basic
security headers; `_routes.json` confines Functions to `/api/intake` so every other
path is served as a static asset.

The Pages project is a **Direct Upload** project. Cloudflare cannot convert one to a
Git-connected project, which is why deploys go through wrangler in CI rather than
Cloudflare's own GitHub integration; switching would mean a new project, moving the
custom domain, and re-adding every secret.

DNS lives in the same Cloudflare account: `kayspectivemedia.com` and `www` are both
CNAMEs to `kayspective-media.pages.dev`, proxied.

### Secrets

The contact form needs three, set as Pages secrets (never committed):

```sh
printf '%s' "<resend-api-key>" | npx wrangler pages secret put RESEND_API_KEY --project-name kayspective-media
printf '%s' "kayspectivemedia@gmail.com" | npx wrangler pages secret put INTAKE_TO --project-name kayspective-media
printf '%s' "Kayspective Media <hello@kayspectivemedia.com>" | npx wrangler pages secret put INTAKE_FROM --project-name kayspective-media
```

`TURNSTILE_SECRET` is the fourth, set the same way. **Secrets only reach a new
deployment**, so redeploy after changing one.

CI needs two GitHub repository secrets of its own: `CLOUDFLARE_API_TOKEN` (scoped to
`Account -> Cloudflare Pages -> Edit`) and `CLOUDFLARE_ACCOUNT_ID`. The runtime
secrets above are deliberately *not* duplicated there.

Resend sends from `kayspectivemedia.com` (verified via DKIM/SPF/MX on `send`). Enquiries
land in `kayspectivemedia@gmail.com` with reply-to set to the enquirer, and the enquirer
gets a confirmation from `hello@`.

---

## Design

The logo is cream, gold foil, and blush marble. Rendering the *page* in those same
proportions reads bridal rather than luxury, so the emphasis is inverted: a quiet
cream ground, near-black serif type, and gold restricted to hairlines, small-caps
eyebrows, and rules. Nothing is allowed to out-saturate the logo. Blush appears
exactly once, as the closing CTA wash.

**Type:** Cormorant Garamond (display) + Jost (UI). Both self-hosted variable fonts —
one 37 KB and one 26 KB file covering weights 300–500. Two third parties are called,
both deliberate: Cloudflare Turnstile for the form's bot check, and Photon for the city
type-ahead, which only fires once someone types into that field.

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
| About | **Still needs Kay's sign-off — the site is live.** Written from her real background; her current employer is deliberately not named. Whether to keep Austin, the sales-to-content story, etc. is her call. |
| Contact form | Headline, sub, field labels, button, the "goes straight to Kay" note |

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

On the live domain, and locally at 390 / 768 / 1440:

- Lighthouse **100 / 100 / 100** on `kayspectivemedia.com` — accessibility, best
  practices, SEO. (SEO reads 69 off-production; that is the `noindex` guard working.)
- Every text/background pair meets WCAG AA (4.5:1 body, 3:1 large) — audited against
  rendered colours, not assumed from tokens
- Zero external requests on page load; zero console errors
- All tab stops have a visible focus ring; skip link first
- Full content renders **without JavaScript** and under `prefers-reduced-motion`.
  The *form* is the exception since Turnstile went in: a visitor with JS off cannot
  produce a bot-check token, so they get the email address instead of a submission
  they think worked
- Contact form delivers end to end: a real submission reached the inbox from
  `hello@kayspectivemedia.com`, with reply-to set to the enquirer
- Form degrades correctly: validation errors inline, honeypot silently accepted,
  delivery failure redirects to `/thank-you/?error=1` rather than claiming success,
  and a missing bot-check token to `?error=verify`, which names JavaScript as the
  likely cause rather than blaming the send
- Turnstile stays invisible for an ordinary visitor (widget renders at zero height)
  and appears as a single checkbox above the button when a challenge is forced
- City type-ahead returns Austin first, and falls back to plain text if Photon is
  unreachable

### Where credentials live, and why

Deploys run in GitHub Actions; the table below is what each credential is for and
why it lives where it does.

| Credential | Lives in | Why there |
|---|---|---|
| `RESEND_API_KEY` | Cloudflare Pages secret | The Function reads it at request time. Nothing else needs it. |
| `INTAKE_TO`, `INTAKE_FROM` | Cloudflare Pages secrets | Same — runtime config. |
| `TURNSTILE_SECRET` | Cloudflare Pages secret | Same — the Function verifies the token at request time. |
| `CLOUDFLARE_API_TOKEN` | GitHub repository secret | CI needs it to deploy, and nothing else does. Scoped to Pages Edit only. |
| Cloudflare credentials | `wrangler login` on the operator's machine | Only needed for a manual deploy. |

`.planning/resend-api-key` is a local convenience copy, gitignored and not in the repo.
The Pages secret is the authoritative store; deleting the local file breaks nothing.

**Why the Resend key is not a GitHub secret.** Runtime credentials belong in the
Pages environment. Putting them in GitHub as well would mean two copies to rotate and
one more place to leak from, for no benefit — the Action never sends email, it only
uploads files.

## Known follow-ups

- **About copy needs Kay's approval.** It is live and drafted from her real background.
