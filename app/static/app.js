/* EVE Healthcare — Demo Console. Vanilla JS, no build step. */
"use strict";

const API = "/api/v1";
const state = {
  token: localStorage.getItem("eve_token") || "",
  user: null,
  centres: [],
  tests: [],
  bookings: [],
  payments: [],
  centreDetail: null,
  lastWebhook: null,
  log: [],
};

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2 });
const pill = (status) => {
  const map = { CONFIRMED: "ok", SUCCESS: "ok", PENDING: "warn", FAILED: "bad", CANCELLED: "muted" };
  return `<span class="pill ${map[status] || "muted"}">${esc(status)}</span>`;
};
const fmtTime = (iso) => { try { return new Date(iso).toLocaleString(); } catch { return iso; } };
const randEvent = () => "evt_" + Math.random().toString(36).slice(2, 10);
const futureISO = (days = 2) => new Date(Date.now() + days * 864e5).toISOString().slice(0, 16);

/* ---------------- API + console + toasts ---------------- */

function logCall(method, path, status, req, res) {
  state.log.unshift({ t: new Date().toLocaleTimeString(), method, path, status, req, res });
  if (state.log.length > 100) state.log.pop();
  $("console-count").textContent = state.log.length;
  renderConsole();
}

async function api(method, path, body = null, extraHeaders = {}, opts = {}) {
  const headers = { "Content-Type": "application/json", ...extraHeaders };
  if (state.token && !opts.noAuth) headers.Authorization = "Bearer " + state.token;
  let status = 0, data = null;
  try {
    const res = await fetch(API + path, {
      method,
      headers,
      body: body === null ? null : JSON.stringify(body),
    });
    status = res.status;
    const text = await res.text();
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  } catch (e) {
    data = { detail: "Network error: " + e.message };
  }
  logCall(method, path, status, body, data);
  if (status === 401 && state.token && !opts.noAuth && !opts.keepToken) {
    // Token expired/invalid — sign out silently.
    setToken("");
    toast("Session expired", "Please sign in again.", "err");
  }
  return { status, data };
}

function toast(title, msg, type = "info") {
  const el = document.createElement("div");
  el.className = "toast " + (type === "ok" ? "ok" : type === "err" ? "err" : "");
  el.innerHTML = `<b>${esc(title)}</b><span class="mono">${esc(msg || "")}</span>`;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

function renderConsole() {
  const box = $("console-log");
  if (!state.log.length) { box.innerHTML = `<div class="empty">No API calls yet — use any tab above.</div>`; return; }
  box.innerHTML = state.log.map((e) => {
    const cls = e.status >= 200 && e.status < 300 ? "status-2" : e.status >= 400 ? "status-4" : "";
    return `<details>
      <summary><span class="method">${esc(e.method)}</span><span>${esc(e.path)}</span>
      <span class="${cls}">${e.status || "ERR"}</span><span style="color:var(--muted)">${esc(e.t)}</span></summary>
      <pre class="json">▸ request:\n${esc(JSON.stringify(e.req, null, 2))}\n\n◂ response (${e.status}):\n${esc(JSON.stringify(e.res, null, 2))}</pre>
    </details>`;
  }).join("");
}

/* ---------------- auth ---------------- */

function setToken(t) {
  state.token = t || "";
  if (t) localStorage.setItem("eve_token", t); else localStorage.removeItem("eve_token");
  if (!t) state.user = null;
  renderSession();
}

function renderSession() {
  const pillEl = $("auth-pill"), chip = $("user-chip"), logout = $("btn-logout");
  if (state.user) {
    pillEl.textContent = "signed in"; pillEl.className = "pill ok";
    chip.textContent = state.user.full_name + " · " + state.user.email;
    chip.classList.remove("hidden"); logout.classList.remove("hidden");
    $("session-info").textContent = JSON.stringify({ user: state.user, token: state.token.slice(0, 24) + "…" }, null, 2);
  } else {
    pillEl.textContent = "signed out"; pillEl.className = "pill muted";
    chip.classList.add("hidden"); logout.classList.add("hidden");
    $("session-info").textContent = "{ signed out }";
  }
}

async function loadMe() {
  if (!state.token) { renderSession(); return; }
  const { status, data } = await api("GET", "/auth/me", null, {}, { keepToken: true });
  if (status === 200) { state.user = data; }
  else { setToken(""); }
  renderSession();
}

async function refreshAuthed() {
  if (!state.user) return;
  await Promise.all([loadBookings(), loadPayments()]);
  fillBookingForm(); fillPaymentForm(); fillWebhookForm();
}

/* ---------------- tabs ---------------- */

function switchTab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + name));
  if (name === "centres") { loadCentres(); loadTests(); }
  if (name === "bookings") { loadCentres().then(fillBookingForm); loadBookings(); }
  if (name === "payments") { loadBookings().then(fillPaymentForm); loadPayments(); }
  if (name === "webhook") { loadBookings().then(fillWebhookForm); }
}

