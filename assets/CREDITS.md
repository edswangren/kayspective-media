# Asset credits & licensing

## Logo
`assets/logo.jpg` — Kayspective Media official logo. Property of Kayspective Media.
All derivatives (`logo.webp`, `logo-mark-*.webp`, `favicon.ico`, `apple-touch-icon.png`,
`og.jpg`) are generated from it by `tools/build_assets.py`.

## Fonts
Both self-hosted, no external requests at runtime. Variable fonts — one file covers
weights 300–500.

| File | Family | License |
|---|---|---|
| `assets/fonts/cormorant-garamond-var.woff2` | Cormorant Garamond | SIL Open Font License 1.1 |
| `assets/fonts/jost-var.woff2` | Jost | SIL Open Font License 1.1 |

## Founder portrait
`assets/src/kay-portrait-original.png` — photograph of Kaylin "Kay" Mee, supplied by
the client. Property of Kayspective Media.

`assets/img/portrait.webp` is generated from it by `tools/build_assets.py`: cropped to
4:5, and the cool rose studio sweep recoloured into the brand's blush. The recolour is
masked to the region connected to the frame edge, so her skin, hair, sweater, and
jewellery are untouched. Adjust `PORTRAIT_CROP_TOP` in the build script to change the
crop; delete `recolour_backdrop(...)` from `build_portrait()` to keep the original rose.

## Imagery
Every remaining panel in `assets/img/` is a brand-tinted derivative of a single source:

**Marble Texture** — https://commons.wikimedia.org/wiki/File:Marble_Texture.png
License: **CC0 1.0 / public domain.** No attribution required; commercial use permitted.

`tools/build_assets.py` converts it to luminance, normalizes it, and maps it onto a
two-color ramp drawn from the brand palette, producing each panel at a different crop
and tint. This is placeholder art direction, not stock photography of hospitality
venues — nothing here depicts a real client or venue.

### Replacing these with real photography
Drop a replacement into `assets/img/` at the same filename and aspect ratio:

| Slot | Aspect | Used for |
|---|---|---|
| `hero.webp` | 16:9 | Full-bleed hero background |
| `reel-1…4.webp` | 9:16 | Selected work — vertical reel stills |
| `band.webp` | 16:5 | Divider band above the closing CTA |

(`portrait.webp` is a real photograph, not a placeholder — see above.)

Also generate an `@half.webp` at half dimensions for each (the `<picture>` elements
serve it to small viewports), or delete the `srcset` line if you don't want two sizes.
