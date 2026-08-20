#!/usr/bin/env python3
"""Assemble the deployable site into dist/.

A Cloudflare Pages deploy uploads whatever directory it is pointed at, and there
is no ignore file for Pages, so pointing it at the repo root publishes the build
tooling, the test suite, and the 3.4 MB of source imagery in assets/src/ as well.
This copies out the shippable set instead.

Deliberately an allowlist: a new file added to the repo is not published until it
is named here, so a credential or working note dropped in the root cannot leak by
accident. The reference check at the end is the other half of that trade -- it
fails the build if the page asks for a local file the allowlist did not copy.

`functions/` is *not* copied. Cloudflare requires it at the project root rather
than inside the static output directory; wrangler picks it up from the working
directory when deploying, so it must stay where it is.

Usage:  python3 tools/build_site.py  [--out dist]
"""
import argparse
import os
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Everything the browser can reach. Directories are copied whole.
FILES = [
    "index.html",
    "404.html",
    "styles.css",
    "main.js",
    "robots.txt",
    "sitemap.xml",
    "_headers",       # cache and security headers, read at deploy time
    "_routes.json",   # confines Functions to /api/intake
]
DIRS = [
    "lib",
    "thank-you",
    "assets",
]
# Pruned after the directory copy. assets/src/ holds the originals the asset
# pipeline consumes -- inputs, not output.
PRUNE = ["assets/src"]

# Scanned for `href="..."`, `src="..."`, `srcset`, and `url('...')` so a missing
# copy is caught here rather than as a 404 in production.
SCANNED = ["index.html", "404.html", "thank-you/index.html", "styles.css"]
REF = re.compile(r"""(?:href|src)=["']([^"'>]+)["']|url\(['"]?([^'")]+)['"]?\)""")


def resolve(raw, base):
    """One reference, as a path relative to the output root.

    Root-absolute (`/assets/x`) and document-relative (`assets/x`) both appear in
    the markup -- 404.html uses the former so it resolves from any URL depth.
    """
    clean = raw.split("?")[0].split("#")[0]
    if clean.startswith("/"):
        return os.path.normpath(clean.lstrip("/"))
    return os.path.normpath(os.path.join(base, clean))


def local_refs(text, base):
    """Same-origin paths referenced by one document, resolved from repo root."""
    refs = set()
    for a, b in REF.findall(text):
        for raw in (a, b):
            if not raw or raw.startswith(("http", "mailto:", "tel:", "data:", "#", "//")):
                continue
            refs.add(resolve(raw, base))
    for line in re.findall(r'srcset=["\']([^"\']+)["\']', text):
        for part in line.split(","):
            url = part.strip().split()[0] if part.strip() else ""
            if url and not url.startswith(("http", "data:")):
                refs.add(resolve(url, base))
    return refs


def build(out):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in FILES:
        shutil.copy2(ROOT / name, out / name)
    for name in DIRS:
        shutil.copytree(ROOT / name, out / name)
    for name in PRUNE:
        shutil.rmtree(out / name, ignore_errors=True)

    missing = set()
    for doc in SCANNED:
        base = os.path.dirname(doc)
        for ref in local_refs((ROOT / doc).read_text(), base):
            if not (out / ref).exists():
                missing.add(f"{ref}  (referenced by {doc})")
    if missing:
        sys.exit("build_site: referenced files missing from the output:\n  " +
                 "\n  ".join(sorted(missing)))

    # Nothing that only exists to build or test the site should reach the CDN.
    stowaways = [str(p.relative_to(out)) for p in out.rglob("*")
                 if p.is_file() and (p.suffix == ".py" or p.name.startswith(".dev.vars"))]
    if stowaways:
        sys.exit("build_site: build-only files in the output:\n  " + "\n  ".join(stowaways))

    files = [p for p in out.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    print(f"{out.name}/: {len(files)} files, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    build(pathlib.Path(ROOT, ap.parse_args().out))
