/**
 * City type-ahead against Photon (komoot's OpenStreetMap geocoder).
 *
 * Photon is free and needs no key, but it is a shared community service: keep
 * requests debounced, cached, and short. Nominatim is NOT an alternative here —
 * its usage policy forbids autocomplete outright.
 *
 * Pure functions only, so they can be unit-tested without a browser.
 */

export const ENDPOINT = "https://photon.komoot.io/api/";
export const MIN_QUERY = 2;
export const LIMIT = 6;

// Bias results toward Austin, where Kay is based, so "aus" surfaces Austin, TX
// ahead of Aus, Namibia. It is a bias, not a filter — clients elsewhere still work.
export const BIAS = { lat: 30.2672, lon: -97.7431 };

/** @returns {string|null} the request URL, or null if the query is too short. */
export function buildQueryUrl(query, { endpoint = ENDPOINT, limit = LIMIT } = {}) {
  const q = String(query || "").trim();
  if (q.length < MIN_QUERY) return null;
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    lang: "en",
    layer: "city",
    lat: String(BIAS.lat),
    lon: String(BIAS.lon),
  });
  return `${endpoint}?${params}`;
}

/** "Austin, Texas" at home; "Aus, Karas Region, Namibia" abroad. */
export function formatLabel(properties = {}) {
  const { name, state, country, countrycode } = properties;
  if (!name) return "";
  const parts = [name];
  if (state && state !== name) parts.push(state);
  if (countrycode !== "US" && country) parts.push(country);
  return parts.join(", ");
}

/**
 * Photon returns near-duplicates (a city and its suburb of the same name), and
 * the same place can appear twice at different admin levels. Collapse by label.
 * @returns {{label: string, name: string}[]}
 */
export function toSuggestions(payload, { limit = LIMIT } = {}) {
  const features = (payload && payload.features) || [];
  const seen = new Set();
  const out = [];
  for (const feature of features) {
    const properties = (feature && feature.properties) || {};
    const label = formatLabel(properties);
    if (!label) continue;
    const key = label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ label, name: properties.name });
    if (out.length >= limit) break;
  }
  return out;
}
