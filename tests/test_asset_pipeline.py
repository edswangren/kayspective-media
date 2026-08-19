"""Colour maths behind the generated imagery.

The HSV conversions are hand-rolled (numpy-vectorised, no colorsys), and the
portrait recolour depends on them being exactly right -- a subtle error here
silently distorts Kay's skin tone rather than throwing. The mask tests pin the
two properties that make the recolour safe: border connectivity, and RGB
compositing.
"""
import os
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_assets as ba  # noqa: E402


def solid(rgb, size=(200, 200)):
    return Image.new("RGB", size, rgb)


def synthetic_portrait():
    """Rose sweep, a dark central subject, and an isolated rose island inside it.

    The island is the crux: it matches the backdrop by colour but is cut off from
    the frame edge, exactly like a lit highlight on skin. Colour thresholds alone
    would recolour it; border connectivity must not.
    """
    im = solid((198, 128, 128))          # backdrop: rose, val .78, sat .35
    px = im.load()
    for x in range(60, 140):             # subject
        for y in range(60, 140):
            px[x, y] = (10, 10, 10)
    for x in range(90, 110):             # island of backdrop colour inside subject
        for y in range(90, 110):
            px[x, y] = (198, 128, 128)
    return im


class TestHsvConversion(unittest.TestCase):
    def test_roundtrip_is_lossless(self):
        rng = np.random.default_rng(0)
        a = rng.random((64, 64, 3)).astype(np.float32)
        back = ba.hsv_to_rgb(ba.rgb_to_hsv(a))
        np.testing.assert_allclose(back, a, atol=1e-5)

    def test_known_hues(self):
        cases = {
            (1.0, 0.0, 0.0): (0.0, 1.0, 1.0),        # red
            (0.0, 1.0, 0.0): (1 / 3, 1.0, 1.0),      # green
            (0.0, 0.0, 1.0): (2 / 3, 1.0, 1.0),      # blue
            (0.5, 0.5, 0.5): (0.0, 0.0, 0.5),        # grey: hue undefined, sat 0
        }
        for rgb, expected in cases.items():
            with self.subTest(rgb=rgb):
                got = ba.rgb_to_hsv(np.array([[rgb]], dtype=np.float32))[0, 0]
                np.testing.assert_allclose(got, expected, atol=1e-5)

    def test_greyscale_has_zero_saturation(self):
        grey = np.linspace(0, 1, 32, dtype=np.float32).reshape(-1, 1, 1).repeat(3, axis=2)
        self.assertTrue(np.all(ba.rgb_to_hsv(grey)[..., 1] == 0))


class TestDuotone(unittest.TestCase):
    def test_maps_luminance_endpoints_onto_the_colour_ramp(self):
        lum = np.array([[0.0, 1.0]], dtype=np.float32)
        out = ba.duotone(lum, (10, 20, 30), (200, 210, 220))
        np.testing.assert_allclose(out[0, 0], (10, 20, 30))
        np.testing.assert_allclose(out[0, 1], (200, 210, 220))

    def test_midpoint_is_the_average(self):
        out = ba.duotone(np.array([[0.5]], dtype=np.float32), (0, 0, 0), (100, 200, 255))
        np.testing.assert_allclose(out[0, 0], (50, 100, 127.5))


class TestBackdropMask(unittest.TestCase):
    def setUp(self):
        self.im = synthetic_portrait()
        self.mask = ba.backdrop_mask(self.im)

    def test_backdrop_is_selected(self):
        self.assertGreater(self.mask[5, 5], 0.9)

    def test_subject_is_excluded(self):
        self.assertLess(self.mask[70, 70], 0.1)

    def test_isolated_island_of_backdrop_colour_is_not_selected(self):
        """Border connectivity is what protects lit skin from being recoloured."""
        self.assertLess(self.mask[100, 100], 0.1)

    def test_mask_is_feathered_not_binary(self):
        edge = self.mask[(self.mask > 0.05) & (self.mask < 0.95)]
        self.assertGreater(edge.size, 0, "hard-edged mask would cut a halo around hair")

    def test_mask_is_normalised(self):
        self.assertGreaterEqual(self.mask.min(), 0.0)
        self.assertLessEqual(self.mask.max(), 1.0)