/* ---------------- centres & tests ---------------- */

async function loadCentres() {
  const q = $("centre-search").value.trim();
  const { status, data } = await api("GET", `/centres/?limit=50${q ? "&q=" + encodeURIComponent(q) : ""}`);
  if (status !== 200) { toast("Failed to load centres", "HTTP " + status, "err"); return; }
  state.centres = data.items;
  const grid = $("centres-grid");
  grid.innerHTML = state.centres.length ? state.centres.map((c) => `
    <div class="card">
      <h3>${esc(c.name)}</h3>
      <p class="hint">📍 ${esc(c.location)}${c.phone ? " · ☎ " + esc(c.phone) : ""}</p>
      <div class="card-actions">
        <button class="btn secondary small" onclick="viewCentre(${c.id})">View tests &amp; prices</button>
        <button class="btn danger small" onclick="deleteCentre(${c.id}, '${esc(c.name).replace(/'/g, "\\'")}')">Delete</button>
      </div>
    </div>`).join("")
    : `<div class="empty">No centres found. Run <code>python -m app.seed</code> or create one above.</div>`;
}

async function viewCentre(id) {
  const { status, data } = await api("GET", `/centres/${id}`);
  if (status !== 200) { toast("Centre not found", "HTTP " + status, "err"); return; }
  state.centreDetail = data;
  const box = $("centre-detail");
  box.classList.remove("hidden");
  box.innerHTML = `
    <h2>${esc(data.name)}</h2>
    <p class="hint">GET /api/v1/centres/${id} · 📍 ${esc(data.location)}</p>
    <div class="list">
      ${data.tests.length ? data.tests.map((t) => `
        <div class="list-item">
          <span><code>${esc(t.test.code)}</code> ${esc(t.test.name)}
            ${t.is_available ? "" : '<span class="pill muted">unlisted</span>'}</span>
          <span class="price">${esc(t.currency)} ${esc(t.price)}</span>
        </div>`).join("") : `<div class="empty">No tests linked yet — attach one below.</div>`}
    </div>
    <h3 style="margin-top:1rem">Offer a test here <span class="tag">POST /centres/${id}/tests</span></h3>
    <form class="row-form" onsubmit="return attachTest(event, ${id})">
      <label>Test<select id="attach-test">${state.tests.map((t) => `<option value="${t.id}">${esc(t.code)} — ${esc(t.name)}</option>`).join("")}</select></label>
      <label>Price (INR)<input id="attach-price" type="number" min="1" step="0.01" value="499" required /></label>
      <button class="btn primary" type="submit">Attach</button>
    </form>`;
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function attachTest(e, centreId) {
  e.preventDefault();
  const { status, data } = await api("POST", `/centres/${centreId}/tests`, {
    test_id: Number($("attach-test").value), price: $("attach-price").value,
  });
  if (status === 201) { toast("Test attached", data.test.code + " @ ₹" + data.price, "ok"); viewCentre(centreId); }
  else toast("Attach failed", "HTTP " + status + " · " + (data.detail || JSON.stringify(data)), "err");
  return false;
}

async function deleteCentre(id, name) {
  if (!confirm(`Soft-delete "${name}"? Historical bookings stay intact.`)) return;
  const { status, data } = await api("DELETE", `/centres/${id}`);
  if (status === 204) { toast("Centre deleted", name, "ok"); $("centre-detail").classList.add("hidden"); loadCentres(); }
  else toast("Delete failed", "HTTP " + status + " · " + (data.detail || ""), "err");
}

async function loadTests() {
  const { status, data } = await api("GET", "/tests/?limit=100");
  if (status !== 200) return;
  state.tests = data.items;
  $("tests-list").innerHTML = state.tests.length ? state.tests.map((t) => `
    <div class="list-item"><span><code>${esc(t.code)}</code> ${esc(t.name)}</span>
    <span class="hint">${esc(t.category || "")}</span></div>`).join("")
    : `<div class="empty">No tests yet.</div>`;
}

/* ---------------- bookings ---------------- */

async function loadBookings() {
  if (!state.user) {
    $("bookings-list").innerHTML = `<div class="empty">Sign in to see your bookings.</div>`;
    state.bookings = [];
    return;
  }
  const f = $("booking-filter").value;
  const { status, data } = await api("GET", `/bookings/?limit=50${f ? "&status=" + f : ""}`);
  if (status !== 200) { toast("Failed to load bookings", "HTTP " + status, "err"); return; }
  state.bookings = data.items;
  $("bookings-list").innerHTML = state.bookings.length ? state.bookings.map((b) => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
        <b>#${b.id} · ${esc(b.test_name || "")}</b>${pill(b.status)}
      </div>
      <dl class="kv">
        <dt>Centre</dt><dd>${esc(b.centre_name || b.centre_id)}</dd>
        <dt>When</dt><dd>${esc(fmtTime(b.appointment_time))}</dd>
        <dt>Amount</dt><dd class="price">${esc(b.currency)} ${esc(b.amount)}</dd>
      </dl>
      <div class="card-actions">
        ${(b.status === "PENDING" || b.status === "FAILED") ? `<button class="btn primary small" onclick="goPay(${b.id})">Pay now</button>` : ""}
        ${(b.status === "PENDING" || b.status === "CONFIRMED") ? `<button class="btn danger small" onclick="cancelBooking(${b.id})">Cancel</button>` : ""}
      </div>
    </div>`).join("")
    : `<div class="empty">No bookings yet — create one above.</div>`;
}

function fillBookingForm() {
  const cs = $("booking-centre");
  cs.innerHTML = state.centres.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("") || `<option value="">(no centres)</option>`;
  updateBookingTests();
}

async function updateBookingTests() {
  const ts = $("booking-test");
  const centreId = Number($("booking-centre").value);
  if (!centreId) { ts.innerHTML = ""; return; }
  // Reuse cached detail when possible to avoid extra calls.
  let detail = state.centreDetail && state.centreDetail.id === centreId ? state.centreDetail : null;
  if (!detail) {
    const { status, data } = await api("GET", `/centres/${centreId}`);
    if (status !== 200) return;
    detail = state.centreDetail = data;
  }
  const avail = detail.tests.filter((t) => t.is_available);
  ts.innerHTML = avail.map((t) => `<option value="${t.test.id}" data-price="${t.price}">${esc(t.test.code)} — ${esc(t.test.name)} · ₹${t.price}</option>`).join("")
    || `<option value="">(no tests at this centre)</option>`;
  updateBookingAmount();
}

function updateBookingAmount() {
  const opt = $("booking-test").selectedOptions[0];
  $("booking-amount").textContent = opt && opt.dataset.price ? inr(opt.dataset.price) : inr(0);
}

async function cancelBooking(id) {
  if (!confirm(`Cancel booking #${id}?`)) return;
  const { status, data } = await api("POST", `/bookings/${id}/cancel`);
  if (status === 200) { toast("Booking cancelled", "#" + id, "ok"); loadBookings(); }
  else toast("Cancel failed", "HTTP " + status + " · " + (data.detail || ""), "err");
}

function goPay(bookingId) {
  switchTab("payments");
  fillPaymentForm(bookingId);
}

/* ---------------- payments ---------------- */

async function loadPayments() {
  if (!state.user) {
    $("payments-list").innerHTML = `<div class="empty">Sign in to see your payments.</div>`;
    state.payments = [];
    return;
  }
  const { status, data } = await api("GET", "/payments/?limit=50");
  if (status !== 200) return;
  state.payments = data.items;
  $("payments-list").innerHTML = state.payments.length ? state.payments.map((p) => `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
        <b>Payment #${p.id} → booking #${p.booking_id}</b>${pill(p.status)}
      </div>
      <dl class="kv">
        <dt>Amount</dt><dd class="price">${esc(p.currency)} ${esc(p.amount)}</dd>
        <dt>Method</dt><dd>${esc(p.payment_method || "—")}</dd>
        <dt>Provider ref</dt><dd>${esc(p.provider_payment_id || "—")}</dd>
        ${p.failure_reason ? `<dt>Reason</dt><dd>${esc(p.failure_reason)}</dd>` : ""}
      </dl>
    </div>`).join("")
    : `<div class="empty">No payments yet.</div>`;
}

function fillPaymentForm(preselect) {
  const sel = $("payment-booking");
  const payable = state.bookings.filter((b) => b.status === "PENDING" || b.status === "FAILED");
  sel.innerHTML = payable.map((b) => `<option value="${b.id}">#${b.id} · ${esc(b.test_name || "")} · ${b.status} · ₹${b.amount}</option>`).join("")
    || `<option value="">(no payable bookings — book a test first)</option>`;
  if (preselect) sel.value = String(preselect);
}

/* ---------------- webhook ---------------- */

function fillWebhookForm() {
  const sel = $("webhook-booking");
  sel.innerHTML = state.bookings.map((b) => `<option value="${b.id}">#${b.id} · ${esc(b.test_name || "")} · ${b.status}</option>`).join("")
    || `<option value="">(sign in + book first)</option>`;
}

function webhookCard(data, status) {
  const el = document.createElement("div");
  el.className = "card";
  el.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
      <b>${esc(state.lastWebhook?.event_id || "")}</b>
      ${data.deduped ? '<span class="pill info">deduped · no state change</span>' : '<span class="pill ok">processed</span>'}
    </div>
    <dl class="kv">
      <dt>HTTP</dt><dd>${status}</dd>
      <dt>Booking</dt><dd>#${data.booking_id} → ${esc(data.booking_status || "?")}</dd>
      <dt>Payment</dt><dd>${data.payment_id ? "#" + data.payment_id : "—"}</dd>
      <dt>Message</dt><dd>${esc(data.message || "")}</dd>
    </dl>`;
  $("webhook-results").prepend(el);
}

/* ---------------- edge-case playground ---------------- */

function edgeCard(name, expected, actual, pass, detail) {
  const el = document.createElement("div");
  el.className = "card";
  el.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
      <b>${esc(name)}</b>${pass ? '<span class="pill ok">PASS</span>' : '<span class="pill bad">CHECK</span>'}
    </div>
    <dl class="kv"><dt>Expected</dt><dd>${esc(expected)}</dd><dt>Actual</dt><dd>${esc(actual)}</dd></dl>
    ${detail ? `<pre class="json">${esc(detail)}</pre>` : ""}`;
  $("edge-results").prepend(el);
}

async function needCatalogue() {
  if (!state.centres.length) await loadCentres();
  if (!state.centres.length) return null;
  const { status, data } = await api("GET", `/centres/${state.centres[0].id}`);
  if (status !== 200 || !data.tests.length) return null;
  return { centre: state.centres[0], test: data.tests[0].test };
}

async function makeBooking(centreId, testId, days = 3) {
  const t = new Date(Date.now() + days * 864e5).toISOString();
  return api("POST", "/bookings/", { centre_id: centreId, test_id: testId, appointment_time: t });
}

const edgeTests = {
  async pastDate() {
    const cat = await needCatalogue();
    if (!cat) return edgeCard("Past appointment → 422", "HTTP 422", "no catalogue data", false, "Seed data or create a centre + test first.");
    const past = new Date(Date.now() - 864e5).toISOString();
    const { status, data } = await api("POST", "/bookings/", { centre_id: cat.centre.id, test_id: cat.test.id, appointment_time: past });
    edgeCard("Past appointment → 422", "HTTP 422", "HTTP " + status, status === 422, JSON.stringify(data, null, 2));
  },
  async noAuth() {
    const { status, data } = await api("GET", "/bookings/", null, {}, { noAuth: true, keepToken: true });
    edgeCard("No token → 401", "HTTP 401", "HTTP " + status, status === 401, JSON.stringify(data, null, 2));
  },
  async doublePay() {
    const cat = await needCatalogue();
    if (!cat) return edgeCard("Double-pay → 409", "HTTP 409", "no catalogue data", false, "");
    const b = await makeBooking(cat.centre.id, cat.test.id);
    if (b.status !== 201) return edgeCard("Double-pay → 409", "HTTP 409", "setup failed: HTTP " + b.status, false, JSON.stringify(b.data));
    await api("POST", "/payments/", { booking_id: b.data.id });
    const { status, data } = await api("POST", "/payments/", { booking_id: b.data.id });
    edgeCard("Double-pay CONFIRMED → 409", "HTTP 409", "HTTP " + status, status === 409, JSON.stringify(data, null, 2));
    loadBookings(); loadPayments();
  },
  async invalidPay() {
    const { status, data } = await api("POST", "/payments/", { booking_id: 999999 });
    edgeCard("Pay bad booking ID → 404", "HTTP 404", "HTTP " + status, status === 404, JSON.stringify(data, null, 2));
  },
  async webhookReplay() {
    const cat = await needCatalogue();
    if (!cat) return edgeCard("Replay webhook 3× → deduped", "deduped ×2, 1 payment", "no catalogue data", false, "");
    const b = await makeBooking(cat.centre.id, cat.test.id);
    if (b.status !== 201) return edgeCard("Replay webhook 3× → deduped", "deduped ×2", "setup failed", false, "");
    const evt = "evt_edge_" + Math.random().toString(36).slice(2, 8);
    const p = { event_id: evt, booking_id: b.data.id, status: "SUCCESS" };
    const r1 = await api("POST", "/payments/webhook/", p);
    const r2 = await api("POST", "/payments/webhook/", p);
    const r3 = await api("POST", "/payments/webhook/", p);
    const count = await api("GET", `/payments/?booking_id=${b.data.id}`);
    const pass = r1.data?.deduped === false && r2.data?.deduped === true && r3.data?.deduped === true && count.data?.total === 1;
    edgeCard("Replay webhook 3× → deduped", "deduped:false,true,true · payments:1",
      `deduped:${r1.data?.deduped},${r2.data?.deduped},${r3.data?.deduped} · payments:${count.data?.total}`, pass,
      JSON.stringify({ first: r1.data, replay: r3.data }, null, 2));
    loadBookings(); loadPayments();
  },
  async lateFailed() {
    const cat = await needCatalogue();
    if (!cat) return edgeCard("Late FAILED → ignored", "stays CONFIRMED", "no catalogue data", false, "");
    const b = await makeBooking(cat.centre.id, cat.test.id);
    if (b.status !== 201) return edgeCard("Late FAILED → ignored", "stays CONFIRMED", "setup failed", false, "");
    await api("POST", "/payments/", { booking_id: b.data.id });
    const evt = "evt_late_" + Math.random().toString(36).slice(2, 8);
    await api("POST", "/payments/webhook/", { event_id: evt, booking_id: b.data.id, status: "FAILED" });
    const check = await api("GET", `/bookings/${b.data.id}`);
    const pass = check.data?.status === "CONFIRMED";
    edgeCard("Late FAILED after CONFIRMED → ignored", "status CONFIRMED", "status " + check.data?.status, pass,
      JSON.stringify(check.data, null, 2));
    loadBookings(); loadPayments();
  },
  async otherUser() {
    const email = "intruder@eve.health";
    // Raw fetch so the second user's token never touches our session.
    const raw = async (method, path, body, token) => {
      const h = { "Content-Type": "application/json" };
      if (token) h.Authorization = "Bearer " + token;
      const r = await fetch(API + path, { method, headers: h, body: body ? JSON.stringify(body) : null });
      return { status: r.status, data: await r.json().catch(() => null) };
    };
    let login = await raw("POST", "/auth/login", { email, password: "password123" });
    if (login.status !== 200) {
      await raw("POST", "/auth/signup", { email, password: "password123", full_name: "Intruder" });
      login = await raw("POST", "/auth/login", { email, password: "password123" });
    }
    const cat = await needCatalogue();
    if (!cat) return edgeCard("Other user's booking → 404", "HTTP 404", "no catalogue data", false, "");
    const mine = await makeBooking(cat.centre.id, cat.test.id);
    if (mine.status !== 201) return edgeCard("Other user's booking → 404", "HTTP 404", "setup failed", false, "");
    const peek = await raw("GET", `/bookings/${mine.data.id}`, null, login.data.access_token);
    logCall("GET", `/bookings/${mine.data.id}`, peek.status, "(as intruder@eve.health)", peek.data);
    edgeCard("Read another user's booking → 404", "HTTP 404 (no existence leak)", "HTTP " + peek.status, peek.status === 404,
      JSON.stringify(peek.data, null, 2));
    loadBookings();
  },
  async dupCode() {
    if (!state.tests.length) await loadTests();
    if (!state.tests.length) return edgeCard("Duplicate test code → 409", "HTTP 409", "no tests exist", false, "");
    const { status, data } = await api("POST", "/tests/", { name: "Duplicate", code: state.tests[0].code });
    edgeCard("Duplicate test code → 409", "HTTP 409", "HTTP " + status, status === 409, JSON.stringify(data, null, 2));
  },
};

/* ---------------- wiring ---------------- */

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  renderConsole();

  $("form-signup").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const { status, data } = await api("POST", "/auth/signup", Object.fromEntries(f));
    if (status === 201) {
      toast("Account created", data.email, "ok");
      const login = await api("POST", "/auth/login", { email: data.email, password: f.get("password") });
      if (login.status === 200) { setToken(login.data.access_token); await loadMe(); refreshAuthed(); }
    } else toast("Signup failed", "HTTP " + status + " · " + (data.detail || JSON.stringify(data)), "err");
  });

  $("form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const { status, data } = await api("POST", "/auth/login", Object.fromEntries(f));
    if (status === 200) { setToken(data.access_token); await loadMe(); refreshAuthed(); toast("Welcome back", state.user.full_name, "ok"); }
    else toast("Login failed", "HTTP " + status + " · " + (data.detail || ""), "err");
  });

  $("btn-demo-user").addEventListener("click", async () => {
    const creds = { email: "demo@eve.health", password: "password123", full_name: "Demo User" };
    let r = await api("POST", "/auth/signup", creds);
    if (r.status !== 201 && r.data?.detail !== "Email already registered") {
      toast("Demo setup failed", "HTTP " + r.status, "err"); return;
    }
    r = await api("POST", "/auth/login", { email: creds.email, password: creds.password });
    if (r.status === 200) { setToken(r.data.access_token); await loadMe(); refreshAuthed(); toast("Signed in as demo user", creds.email, "ok"); }
  });

  $("btn-logout").addEventListener("click", () => {
    setToken(""); state.bookings = []; state.payments = [];
    loadBookings(); loadPayments();
    toast("Signed out", "", "info");
  });

  $("centre-search").addEventListener("input", () => loadCentres());
  $("btn-centre-refresh").addEventListener("click", () => { loadCentres(); loadTests(); });
  $("btn-centre-new-toggle").addEventListener("click", () => $("centre-form-wrap").classList.toggle("hidden"));

  $("form-centre").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    if (!f.phone) delete f.phone;
    const { status, data } = await api("POST", "/centres/", f);
    if (status === 201) { toast("Centre created", data.name, "ok"); e.target.reset(); loadCentres(); }
    else toast("Create failed", "HTTP " + status + " · " + (data.detail || ""), "err");
  });

  $("form-test").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    f.code = f.code.toUpperCase();
    if (!f.category) delete f.category;
    const { status, data } = await api("POST", "/tests/", f);
    if (status === 201) { toast("Test added", data.code, "ok"); e.target.reset(); loadTests(); }
    else toast("Add failed", "HTTP " + status + " · " + (data.detail || JSON.stringify(data)), "err");
  });

  $("booking-centre").addEventListener("change", updateBookingTests);
  $("booking-test").addEventListener("change", updateBookingAmount);
  $("booking-time").value = futureISO(2);
  $("form-booking").addEventListener("submit", async (e) => {
    e.preventDefault();
    const headers = {};
    if ($("booking-key").value.trim()) headers["Idempotency-Key"] = $("booking-key").value.trim();
    const { status, data } = await api("POST", "/bookings/", {
      centre_id: Number($("booking-centre").value),
      test_id: Number($("booking-test").value),
      appointment_time: new Date($("booking-time").value).toISOString(),
    }, headers);
    if (status === 201) { toast("Booked! PENDING", "#" + data.id + " · ₹" + data.amount, "ok"); loadBookings().then(fillPaymentForm); }
    else toast("Booking failed", "HTTP " + status + " · " + (data.detail || JSON.stringify(data)), "err");
  });
  $("booking-filter").addEventListener("change", loadBookings);
  $("btn-booking-refresh").addEventListener("click", loadBookings);

  $("form-payment").addEventListener("submit", async (e) => {
    e.preventDefault();
    const headers = {};
    if ($("payment-key").value.trim()) headers["Idempotency-Key"] = $("payment-key").value.trim();
    const { status, data } = await api("POST", "/payments/", {
      booking_id: Number($("payment-booking").value),
      payment_method: $("payment-method").value,
      simulate_failure: $("payment-fail").checked,
    }, headers);
    if (status === 201) {
      toast(data.status === "SUCCESS" ? "Payment SUCCESS → CONFIRMED" : "Payment FAILED → booking FAILED",
        "ref " + data.provider_payment_id, data.status === "SUCCESS" ? "ok" : "err");
      loadBookings(); loadPayments();
    } else toast("Payment failed", "HTTP " + status + " · " + (data.detail || ""), "err");
  });
  $("btn-payment-refresh").addEventListener("click", loadPayments);

  $("webhook-event").value = randEvent();
  $("btn-webhook-new").addEventListener("click", () => { $("webhook-event").value = randEvent(); });
  $("form-webhook").addEventListener("submit", async (e) => {
    e.preventDefault();
    state.lastWebhook = {
      event_id: $("webhook-event").value.trim(),
      booking_id: Number($("webhook-booking").value),
      status: $("webhook-status").value,
    };
    const { status, data } = await api("POST", "/payments/webhook/", state.lastWebhook);
    if (status === 200) {
      webhookCard(data, status);
      $("btn-webhook-replay").disabled = false;
      toast(data.deduped ? "Duplicate ignored (idempotent)" : "Webhook processed", data.message, data.deduped ? "info" : "ok");
      loadBookings().then(() => { fillPaymentForm(); fillWebhookForm(); }); loadPayments();
    } else toast("Webhook failed", "HTTP " + status + " · " + (data.detail || ""), "err");
  });
  $("btn-webhook-replay").addEventListener("click", async () => {
    if (!state.lastWebhook) return;
    const { status, data } = await api("POST", "/payments/webhook/", state.lastWebhook);
    if (status === 200) { webhookCard(data, status); toast("Replay sent", data.message, "info"); }
  });

  document.querySelectorAll("[data-edge]").forEach((b) =>
    b.addEventListener("click", () => {
      if (!state.user) return toast("Sign in first", "Edge tests need an account.", "err");
      edgeTests[b.dataset.edge]();
    }));
  $("btn-edge-all").addEventListener("click", async () => {
    if (!state.user) return toast("Sign in first", "Edge tests need an account.", "err");
    for (const key of Object.keys(edgeTests)) await edgeTests[key]();
    toast("Edge suite finished", "See results above + API Console.", "ok");
  });

  $("btn-console-clear").addEventListener("click", () => {
    state.log = []; $("console-count").textContent = "0"; renderConsole();
  });

  // init
  loadMe().then(refreshAuthed);
  loadCentres();
  loadTests();
});

// exposed for inline onclick handlers
window.viewCentre = viewCentre;
window.deleteCentre = deleteCentre;
window.attachTest = attachTest;
window.cancelBooking = cancelBooking;
window.goPay = goPay;
