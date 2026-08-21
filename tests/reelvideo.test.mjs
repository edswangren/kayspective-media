/**
 * Reel video source expansion.
 *
 * The subresource tests pin <link>, <script>, <img> and the hosts named in JS
 * and CSS, but none of them walks a <video> -- so the rule that a reel may only
 * ever load from our own origin is enforced in sourcesFor(), and pinned here.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { sourcesFor, shouldAutoplay, controlLabel, VIDEO_TYPES }
  from "../lib/reelvideo.js";

test("a stem expands to one source per offered type", () => {
  const out = sourcesFor("assets/video/reel-1");
  assert.equal(out.length, VIDEO_TYPES.length);
  assert.deepEqual(out, [
    { src: "assets/video/reel-1.webm", type: "video/webm" },
    { src: "assets/video/reel-1.mp4", type: "video/mp4" },
  ]);
});

test("webm is offered before mp4, since browsers take the first they can play", () => {
  const [first] = sourcesFor("assets/video/reel-1");
  assert.equal(first.type, "video/webm");
});

test("surrounding whitespace is tolerated", () => {
  assert.equal(sourcesFor("  assets/video/reel-2  ")[0].src,
    "assets/video/reel-2.webm");
});

test("off-origin stems are refused, whatever the scheme", () => {
  for (const bad of [
    "https://cdn.example.com/reel-1",
    "http://example.com/reel-1",
    "//example.com/reel-1",
    "data:video/mp4;base64,AAAA",
    "javascript:alert(1)",
  ]) {
    assert.deepEqual(sourcesFor(bad), [], bad);
  }
});

test("a stem carrying its own extension is refused", () => {
  // We append the extension; a stem with one would ask for reel-1.mp4.webm.
  assert.deepEqual(sourcesFor("assets/video/reel-1.mp4"), []);
});

test("traversal is refused", () => {
  assert.deepEqual(sourcesFor("../../etc/passwd"), []);
});

test("junk yields no sources, so the still poster simply stays", () => {
  for (const bad of ["", "   ", null, undefined, 42, {}]) {
    assert.deepEqual(sourcesFor(bad), []);
  }
});

test("autoplay is withheld from reduced-motion and data-saver visitors", () => {
  assert.equal(shouldAutoplay({ reduced: false, saveData: false }), true);
  assert.equal(shouldAutoplay({ reduced: true, saveData: false }), false);
  assert.equal(shouldAutoplay({ reduced: false, saveData: true }), false);
  assert.equal(shouldAutoplay({}), true);
  assert.equal(shouldAutoplay(), true);
});

test("the control names the clip it governs", () => {
  assert.equal(controlLabel(true, "Spa & Wellness"), "Pause the Spa & Wellness clip");
  assert.equal(controlLabel(false, "Spa & Wellness"), "Play the Spa & Wellness clip");
});

test("the control is still named when a caption is missing", () => {
  assert.equal(controlLabel(true, ""), "Pause this clip");
  assert.equal(controlLabel(false, undefined), "Play this clip");
});
