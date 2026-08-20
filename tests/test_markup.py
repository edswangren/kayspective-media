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

    def test_third_party_subresources_are_only_the_vetted_ones(self):
        """Every host the page loads on sight is one we chose deliberately.

        Fonts and imagery are self-hosted, so the list stays short: Turnstile is
        the only entry, and it is here because bot protection cannot be done in
        first-party code. A new host appearing is not automatically wrong -- it
        just has to be a decision rather than a drifted-in dependency.

        Outbound <a> links and metadata (canonical, og:*) are not fetched, so only
        rels the browser actually loads are in scope.
        """
        ALLOWED = {"challenges.cloudflare.com"}
        FETCHED = {"stylesheet", "preload", "icon", "apple-touch-icon", "manifest", "preconnect"}

        def host(url):
            return url.split("//", 1)[1].split("/", 1)[0]

        for a in of("link"):
            href = a.get("href", "")
            if a.get("rel") in FETCHED and href.startswith("http") and host(href) not in ALLOWED:
                self.fail(f"unvetted subresource: <link rel={a['rel']} href={href}>")
        for tag, attr in (("script", "src"), ("img", "src")):
            for a in of(tag):
                v = a.get(attr)
                if v and v.startswith("http") and host(v) not in ALLOWED:
                    self.fail(f"unvetted subresource: <{tag} {attr}={v}>")

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
    def test_long_google_intake_is_not_exposed_to_cold_traffic(self):
        """The 34-question questionnaire is an onboarding step Kay sends after first
        contact, not a landing-page CTA. Cold visitors get the short on-site form."""
        forms = [a["href"] for a in of("a") if "docs.google.com/forms" in a.get("href", "")]
        self.assertEqual(forms, [], f"Google Form linked publicly: {forms}")

    def test_any_google_form_link_would_be_the_public_url(self):
        """Guard for if one is ever re-added: /edit is the private editor and 403s."""
        for a in of("a"):
            href = a.get("href", "")
            if "docs.google.com/forms" in href:
                with self.subTest(href=href):
                    self.assertNotIn("/edit", href)
                    self.assertIn("/viewform", href)

    def test_primary_calls_to_action_point_at_the_on_site_form(self):
        labels = {"Start a project"}
        ctas = [a for a in of("a") if (a.get("class") or "").startswith("btn")]
        targeted = [a for a in ctas if a.get("href") == "#contact"]
        self.assertGreaterEqual(len(targeted), 2, "hero and header CTAs should reach #contact")

    def test_contact_details_are_present(self):
        hrefs = [a.get("href", "") for a in of("a")]
        self.assertTrue(any(h.startswith("mailto:kayspectivemedia@gmail.com") for h in hrefs))
        self.assertTrue(any("instagram.com/kayspective.media" in h for h in hrefs))

    def test_linked_profiles_and_structured_data_agree(self):
        """Every off-site profile we link is also declared in JSON-LD sameAs, and
        nothing is declared that the page does not link. Adding a social account in
        one place and forgetting the other is the failure this catches; if an
        external link is ever added that is *not* one of Kay's profiles, this test
        is the deliberate prompt to decide which set it belongs to."""
        linked = {a["href"] for a in of("a")
                  if a.get("href", "").startswith("http")}
        org = json.loads(DOC.ld_json[0])
        declared = set(org.get("sameAs", []))
        self.assertEqual(linked, declared,
                         "footer profile links and JSON-LD sameAs have drifted")

    def test_no_placeholder_or_dead_links(self):
        for a in of("a"):
            self.assertNotIn(a.get("href"), ("#", "", None), "placeholder href left in markup")


