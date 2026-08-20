/**
 * POST /api/intake — the landing page's contact form.
 *
 * Sends Kay a notification and the enquirer a short confirmation. Nothing is
 * persisted: this is a delivery pipe, not a CRM.
 *
 * Environment (set as Pages secrets, never committed):
 *   RESEND_API_KEY     required — Resend API key
 *   INTAKE_TO          required — where enquiries land (Kay's inbox)
 *   INTAKE_FROM        required — verified sender, e.g. "Kayspective Media <hello@kayspectivemedia.com>"
 *   TURNSTILE_SECRET   optional — enables bot checking when present
 */
import { validate, renderEmail, escapeHtml } from "./_lib/validate.js";

const RESEND_ENDPOINT = "https://api.resend.com/emails";
const TURNSTILE_ENDPOINT = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

/** Native form posts get a redirect; fetch() callers get JSON. */
const wantsJson = (request) =>
  (request.headers.get("accept") || "").includes("application/json") ||
  request.headers.get("x-requested-with") === "fetch";

const redirect = (request, path) =>
  Response.redirect(new URL(path, request.url).toString(), 303);

async function readFields(request) {
  const type = request.headers.get("content-type") || "";
  if (type.includes("application/json")) return await request.json();
  const form = await request.formData();
  return Object.fromEntries(form.entries());
}

async function passesTurnstile(env, token, ip) {
  if (!env.TURNSTILE_SECRET) return true; // not configured (local dev) — skip
  if (!token) return false;
  const body = new FormData();
  body.append("secret", env.TURNSTILE_SECRET);
  body.append("response", token);
  if (ip) body.append("remoteip", ip);
  try {
    const res = await fetch(TURNSTILE_ENDPOINT, { method: "POST", body });
    return (await res.json()).success === true;
  } catch {
    return false; // fail closed
  }
}

async function sendEmail(env, payload) {
  const res = await fetch(RESEND_ENDPOINT, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.RESEND_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`resend ${res.status}: ${(await res.text()).slice(0, 300)}`);
  return res.json();
}

function confirmation(data) {
  return {
    subject: "Thanks — I've got your details",
    text:
      `Hi ${data.name},\n\n` +
      `Thanks for reaching out about ${data.business}. I've got your details and I'll come ` +
      `back to you personally, usually within two business days.\n\n— Kay\nKayspective Media\n`,
    html:
      `<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:520px;color:#2B231C">` +
      `<p>Hi ${escapeHtml(data.name)},</p>` +
      `<p>Thanks for reaching out about <strong>${escapeHtml(data.business)}</strong>. I&rsquo;ve got your ` +
      `details and I&rsquo;ll come back to you personally, usually within two business days.</p>` +
      `<p style="color:#62533F">— Kay<br>Kayspective Media</p></div>`,
  };
}

async function handlePost({ request, env }) {
  let fields;
  try {
    fields = await readFields(request);
  } catch {
    return json({ ok: false, message: "Could not read the form." }, 400);
  }

  const { ok, errors, data, spam } = validate(fields);

  // Bots get the same shape as success so they learn nothing. Nothing is sent.
  if (spam) return wantsJson(request) ? json({ ok: true }) : redirect(request, "/thank-you/");

  if (!ok) {
    if (wantsJson(request)) return json({ ok: false, errors }, 422);
    return redirect(request, "/thank-you/?error=1");
  }

  // A missing token and a rejected one are different situations. The widget is
  // JavaScript, so no token usually means a visitor with JS off rather than a
  // bot -- they get told to email instead. The server cannot tell the two apart,
  // so both are still refused; only the wording differs.
  const token = fields["cf-turnstile-response"];
  const ip = request.headers.get("cf-connecting-ip");
  if (env.TURNSTILE_SECRET && !token) {
    const message = "This form needs JavaScript to verify you're human. Please email kayspectivemedia@gmail.com instead.";
    return wantsJson(request) ? json({ ok: false, message }, 403) : redirect(request, "/thank-you/?error=verify");
  }
  if (!(await passesTurnstile(env, token, ip))) {
    const message = "Could not verify you're human. Please try again, or email kayspectivemedia@gmail.com.";
    return wantsJson(request) ? json({ ok: false, message }, 403) : redirect(request, "/thank-you/?error=verify");
  }

  if (!env.RESEND_API_KEY || !env.INTAKE_TO || !env.INTAKE_FROM) {
    console.error("intake: missing RESEND_API_KEY / INTAKE_TO / INTAKE_FROM");
    const message = "The form is not configured yet. Please email kayspectivemedia@gmail.com.";
    return wantsJson(request) ? json({ ok: false, message }, 503) : redirect(request, "/thank-you/?error=1");
  }

  const mail = renderEmail(data, { received: new Date().toUTCString() });

  try {
    await sendEmail(env, {
      from: env.INTAKE_FROM,
      to: [env.INTAKE_TO],
      reply_to: data.email,
      subject: mail.subject,
      html: mail.html,
      text: mail.text,
    });
  } catch (err) {
    // Never lose a lead silently: surface it so they can email directly.
    console.error("intake: notification failed —", err.message);
    const message = "Something went wrong sending that. Please email kayspectivemedia@gmail.com and I'll pick it up.";
    return wantsJson(request) ? json({ ok: false, message }, 502) : redirect(request, "/thank-you/?error=1");
  }

  // Best-effort courtesy reply; a failure here must not fail the submission,
  // because Kay already has the enquiry.
  try {
    const reply = confirmation(data);
    await sendEmail(env, {
      from: env.INTAKE_FROM,
      to: [data.email],
      subject: reply.subject,
      html: reply.html,
      text: reply.text,
    });
  } catch (err) {
    console.error("intake: confirmation failed —", err.message);
  }

  return wantsJson(request) ? json({ ok: true }) : redirect(request, "/thank-you/");
}

/**
 * Single entry point so every verb is accounted for. Exporting both `onRequest`
 * and method-specific handlers is ambiguous; a bare GET would otherwise fall
 * through to the static assets and quietly return the home page.
 */
export async function onRequest(context) {
  if (context.request.method === "POST") return handlePost(context);
  if (context.request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: { allow: "POST, OPTIONS" } });
  }
  return new Response("Method not allowed", {
    status: 405,
    headers: { allow: "POST, OPTIONS", "cache-control": "no-store" },
  });
}
