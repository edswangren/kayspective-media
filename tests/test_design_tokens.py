"""Design-token invariants.

The page has two golds that look nearly identical and are NOT interchangeable:
Kay's brand deep gold is correct for rules and large display type but fails WCAG
AA for small text. These tests pin that distinction down so a future edit can't
quietly swap one for the other, which is exactly the bug this palette invites.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(ROOT, "styles.css")).read()

GROUNDS = ("cream", "sand", "cream-lift")     # every surface body text sits on
AA_SMALL, AA_LARGE = 4.5, 3.0


def tokens():
    root = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S).group(1)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;", root))


def _channel(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class TestBrandColours(unittest.TestCase):
    def test_kays_four_brand_colours_are_unchanged(self):
        """These are the client's canonical values; derived tokens may move, these may not."""
        t = tokens()
        self.assertEqual(t["cream"].upper(), "#F8EEE4")
        self.assertEqual(t["blush"].upper(), "#F3D2C0")
        self.assertEqual(t["gold"].upper(), "#C19359")
        self.assertEqual(t["gold-deep"].upper(), "#AB7937")


class TestContrast(unittest.TestCase):
    def test_body_text_meets_aa_on_every_ground(self):
        t = tokens()
        for fg in ("ink", "ink-soft"):
            for bg in GROUNDS + ("blush",):
                with self.subTest(fg=fg, bg=bg):
                    self.assertGreaterEqual(contrast(t[fg], t[bg]), AA_SMALL)

    def test_gold_text_meets_aa_for_small_text(self):
        t = tokens()
        for bg in GROUNDS:
            with self.subTest(bg=bg):
                self.assertGreaterEqual(contrast(t["gold-text"], t[bg]), AA_SMALL)

    def test_brand_deep_gold_is_large_text_only(self):
        """Documents *why* --gold-text exists: deep gold clears AA large, not AA small."""
        t = tokens()
        for bg in GROUNDS:
            with self.subTest(bg=bg):
                self.assertGreaterEqual(contrast(t["gold-deep"], t[bg]), AA_LARGE)
                self.assertLess(contrast(t["gold-deep"], t[bg]), AA_SMALL)

    def test_no_gold_is_readable_on_the_blush_cta_band(self):
        """Why the closing email link keeps --ink and only moves its underline on hover."""
        t = tokens()
        for gold in ("gold", "gold-deep", "gold-text"):
            with self.subTest(gold=gold):
                self.assertLess(contrast(t[gold], t["blush"]), AA_SMALL)

    def test_focus_ring_meets_non_text_contrast(self):
        t = tokens()
        ring = re.search(r"outline:\s*2px solid var\(--([\w-]+)\)", CSS).group(1)
        for bg in GROUNDS:
            with self.subTest(bg=bg):
                self.assertGreaterEqual(contrast(t[ring], t[bg]), AA_LARGE)


class TestCssHygiene(unittest.TestCase):
    def test_every_referenced_custom_property_is_defined(self):
        defined = set(re.findall(r"--([\w-]+):", CSS))
        used = set(re.findall(r"var\(--([\w-]+)\)", CSS))
        self.assertEqual(used - defined, set())

    def test_page_does_not_auto_invert(self):
        """A print-inspired cream brand must not be flipped by the OS dark theme."""
        self.assertIn("color-scheme: light", CSS)
        self.assertNotIn("prefers-color-scheme", CSS)

    def test_reveal_hidden_state_is_gated_on_the_js_class(self):
        """Without the gate, a JS failure renders the whole page invisible."""
        self.assertIn(".js .reveal", CSS)
        self.assertFalse(re.search(r"^\.reveal\s*\{[^}]*opacity:\s*0", CSS, re.M))

    def test_reduced_motion_is_honoured(self):
        self.assertIn("prefers-reduced-motion: reduce", CSS)


if __name__ == "__main__":
    unittest.main()