class TestBotProtection(unittest.TestCase):
    """Turnstile is a managed widget in interaction-only mode: nothing is shown to
    an ordinary visitor, and a checkbox appears only when Cloudflare's signals ask
    for one. Anything that quietly turns it into an always-on captcha, or that
    leaves a visitor with no route to Kay, is a regression."""

    # Cloudflare's documented development keys. They always pass, so shipping one
    # would leave the form protected in appearance only.
    TEST_SITEKEYS = {"1x00000000000000000000AA", "2x00000000000000000000AB",
                     "3x00000000000000000000FF"}

    def widget(self):
        found = [a for a in of("div") if "cf-turnstile" in (a.get("class") or "")]
        self.assertEqual(len(found), 1, "expected exactly one Turnstile widget")
        return found[0]

    def test_widget_never_demands_interaction_from_every_visitor(self):
        self.assertEqual(self.widget().get("data-appearance"), "interaction-only")

    def test_widget_carries_a_production_sitekey(self):
        key = self.widget().get("data-sitekey", "")
        self.assertTrue(key, "widget has no data-sitekey")
        self.assertNotIn(key, self.TEST_SITEKEYS,
                         "a Cloudflare development sitekey is in the markup: it always "
                         "passes, so the form only looks protected. Swap in the real one.")

    def test_visitors_without_javascript_are_told_how_to_reach_kay(self):
        """The widget needs JS, so those visitors cannot submit at all. Silence
        would read as a broken form; they get the email address instead."""
        block = re.search(r"<noscript>(.*?)</noscript>", HTML, re.S)
        self.assertIsNotNone(block, "no <noscript> fallback in the intake form")
        self.assertIn("mailto:kayspectivemedia@gmail.com", block.group(1))

    def test_the_honeypot_is_still_there(self):
        """Turnstile supplements the trap rather than replacing it -- the honeypot
        costs nothing and catches the bots that render JS but read the DOM."""
        hp = [a for a in of("input") if a.get("name") == "website"]
        self.assertEqual(len(hp), 1)


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

    def test_noindex_guard_matches_only_the_production_hostname(self):
        """Locally and on previews this fires, which is why Lighthouse SEO reads 69
        there. Production must be the one place it does not."""
        # extract the regex the page actually ships, not a copy of it
        m = re.search(r"/(\^[^/]+\$)/\.test\(location\.hostname\)", HTML)
        self.assertIsNotNone(m, "hostname guard not found in index.html")
        rx = re.compile(m.group(1))
        for host in ("kayspectivemedia.com", "www.kayspectivemedia.com"):
            self.assertTrue(rx.match(host), f"{host} should be indexable")
        for host in ("localhost", "edswangren.github.io",
                     "kayspective-media.pages.dev", "evil-kayspectivemedia.com"):
            self.assertFalse(rx.match(host), f"{host} must not be treated as production")

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


class TestHtmlNesting(unittest.TestCase):
    """<p> accepts phrasing content only. Authoring a block element inside one
    makes every browser silently close the paragraph, which moved the combobox
    listbox out of its positioned wrapper and dropped it at the foot of the page."""

    BLOCK = {"ul", "ol", "div", "table", "form", "section", "p", "fieldset"}
    VOID = {"img", "input", "br", "meta", "link", "source", "use", "path", "hr", "area"}

    def test_no_block_elements_inside_a_paragraph(self):
        class Stack(HTMLParser):
            def __init__(inner):
                super().__init__()
                inner.stack, inner.bad = [], []

            def handle_starttag(inner, tag, attrs):
                if tag in TestHtmlNesting.BLOCK and "p" in inner.stack:
                    inner.bad.append(f"<{tag}> inside <p> at line {inner.getpos()[0]}")
                if tag not in TestHtmlNesting.VOID:
                    inner.stack.append(tag)

            def handle_endtag(inner, tag):
                if tag in inner.stack:
                    while inner.stack and inner.stack.pop() != tag:
                        pass

        for name in ("index.html", "thank-you/index.html", "404.html"):
            with self.subTest(page=name):
                parser = Stack()
                parser.feed(pathlib.Path(ROOT, name).read_text())
                self.assertEqual(parser.bad, [])

    def test_combobox_listbox_is_inside_its_positioned_wrapper(self):
        """Without this the absolutely-positioned list has no containing block."""
        wrapper = re.search(r'<div[^>]*class="[^"]*field-combo[^"]*"[^>]*>(.*?)</div>', HTML, re.S)
        self.assertIsNotNone(wrapper, "field-combo wrapper not found")
        self.assertIn('id="city-list"', wrapper.group(1))
        css = pathlib.Path(ROOT, "styles.css").read_text()
        self.assertRegex(css, r"\.field-combo\s*\{[^}]*position:\s*relative")


