"""Markup and asset integrity.

Most of these encode a bug that actually shipped during the build and was caught
by hand: a private /edit form URL, declared image dimensions that disagreed with
the file on disk, a lazy asset path that no longer existed. They are cheap enough
to run on every change; the browser pass is for things only a renderer can judge.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = pathlib.Path(ROOT, "index.html").read_text()

# Kay's current employer must never appear on the site: naming it implies
# portfolio rights and an endorsement she may not have.
EMPLOYER_TERMS = ("covert", "bee cave")


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []          # (tag, {attrs})
        self._script = None
        self.ld_json = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if tag == "script" and d.get("type") == "application/ld+json":
            self._script = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.ld_json.append("".join(self._script))
            self._script = None


def parse():
    c = Collector()
    c.feed(HTML)
    return c


DOC = parse()


def of(tag):
    return [a for t, a in DOC.tags if t == tag]


def local_refs():
    """Every same-origin subresource path referenced by the document."""
    refs = []
    for tag, attr in (("link", "href"), ("script", "src"), ("img", "src")):
        refs += [a[attr] for a in of(tag) if a.get(attr) and not a[attr].startswith(("http", "mailto:", "#", "data:"))]
    for a in of("source"):
        refs += [s.strip() for s in a.get("srcset", "").split(",") if s.strip()]
    # url(...) references inside the stylesheet, resolved relative to repo root
    css = pathlib.Path(ROOT, "styles.css").read_text()
    refs += [u for u in re.findall(r"url\('([^']+)'\)", css) if not u.startswith(("http", "data:"))]
    return refs


class TestAssetIntegrity(unittest.TestCase):
    def test_every_referenced_local_asset_exists(self):
        for ref in local_refs():
            with self.subTest(ref=ref):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, ref)), f"missing: {ref}")

    def test_no_external_subresources(self):
        """The page must make zero third-party requests.

        Outbound <a> links and metadata (canonical, og:*) are not fetched, so only
        rels the browser actually loads are in scope.
        """
        FETCHED = {"stylesheet", "preload", "icon", "apple-touch-icon", "manifest", "preconnect"}
        for a in of("link"):
            if a.get("rel") in FETCHED and a.get("href", "").startswith("http"):
                self.fail(f"external subresource: <link rel={a['rel']} href={a['href']}>")
        for tag, attr in (("script", "src"), ("img", "src")):
            for a in of(tag):
                v = a.get(attr)
                if v and v.startswith("http"):
                    self.fail(f"external subresource: <{tag} {attr}={v}>")

    def test_declared_image_dimensions_match_the_files_aspect_ratio(self):
        """Wrong ratios reintroduce layout shift even when width/height are present."""
        for a in of("img"):
            src = a.get("src")
            if not src or src.startswith(("http", "data:")):
                continue
            with self.subTest(src=src):
                self.assertIn("width", a, f"{src} has no width")
                self.assertIn("height", a, f"{src} has no height")
                declared = int(a["width"]) / int(a["height"])
                with Image.open(os.path.join(ROOT, src)) as im:
                    actual = im.width / im.height
                self.assertAlmostEqual(declared, actual, places=2,
                                       msg=f"{src}: declared {declared:.3f} vs file {actual:.3f}")

    def test_half_size_variant_exists_for_every_responsive_image(self):
        for a in of("source"):
            for cand in a.get("srcset", "").split(","):
                cand = cand.strip().split()[0]
                with self.subTest(cand=cand):
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, cand)))


class TestAccessibility(unittest.TestCase):
    def test_every_image_has_an_alt_attribute(self):
        for a in of("img"):
            self.assertIn("alt", a, f"missing alt: {a.get('src')}")

    def test_exactly_one_h1(self):
        self.assertEqual(HTML.count("<h1"), 1)

    def test_external_links_are_safe(self):
        for a in of("a"):
            if a.get("target") == "_blank":
                with self.subTest(href=a.get("href")):
                    self.assertIn("noopener", a.get("rel", ""))

    def test_skip_link_is_present_and_targets_main(self):
        skip = [a for a in of("a") if "skip-link" in a.get("class", "")]
        self.assertEqual(len(skip), 1)
        self.assertEqual(skip[0]["href"], "#main")
        self.assertTrue(any(a.get("id") == "main" for _, a in DOC.tags))

    def test_nav_toggle_exposes_expanded_state(self):
        btn = [a for a in of("button") if a.get("id") == "nav-toggle"][0]
        self.assertIn("aria-expanded", btn)
        self.assertEqual(btn.get("aria-controls"), "nav")


class TestOutboundLinks(unittest.TestCase):
    def test_intake_form_uses_the_public_published_url(self):
        """The /edit URL is the private editor and 403s for everyone but Kay."""
        forms = [a["href"] for a in of("a") if "docs.google.com/forms" in a.get("href", "")]
        self.assertTrue(forms, "intake form link is missing entirely")
        for href in forms:
            with self.subTest(href=href):
                self.assertNotIn("/edit", href)
                self.assertIn("/viewform", href)
                self.assertRegex(href, r"/forms/d/e/[\w-]+/viewform")

    def test_contact_details_are_present(self):
        hrefs = [a.get("href", "") for a in of("a")]
        self.assertTrue(any(h.startswith("mailto:kayspectivemedia@gmail.com") for h in hrefs))
        self.assertTrue(any("instagram.com/kayspective.media" in h for h in hrefs))

    def test_no_placeholder_or_dead_links(self):
        for a in of("a"):
            self.assertNotIn(a.get("href"), ("#", "", None), "placeholder href left in markup")


class TestContentRules(unittest.TestCase):
    def test_current_employer_is_never_named(self):
        lowered = HTML.lower()
        for term in EMPLOYER_TERMS:
            self.assertNotIn(term, lowered, f"employer reference leaked into markup: {term!r}")

    def test_provisional_copy_markers_are_balanced(self):
        self.assertEqual(HTML.count("<!-- COPY: provisional"), HTML.count("<!-- /COPY -->"))

    def test_no_lorem_ipsum(self):
        self.assertNotIn("lorem", HTML.lower())


class TestMetadata(unittest.TestCase):
    def test_structured_data_is_valid_and_describes_the_business(self):
        self.assertTrue(DOC.ld_json, "no JSON-LD block found")
        data = json.loads(DOC.ld_json[0])
        self.assertEqual(data["@type"], "ProfessionalService")
        self.assertEqual(data["name"], "Kayspective Media")
        self.assertEqual(data["slogan"], "Content with perspective")
        self.assertEqual(data["address"]["addressLocality"], "Austin")

    def test_canonical_and_og_point_at_the_production_domain(self):
        canonical = [a for a in of("link") if a.get("rel") == "canonical"][0]
        self.assertEqual(canonical["href"], "https://kayspectivemedia.com/")
        og = {a["property"]: a["content"] for a in of("meta") if a.get("property")}
        self.assertEqual(og["og:url"], "https://kayspectivemedia.com/")
        self.assertTrue(og["og:image"].startswith("https://kayspectivemedia.com/"))

    def test_noindex_guard_is_scoped_to_non_production_hosts(self):
        """Review previews must not be indexed, and the guard must self-disable at launch."""
        self.assertIn("kayspectivemedia\\.com$", HTML)
        self.assertIn("noindex", HTML)
        # it must be conditional, never a bare tag that would ship to production
        self.assertNotRegex(HTML, r'<meta[^>]+name="robots"[^>]+noindex')

    def test_tagline_is_the_h1(self):
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", HTML, re.S).group(1)
        self.assertIn("Content with", h1)
        self.assertIn("perspective", h1)

    def test_fonts_are_preloaded_with_crossorigin(self):
        preloads = [a for a in of("link") if a.get("rel") == "preload" and a.get("as") == "font"]
        self.assertEqual(len(preloads), 2)
        for p in preloads:
            self.assertIn("crossorigin", p)


class TestDeployment(unittest.TestCase):
    def test_nojekyll_present(self):
        """Without it GitHub Pages runs Jekyll, which strips files starting with '_'."""
        self.assertTrue(os.path.isfile(os.path.join(ROOT, ".nojekyll")))

    def test_underscore_files_that_jekyll_would_eat_are_accounted_for(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "_headers")))

    def test_sitemap_and_robots_reference_the_production_domain(self):
        sitemap = pathlib.Path(ROOT, "sitemap.xml").read_text()
        robots = pathlib.Path(ROOT, "robots.txt").read_text()
        self.assertIn("https://kayspectivemedia.com/", sitemap)
        self.assertIn("https://kayspectivemedia.com/sitemap.xml", robots)


class TestScripts(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_main_js_parses(self):
        r = subprocess.run(["node", "--check", os.path.join(ROOT, "main.js")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_reveal_sweep_is_present(self):
        """Without it, anything landing in the observer's bottom dead zone -- which is
        where the closing CTA sits -- never becomes visible."""
        js = pathlib.Path(ROOT, "main.js").read_text()
        self.assertIn("sweep", js)
        self.assertIn("addEventListener('scroll'", js)

    def test_no_console_statements_ship(self):
        js = pathlib.Path(ROOT, "main.js").read_text()
        self.assertNotIn("console.", js)


if __name__ == "__main__":
    unittest.main()
