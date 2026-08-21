/**
 * Selected-work reel video.
 *
 * The four reel slots ship as still <picture> posters. A slot upgrades to video
 * only when its <figure> carries data-src, so the markup stays correct — and
 * the page stays still — until real footage exists. Activating one is a file
 * drop into assets/video/ plus one attribute; no layout changes either way.
 *
 * Paths are local-only by contract. The subresource tests pin <link>, <script>,
 * <img> and the hosts named in JS and CSS, but nothing walks a <video>, so the
 * guard against quietly acquiring a third party lives here instead.
 *
 * Pure functions only, so they can be unit-tested without a browser.
 */

/* Offered in preference order — a browser takes the first type it can play, and
   webm is materially smaller than mp4 at the quality these clips need. */
export const VIDEO_TYPES = [
  { ext: "webm", mime: "video/webm" },
  { ext: "mp4", mime: "video/mp4" },
];

const ABSOLUTE = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;

/**
 * Expand a stem ("assets/video/reel-1") into <source> descriptors.
 * Returns [] for anything unusable, so a bad attribute leaves the still poster
 * in place rather than producing a broken player.
 */
export function sourcesFor(stem) {
  if (typeof stem !== "string") return [];
  const path = stem.trim();
  if (!path) return [];
  if (ABSOLUTE.test(path)) return [];          // never load video off-origin
  if (path.includes("..")) return [];
  if (/\.[a-z0-9]{2,4}$/i.test(path)) return [];  // stem only — we add the extension
  return VIDEO_TYPES.map((t) => ({ src: path + "." + t.ext, type: t.mime }));
}

/**
 * Whether a clip may start on its own. Reduced-motion users get a still with a
 * play control; so does anyone who has asked their browser to save data, which
 * is worth honouring for an audience arriving on phones from Instagram.
 */
export function shouldAutoplay(env) {
  const e = env || {};
  return !e.reduced && !e.saveData;
}

/** Accessible name for a reel's playback control. */
export function controlLabel(playing, caption) {
  const verb = playing ? "Pause" : "Play";
  const subject = (caption || "").trim();
  return subject ? verb + " the " + subject + " clip" : verb + " this clip";
}
