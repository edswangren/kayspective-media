#!/usr/bin/env python3
"""
Build-time asset pipeline for the Kayspective Media landing page.

Runs once, offline, and writes everything into assets/. Nothing here executes at
runtime -- the deployed site is pure static HTML/CSS/JS.

Produces:
  * circular logo marks + favicon + apple-touch-icon, cropped from the master logo
  * a 1200x630 Open Graph card
  * brand-tinted marble texture panels used as the page's visual layer

The texture panels are duotone maps of a real CC0 marble photograph (see
assets/CREDITS.md) pushed into Kay's brand palette, so they read as one
deliberate art direction rather than as stock. Every panel is a drop-in
replacement target: swap the .webp for real photography at the same aspect
ratio and the layout is unchanged.
"""
import os
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
IMG    = os.path.join(ASSETS, "img")
MARBLE = "/tmp/src/marble.png"          # CC0 source, fetched by fetch_sources()

# ---- brand palette (Kay's four canonical colors + derived neutrals) ----------
CREAM       = (0xF8, 0xEE, 0xE4)
BLUSH       = (0xF3, 0xD2, 0xC0)
GOLD        = (0xC1, 0x93, 0x59)
GOLD_DEEP   = (0xAB, 0x79, 0x37)
BLUSH_DEEP  = (0xE0, 0xAC, 0x93)
CREAM_LIFT  = (0xFC, 0xF7, 0xF1)
ESPRESSO    = (0x4A, 0x38, 0x2A)
ROSE_DEEP   = (0xC9, 0x8A, 0x6E)


def fetch_sources():
    """Download the CC0 marble source if it isn't already cached."""
    if os.path.exists(MARBLE):
        return
    import urllib.request
    os.makedirs(os.path.dirname(MARBLE), exist_ok=True)
    url = ("https://upload.wikimedia.org/wikipedia/commons/0/00/Marble_Texture.png")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        open(MARBLE, "wb").write(r.read())


# ---------------------------------------------------------------- logo marks --
def circular_mark(src, size):
    """Crop the logo's circular crest and mask it to a clean circle."""
    im = src.copy().resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    im.putalpha(mask)
    return im