class TestRecolourBackdrop(unittest.TestCase):
    def setUp(self):
        self.im = synthetic_portrait()
        self.out = ba.recolour_backdrop(self.im, ba.backdrop_mask(self.im))
        self.arr = np.asarray(self.out, dtype=np.float32) / 255.0
        self.hsv = ba.rgb_to_hsv(self.arr)

    def test_output_shape_and_type_are_preserved(self):
        self.assertEqual(self.out.size, self.im.size)
        self.assertEqual(self.out.mode, "RGB")

    def test_no_green_or_cyan_fringing(self):
        """Regression guard: blending in HSV sends edge hues the long way round the
        wheel and fringes hair green. Compositing must happen in RGB."""
        h, s, v = self.hsv[..., 0] * 360, self.hsv[..., 1], self.hsv[..., 2]
        meaningful = (s > 0.15) & (v > 0.15)
        offending = meaningful & (h > 90) & (h < 270)
        self.assertEqual(int(offending.sum()), 0,
                         f"{int(offending.sum())} px fringed green/cyan")

    def test_backdrop_lands_in_the_brand_blush_family(self):
        h = self.hsv[..., 0][5, 5] * 360
        self.assertAlmostEqual(h, 21.2, delta=3.0)

    def test_subject_pixels_are_untouched(self):
        src = np.asarray(self.im, dtype=np.int16)
        out = np.asarray(self.out, dtype=np.int16)
        np.testing.assert_array_equal(out[70, 70], src[70, 70])

    def test_backdrop_retains_variation_rather_than_flattening(self):
        """Value is remapped, not flattened, so the studio vignette survives."""
        self.assertGreaterEqual(self.hsv[..., 2].max(), 0.80)


class TestCircularMark(unittest.TestCase):
    def setUp(self):
        self.mark = ba.circular_mark(solid((200, 100, 50), (64, 64)), 64)

    def test_has_alpha(self):
        self.assertEqual(self.mark.mode, "RGBA")

    def test_corners_are_transparent_and_centre_is_opaque(self):
        alpha = self.mark.getchannel("A")
        self.assertEqual(alpha.getpixel((32, 32)), 255)
        for corner in ((0, 0), (63, 0), (0, 63), (63, 63)):
            with self.subTest(corner=corner):
                self.assertEqual(alpha.getpixel(corner), 0)

    def test_requested_size_is_honoured(self):
        self.assertEqual(ba.circular_mark(solid((0, 0, 0), (10, 10)), 96).size, (96, 96))


class TestPanelGeometry(unittest.TestCase):
    def test_reels_are_vertical_video_aspect(self):
        for name, _, size, *_ in ba.PANELS:
            if name.startswith("reel-"):
                with self.subTest(name=name):
                    self.assertAlmostEqual(size[0] / size[1], 9 / 16, places=3)

    def test_crop_boxes_stay_inside_the_1500px_source(self):
        for name, box, *_ in ba.PANELS:
            with self.subTest(name=name):
                x0, y0, x1, y1 = box
                self.assertGreaterEqual(min(x0, y0), 0)
                self.assertLessEqual(max(x1, y1), 1500)
                self.assertLess(x0, x1)
                self.assertLess(y0, y1)

    def test_crop_aspect_matches_output_aspect(self):
        """Any mismatch stretches the panel instead of cropping it."""
        for name, box, size, *_ in ba.PANELS:
            with self.subTest(name=name):
                crop_ar = (box[2] - box[0]) / (box[3] - box[1])
                self.assertAlmostEqual(crop_ar, size[0] / size[1], delta=0.01)


class TestGeneratedOutputs(unittest.TestCase):
    """The committed assets must match what the pipeline declares it produces."""

    def test_every_panel_has_a_full_and_half_variant_on_disk(self):
        for name, _, size, *_ in ba.PANELS:
            for suffix, expected in ((".webp", size), ("@half.webp", (size[0] // 2, size[1] // 2))):
                path = os.path.join(ba.IMG, f"{name}{suffix}")
                with self.subTest(path=os.path.basename(path)):
                    self.assertTrue(os.path.isfile(path))
                    with Image.open(path) as im:
                        self.assertEqual(im.size, expected)

    def test_og_card_is_the_required_share_size(self):
        with Image.open(os.path.join(ba.ASSETS, "og.jpg")) as im:
            self.assertEqual(im.size, (1200, 630))

    def test_portrait_is_four_by_five(self):
        with Image.open(os.path.join(ba.IMG, "portrait.webp")) as im:
            self.assertAlmostEqual(im.width / im.height, 4 / 5, places=3)


if __name__ == "__main__":
    unittest.main()
