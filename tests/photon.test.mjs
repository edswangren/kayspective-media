/**
 * Unit tests for the city type-ahead's pure logic.
 * Run with:  node --test tests/*.test.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildQueryUrl, formatLabel, toSuggestions, MIN_QUERY, LIMIT, ENDPOINT, BIAS,
} from "../lib/photon.js";

const feature = (properties) => ({ type: "Feature", properties });
const AUSTIN = { name: "Austin", state: "Texas", country: "United States", countrycode: "US" };
const AUS_NA = { name: "Aus", state: "Karas", country: "Namibia", countrycode: "NA" };

test("short queries produce no request at all", () => {
  for (const q of ["", " ", "a", null, undefined]) {
    assert.equal(buildQueryUrl(q), null, `should not query for ${JSON.stringify(q)}`);
  }
  assert.equal("ab".length, MIN_QUERY);
  assert.ok(buildQueryUrl("ab"));
});

test("the query URL carries the Austin bias and a city filter", () => {
  const url = new URL(buildQueryUrl("  austin  "));
  assert.ok(url.href.startsWith(ENDPOINT));
  assert.equal(url.searchParams.get("q"), "austin", "query should be trimmed");
  assert.equal(url.searchParams.get("layer"), "city");
  assert.equal(url.searchParams.get("limit"), String(LIMIT));
  assert.equal(url.searchParams.get("lat"), String(BIAS.lat));
  assert.equal(url.searchParams.get("lon"), String(BIAS.lon));
});

test("user input is encoded rather than injected into the query string", () => {
  const url = new URL(buildQueryUrl("a&limit=999&x=y"));
  assert.equal(url.searchParams.get("limit"), String(LIMIT));
  assert.equal(url.searchParams.get("q"), "a&limit=999&x=y");
  assert.equal(url.searchParams.get("x"), null);
});

test("US places omit the country; elsewhere includes it", () => {
  assert.equal(formatLabel(AUSTIN), "Austin, Texas");
  assert.equal(formatLabel(AUS_NA), "Aus, Karas, Namibia");
});

test("a city that is its own state is not repeated", () => {
  assert.equal(
    formatLabel({ name: "Singapore", state: "Singapore", country: "Singapore", countrycode: "SG" }),
    "Singapore, Singapore"
  );
});

test("places without a name are skipped entirely", () => {
  assert.equal(formatLabel({}), "");
  assert.deepEqual(toSuggestions({ features: [feature({ state: "Texas" })] }), []);
});

test("duplicate labels collapse to one suggestion", () => {
  const out = toSuggestions({
    features: [feature(AUSTIN), feature({ ...AUSTIN }), feature(AUS_NA)],
  });
  assert.deepEqual(out.map((s) => s.label), ["Austin, Texas", "Aus, Karas, Namibia"]);
});

test("same name in different states are kept apart", () => {
  const out = toSuggestions({
    features: [
      feature(AUSTIN),
      feature({ name: "Austin", state: "Minnesota", countrycode: "US" }),
    ],
  });
  assert.equal(out.length, 2);
});

test("deduplication is case-insensitive", () => {
  const out = toSuggestions({
    features: [feature(AUSTIN), feature({ ...AUSTIN, name: "AUSTIN", state: "TEXAS" })],
  });
  assert.equal(out.length, 1);
});

test("results are capped even when the service returns more", () => {
  const many = Array.from({ length: 40 }, (_, i) =>
    feature({ name: `City ${i}`, state: "Texas", countrycode: "US" })
  );
  assert.equal(toSuggestions({ features: many }).length, LIMIT);
});

test("malformed or empty payloads degrade to no suggestions", () => {
  for (const payload of [null, undefined, {}, { features: null }, { features: [] }, { features: [null] }]) {
    assert.deepEqual(toSuggestions(payload), [], `failed for ${JSON.stringify(payload)}`);
  }
});

test("suggestions expose the bare city name alongside the label", () => {
  const [first] = toSuggestions({ features: [feature(AUSTIN)] });
  assert.equal(first.label, "Austin, Texas");
  assert.equal(first.name, "Austin");
});