def build_marks(logo):
    for s in (96, 192, 384):
        circular_mark(logo, s).save(f"{ASSETS}/logo-mark-{s}.webp", quality=90, method=6)
    circular_mark(logo, 180).convert("RGB").save(f"{ASSETS}/apple-touch-icon.png")
    # multi-resolution .ico
    ico = [circular_mark(logo, s) for s in (16, 32, 48)]
    ico[0].save(f"{ASSETS}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # a compact master for the <img> in the hero/footer
    logo.resize((640, 640), Image.LANCZOS).save(f"{ASSETS}/logo.webp", quality=88, method=6)


def build_og(logo):
    """1200x630 share card: the crest on a cream field between two gold rules."""
    W, H = 1200, 630
    card = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(card)
    d.rectangle((28, 28, W - 29, H - 29), outline=GOLD, width=2)
    d.rectangle((36, 36, W - 37, H - 37), outline=GOLD + (0,), width=1)
    mark = circular_mark(logo, 470)
    card.paste(mark, ((W - 470) // 2, (H - 470) // 2), mark)
    card.save(f"{ASSETS}/og.jpg", quality=88, optimize=True)


# ------------------------------------------------------------- marble panels --
def duotone(lum, dark, light):
    """Map a 0..1 luminance plane onto a two-color brand ramp."""
    d = np.array(dark, dtype=np.float32)
    l = np.array(light, dtype=np.float32)
    return d + (l - d) * lum[..., None]


def panel(src, box, size, dark, light, contrast=1.0, grain=1.6, blur=0.0):
    """Crop a region of the marble, normalize it, and tint into brand colors."""
    im = src.crop(box).resize(size, Image.LANCZOS).convert("L")
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    lum = np.asarray(im, dtype=np.float32) / 255.0
    # normalize then apply an S-curve so veining stays readable after tinting
    lo, hi = np.percentile(lum, 2), np.percentile(lum, 98)
    lum = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1)
    lum = np.clip(0.5 + (lum - 0.5) * contrast, 0, 1)
    rgb = duotone(lum, dark, light)
    if grain:
        rng = np.random.default_rng(7)
        rgb += rng.normal(0, grain, rgb.shape)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


# Each entry: name, crop box in the 1500px source, output size, dark, light, contrast
#
# The four "reel-*" panels are 9:16 -- the native aspect of the vertical video
# this studio actually delivers. Real reel stills drop into these same slots.
PANELS = [
    # hero -- low contrast so display type stays legible over it
    ("hero",      (0,    0,    1500, 1000), (1920, 1080), BLUSH_DEEP, CREAM_LIFT, 0.62),
    # selected work -- vertical reel frames, each a distinct crop + tint so the
    # row reads as four pieces of work rather than one repeated swatch
    ("reel-1",    (150,  60,   700,  1040), (900, 1600), BLUSH_DEEP, CREAM_LIFT, 0.95),
    ("reel-2",    (760,  380,  1310, 1358), (900, 1600), GOLD_DEEP,  BLUSH,      0.88),
    ("reel-3",    (420,  480,  970,  1458), (900, 1600), GOLD,       CREAM_LIFT, 0.80),
    ("reel-4",    (900,  0,    1450, 978),  (900, 1600), ROSE_DEEP,  CREAM_LIFT, 0.98),
    # full-width divider band
    ("band",      (0,    620,  1500, 1120), (1600, 500),  GOLD,       CREAM_LIFT, 0.55),
]


def build_panels():
    src = Image.open(MARBLE).convert("RGB")
    for name, box, size, dark, light, contrast in PANELS:
        full = panel(src, box, size, dark, light, contrast)
        full.save(f"{IMG}/{name}.webp", quality=74, method=6)
        half = full.resize((size[0] // 2, size[1] // 2), Image.LANCZOS)
        half.save(f"{IMG}/{name}@half.webp", quality=72, method=6)
        print(f"  {name:12s} {size[0]}x{size[1]}")


# ─────────────────────────────────────────────────────────── founder portrait --
# Kay's headshot was shot on a cool rose sweep (hue ~4 deg) that fought the
# brand's peach blush. The sweep is recoloured into the palette while her skin,
# hair, and sweater are left exactly as shot.
PORTRAIT_SRC = os.path.join(ASSETS, "src", "kay-portrait-original.png")
PORTRAIT_CROP_TOP = 250          # headroom above her hair, in source pixels

from PIL import Image

def rgb_to_hsv(a):
    r, g, b = a[...,0], a[...,1], a[...,2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    ri, gi, bi = (mx == r) & m, (mx == g) & m, (mx == b) & m
    h[ri] = ((g - b)[ri] / d[ri]) % 6
    h[gi] = ((b - r)[gi] / d[gi]) + 2
    h[bi] = ((r - g)[bi] / d[bi]) + 4
    h = h / 6.0
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0)
    return np.stack([h, s, mx], -1)

def hsv_to_rgb(hsv):
    h, s, v = hsv[...,0]*6.0, hsv[...,1], hsv[...,2]
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v*(1-s), v*(1-s*f), v*(1-s*(1-f))
    out = np.zeros(hsv.shape, dtype=np.float32)
    for k, (R,G,B) in enumerate([(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)]):
        m = i == k
        out[...,0][m], out[...,1][m], out[...,2][m] = R[m], G[m], B[m]
    return out

def grade(im, hue_pull=0.55, sat=0.88, lift=0.055):
    """Warm the image toward the brand's peach family without recoloring skin.
    Hue rotation is weighted by how close a pixel already sits to the backdrop's
    rose, so the flat studio sweep moves most and skin/hair barely shift."""
    a = np.asarray(im, dtype=np.float32) / 255.0
    hsv = rgb_to_hsv(a)
    h, s, v = hsv[...,0], hsv[...,1], hsv[...,2]
    BG, TARGET = 4.1/360.0, 17.5/360.0
    d = np.abs(((h - BG + .5) % 1.0) - .5)
    w = np.clip(1 - d/(28/360.0), 0, 1) * np.clip(s/.28, 0, 1)
    hsv[...,0] = (h + (TARGET - BG)*w*hue_pull) % 1.0
    hsv[...,1] = np.clip(s * (1 - (1-sat)*w), 0, 1)
    hsv[...,2] = np.clip(v + lift*w*(1-v)*2.2, 0, 1)
    return Image.fromarray((np.clip(hsv_to_rgb(hsv),0,1)*255).astype(np.uint8))


def backdrop_mask(im, val_min=0.58, sat_max=0.50, hue_tol=42/360.0, bg_hue=6/360.0, feather=2.5):
    """Soft mask of the flat studio sweep.

    Colour thresholds alone would also catch lit skin, so the candidate set is
    restricted to the region that is *connected to the image border* -- the
    backdrop is by definition the thing touching the frame edge, and she is not.
    """
    a = np.asarray(im, dtype=np.float32) / 255.0
    hsv = rgb_to_hsv(a)
    h, s, v = hsv[...,0], hsv[...,1], hsv[...,2]
    dh = np.abs(((h - bg_hue + .5) % 1.0) - .5)
    cand = (v > val_min) & (s < sat_max) & (dh < hue_tol)
    # floodfill is a no-op on 'L' in this Pillow build, so mark on RGB instead
    m = Image.fromarray(np.where(cand, 255, 0).astype(np.uint8)).convert('RGB')
    W, H = m.size
    seeds = [(x, 1) for x in range(0, W, 40)] + [(x, H-2) for x in range(0, W, 40)] \
          + [(1, y) for y in range(0, H, 40)] + [(W-2, y) for y in range(0, H, 40)]
    for xy in seeds:
        if m.getpixel(xy) == (255, 255, 255):
            ImageDraw.floodfill(m, xy, (0, 255, 0), thresh=0)
    arr = np.asarray(m)
    conn = (arr[..., 1] == 255) & (arr[..., 0] == 0)
    keep = Image.fromarray(np.where(conn, 255, 0).astype(np.uint8))
    return np.asarray(keep.filter(ImageFilter.GaussianBlur(feather)), dtype=np.float32) / 255.0

def recolour_backdrop(im, mask, hue=21.2/360.0, sat=0.185, lo=0.80, hi=0.965):
    """Move the sweep into the brand's blush family, keeping its natural falloff.

    Hue and saturation are replaced outright; value is remapped into a lighter
    band rather than flattened, so the studio vignette survives and the result
    still reads as a photograph instead of a paint fill.
    """
    a = np.asarray(im, dtype=np.float32) / 255.0
    hsv = rgb_to_hsv(a)
    v = hsv[...,2]
    vb = v[mask > .5]
    p2, p98 = (np.percentile(vb, 2), np.percentile(vb, 98)) if vb.size else (0., 1.)
    vn = np.clip((v - p2) / max(p98 - p2, 1e-6), 0, 1)
    tgt = np.stack([np.full_like(v, hue),
                    np.full_like(v, sat),
                    lo + (hi - lo) * vn], -1)
    # Composite in RGB, never HSV: interpolating hue across the feathered edge
    # takes the long way round the colour wheel and fringes her hair green.
    tgt_rgb = np.clip(hsv_to_rgb(tgt), 0, 1)
    blended = a * (1 - mask[..., None]) + tgt_rgb * mask[..., None]
    return Image.fromarray((np.clip(blended, 0, 1) * 255).astype(np.uint8))


def build_portrait():
    if not os.path.exists(PORTRAIT_SRC):
        print("  (no portrait source; skipping)")
        return
    src = Image.open(PORTRAIT_SRC).convert("RGB")
    w, _ = src.size
    crop = src.crop((0, PORTRAIT_CROP_TOP, w, PORTRAIT_CROP_TOP + int(w * 5 / 4)))  # 4:5
    out = recolour_backdrop(crop, backdrop_mask(crop))
    full = out.resize((900, 1125), Image.LANCZOS)
    full.save(f"{IMG}/portrait.webp", quality=88, method=6)
    full.resize((450, 563), Image.LANCZOS).save(f"{IMG}/portrait@half.webp", quality=82, method=6)
    print("  portrait     900x1125 (backdrop recoloured)")


def main():
    os.makedirs(IMG, exist_ok=True)
    fetch_sources()
    logo = Image.open(f"{ASSETS}/logo.jpg").convert("RGB")
    print("marks + favicon…");  build_marks(logo)
    print("open graph card…");  build_og(logo)
    print("marble panels…");    build_panels()
    print("founder portrait…"); build_portrait()
    print("done.")


if __name__ == "__main__":
    main()
