/**
 * Pure validation and formatting for the intake form.
 *
 * Deliberately free of Workers APIs so it can be unit-tested under plain node.
 * Nothing here touches the network, the environment, or `Request`.
 */

export const SUPPORT_LEVELS = [
  "Strategy & Guidance — we'll create and post ourselves",
  "Consistent Content — 3 videos a week",
  "Growth Content — 5 videos a week",
  "Daily Content — showing up every day",
  "Not sure yet — recommend a level after an audit",
];

export const LIMITS = {
  business: 120,
  name: 120,
  email: 200,
  city: 120,
  support: 200,
  message: 2000,
};

// Pragmatic rather than RFC-complete: one @, a dot in the domain, no whitespace.
// Over-strict email regexes reject real addresses, which costs leads.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Collapse whitespace and trim. Returns '' for null/undefined. */
export function clean(value) {
  return typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";
}

/**
 * @returns {{ok: boolean, errors: Record<string,string>, data: object, spam: boolean}}
 */
export function validate(raw = {}) {
  const data = {};
  for (const key of Object.keys(LIMITS)) data[key] = clean(raw[key]);
  // the message is the one field where line breaks carry meaning
  data.message = typeof raw.message === "string" ? raw.message.trim().slice(0, LIMITS.message) : "";

  // Honeypot: a hidden field only a bot fills in. Report success to the caller
  // rather than an error, so a bot learns nothing from the response.
  const spam = clean(raw.website) !== "";

  const errors = {};
  if (!data.business) errors.business = "Please tell me your business name.";
  if (!data.name) errors.name = "Please tell me your name.";

  if (!data.email) errors.email = "Please add an email so I can reply.";
  else if (!EMAIL.test(data.email)) errors.email = "That email doesn't look right.";

  if (!data.support) errors.support = "Please choose a level of support.";
  else if (!SUPPORT_LEVELS.includes(data.support)) errors.support = "Please choose one of the listed options.";

  for (const [key, max] of Object.entries(LIMITS)) {
    if (data[key].length > max) errors[key] = `Please keep this under ${max} characters.`;
  }

  return { ok: Object.keys(errors).length === 0, errors, data, spam };
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape for interpolation into an HTML email body. */
export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

/**
 * Build the notification Kay receives. Submitted values are attacker-controlled,
 * so every one of them is escaped before it reaches an HTML email client.
 */
export function renderEmail(data, meta = {}) {
  const row = (label, value) =>
    value
      ? `<tr><td style="padding:6px 16px 6px 0;color:#62533F;white-space:nowrap;vertical-align:top">${escapeHtml(label)}</td>` +
        `<td style="padding:6px 0;color:#2B231C">${escapeHtml(value).replace(/\n/g, "<br>")}</td></tr>`
      : "";

  const html = `<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:560px">
<h2 style="font-weight:400;color:#2B231C">New enquiry — ${escapeHtml(data.business)}</h2>
<table style="border-collapse:collapse;font-size:15px">
${row("Business", data.business)}${row("Name", data.name)}${row("Email", data.email)}
${row("City", data.city)}${row("Support", data.support)}${row("Message", data.message)}
${row("Received", meta.received)}
</table>
<p style="font-size:13px;color:#62533F">Sent from the kayspectivemedia.com intake form.</p>
</div>`;

  const text = [
    `New enquiry — ${data.business}`,
    "",
    `Name:    ${data.name}`,
    `Email:   ${data.email}`,
    data.city ? `City:    ${data.city}` : null,
    `Support: ${data.support}`,
    data.message ? `\n${data.message}` : null,
  ]
    .filter((line) => line !== null)
    .join("\n");

  return { subject: `New enquiry — ${data.business}`, html, text };
}