class TestIntakeForm(unittest.TestCase):
    """The form is the site's only conversion path, so it must work without JS."""

    def form_controls(self):
        return [(t, a) for t, a in DOC.tags if t in ("input", "select", "textarea")]

    def test_form_posts_natively_to_the_function(self):
        form = of("form")[0]
        self.assertEqual(form.get("method", "").lower(), "post")
        self.assertEqual(form.get("action"), "/api/intake")

    def test_every_control_has_a_label(self):
        labels = {a["for"] for a in of("label") if a.get("for")}
        for tag, a in self.form_controls():
            with self.subTest(name=a.get("name")):
                self.assertIn("id", a, f"{tag} {a.get('name')} has no id")
                self.assertIn(a["id"], labels, f"no <label for> targets {a['id']}")

    def test_required_fields_are_marked_required(self):
        required = {a["name"] for _, a in self.form_controls() if "required" in a}
        self.assertEqual(required, {"business", "name", "email", "support"})

    def test_controls_have_length_caps_matching_the_server(self):
        """Client caps are UX; the server enforces the same limits independently."""
        lib = pathlib.Path(ROOT, "functions/api/_lib/validate.js").read_text()
        limits = dict(re.findall(r"(\w+):\s*(\d+),", lib.split("LIMITS = {")[1].split("}")[0]))
        for _, a in self.form_controls():
            name = a.get("name")
            if name in limits and a.get("type") != "hidden" and name != "support":
                with self.subTest(name=name):
                    self.assertEqual(a.get("maxlength"), limits[name])

    def test_support_options_match_the_server_allowlist(self):
        """A mismatch silently rejects a real submission, so they must not drift.

        Compared character for character. This test used to fold the curly
        apostrophe onto a straight one before comparing, which hid the exact drift
        it existed to catch: the markup posts `we\u2019ll` and the allowlist held
        `we'll`, so every enquiry choosing the first option was refused as "not one
        of the listed options" -- a live form rejecting real leads while every test
        passed. Normalise here and the bug comes straight back.
        """
        lib = pathlib.Path(ROOT, "functions/api/_lib/validate.js").read_text()
        block = lib.split("SUPPORT_LEVELS = [")[1].split("];")[0]
        # Only \uXXXX escapes are decoded: a blanket unicode_escape would mangle
        # the em dashes, which are literal UTF-8 in both files.
        unesc = lambda v: re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), v)
        server = [unesc(m.group(1)) for m in re.finditer(r'"([^"]+)"', block)]
        html_opts = re.findall(r"<option>(.*?)</option>", HTML, re.S)
        import html as htmllib
        rendered = [htmllib.unescape(o).strip() for o in html_opts]
        self.assertEqual(len(server), len(rendered), "option count drifted")
        for a, b in zip(server, rendered):
            with self.subTest(option=b):
                self.assertEqual(a, b)

    def test_honeypot_is_present_and_hidden_from_people(self):
        hp = [a for _, a in self.form_controls() if a.get("name") == "website"]
        self.assertEqual(len(hp), 1, "bot trap missing")
        self.assertEqual(hp[0].get("tabindex"), "-1")
        self.assertEqual(hp[0].get("autocomplete"), "off")
        css = pathlib.Path(ROOT, "styles.css").read_text()
        self.assertIn(".hp {", css)
        self.assertNotIn("website", [a.get("name") for _, a in self.form_controls()][:3])

    def test_status_region_is_announced_to_screen_readers(self):
        status = [a for a in of("p") if a.get("id") == "intake-status"][0]
        self.assertEqual(status.get("role"), "status")
        self.assertEqual(status.get("aria-live"), "polite")

    def test_thank_you_fallback_page_exists_for_no_js_visitors(self):
        page = pathlib.Path(ROOT, "thank-you/index.html")
        self.assertTrue(page.is_file())
        body = page.read_text()
        self.assertIn("noindex", body, "the confirmation page should not be indexed")
        self.assertIn("error", body, "it must handle the delivery-failure redirect")

    def test_functions_are_restricted_to_the_intake_route(self):
        routes = json.loads(pathlib.Path(ROOT, "_routes.json").read_text())
        self.assertEqual(routes["include"], ["/api/intake"])


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

    def test_photon_is_the_only_third_party_the_client_ever_calls(self):
        """The page loads with zero external requests; the city type-ahead is the
        single exception, and only once someone types. Keep it that way."""
        ALLOWED = {"photon.komoot.io"}
        client = "\n".join(
            pathlib.Path(ROOT, f).read_text() for f in ("main.js", "lib/photon.js", "styles.css")
        )
        hosts = set(re.findall(r"https?://([\w.-]+)", client))
        self.assertEqual(hosts - ALLOWED - {"www.w3.org"}, set())

    def test_no_console_statements_ship(self):
        js = pathlib.Path(ROOT, "main.js").read_text()
        self.assertNotIn("console.", js)


if __name__ == "__main__":
    unittest.main()
