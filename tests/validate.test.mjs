/**
 * Unit tests for the intake form's validation and email rendering.
 * Run with:  node --test tests/
 * Built-in test runner, no dependencies.
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  validate, clean, escapeHtml, renderEmail, SUPPORT_LEVELS, LIMITS,
} from "../functions/api/_lib/validate.js";

const valid = () => ({
  business: "The Cedar Spa",
  name: "Dana Reyes",
  email: "dana@cedarspa.com",
  city: "Austin",
  support: SUPPORT_LEVELS[1],
  message: "We open a second location in March.",
});

test("clean() trims and collapses whitespace", () => {
  assert.equal(clean("  The   Cedar  Spa "), "The Cedar Spa");
  assert.equal(clean(undefined), "");
  assert.equal(clean(null), "");
  assert.equal(clean(42), "");
});

test("a complete submission passes", () => {
  const r = validate(valid());
  assert.equal(r.ok, true);
  assert.deepEqual(r.errors, {});
  assert.equal(r.spam, false);
});

test("required fields are enforced", () => {
  for (const field of ["business", "name", "email", "support"]) {
    const r = validate({ ...valid(), [field]: "" });
    assert.equal(r.ok, false, `${field} should be required`);
    assert.ok(r.errors[field], `${field} should report an error`);
  }
});

test("optional fields are genuinely optional", () => {
  const r = validate({ ...valid(), city: "", message: "" });
  assert.equal(r.ok, true);
});

test("whitespace-only input does not satisfy a required field", () => {
  assert.equal(validate({ ...valid(), name: "     " }).ok, false);
});

test("plausible email addresses are accepted", () => {
  const good = [
    "dana@cedarspa.com",
    "dana.reyes@spa.co.uk",
    "dana+intake@cedar-spa.io",
    "d@x.dev",
    "DANA@CEDARSPA.COM",
  ];
  for (const email of good) {
    assert.equal(validate({ ...valid(), email }).ok, true, `rejected: ${email}`);
  }
});

test("malformed email addresses are rejected", () => {
  const bad = ["dana", "dana@", "@cedarspa.com", "dana@spa", "dana @spa.com", "a@b.c"];
  for (const email of bad) {
    assert.equal(validate({ ...valid(), email }).ok, false, `accepted: ${email}`);
  }
});

test("support level must be one of the offered options", () => {
  assert.equal(validate({ ...valid(), support: "Free work please" }).ok, false);
  for (const level of SUPPORT_LEVELS) {
    assert.equal(validate({ ...valid(), support: level }).ok, true, `rejected: ${level}`);
  }
});

test("over-long input is rejected rather than silently truncated", () => {
  const r = validate({ ...valid(), business: "x".repeat(LIMITS.business + 1) });
  assert.equal(r.ok, false);
  assert.ok(r.errors.business);
});

test("the message field is capped, and keeps its line breaks", () => {
  const r = validate({ ...valid(), message: "line one\nline two" });
  assert.equal(r.data.message, "line one\nline two");
  assert.ok(validate({ ...valid(), message: "y".repeat(LIMITS.message + 50) }).data.message.length <= LIMITS.message);
});

test("honeypot flags spam without producing a validation error", () => {
  const r = validate({ ...valid(), website: "http://spam.example" });
  assert.equal(r.spam, true);
  assert.equal(r.ok, true, "bots must not learn anything from the response shape");
});

test("an empty honeypot is not spam", () => {
  assert.equal(validate({ ...valid(), website: "   " }).spam, false);
});

test("missing payload is handled without throwing", () => {
  assert.equal(validate().ok, false);
  assert.equal(validate({}).ok, false);
});

test("escapeHtml neutralises every dangerous character", () => {
  assert.equal(escapeHtml(`<script>&"'`), "&lt;script&gt;&amp;&quot;&#39;");
});

test("submitted values cannot inject markup into Kay's email", () => {
  const { html, subject } = renderEmail(
    validate({ ...valid(), business: '<img src=x onerror=alert(1)>' }).data
  );
  assert.ok(!html.includes("<img src=x"), "raw markup reached the email body");
  assert.ok(html.includes("&lt;img"), "value should appear escaped");
  // The subject is plain text -- mail clients never render it as HTML, so
  // escaping it would be theatre. What matters there is header injection.
  assert.ok(subject.length > 0);
});

test("newlines cannot be smuggled into email headers", () => {
  const r = validate({
    ...valid(),
    business: "Cedar Spa\r\nBcc: victim@example.com",
    name: "Dana\nX-Injected: 1",
  });
  const { subject } = renderEmail(r.data);
  assert.ok(!/[\r\n]/.test(subject), "subject must be a single line");
  assert.ok(!/[\r\n]/.test(r.data.business));
  assert.ok(!/[\r\n]/.test(r.data.name));
  assert.ok(!/[\r\n]/.test(r.data.email));
});

test("the email includes every submitted field", () => {
  const data = validate(valid()).data;
  const { html, text } = renderEmail(data);
  for (const value of [data.business, data.name, data.email, data.city]) {
    assert.ok(html.includes(value), `missing from html: ${value}`);
    assert.ok(text.includes(value), `missing from text: ${value}`);
  }
});

test("empty optional fields are omitted from the email rather than left blank", () => {
  const data = validate({ ...valid(), city: "", message: "" }).data;
  const { html, text } = renderEmail(data);
  assert.ok(!html.includes("City"));
  assert.ok(!text.includes("City:"));
});

test("the subject line names the business so Kay can triage at a glance", () => {
  assert.equal(renderEmail(validate(valid()).data).subject, "New enquiry — The Cedar Spa");
});
