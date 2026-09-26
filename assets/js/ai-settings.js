const RN_FRAPPE_BASE = location.origin + "/rescue-net-frappe/api/method";
let RN_FRAPPE_SESSION = null;

function statusMsg(msg) {
  const el = document.getElementById("aiSettingsStatus");
  if (el) el.textContent = msg;
}

async function frappeCall(method, args = {}, write = false) {
  let url = `${RN_FRAPPE_BASE}/${method}`;

  const headers = {
    "Accept": "application/json"
  };

  const options = {
    credentials: "same-origin",
    headers
  };

  if (write) {
    if (!RN_FRAPPE_SESSION?.csrf_token) {
      throw new Error("Frappe session belum siap.");
    }

    headers["Content-Type"] = "application/json";
    headers["X-Frappe-CSRF-Token"] = RN_FRAPPE_SESSION.csrf_token;

    options.method = "POST";
    options.body = JSON.stringify(args);
  } else {
    const query = new URLSearchParams();

    Object.entries(args).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "") {
        query.set(key, value);
      }
    });

    if (query.toString()) {
      url += "?" + query.toString();
    }
  }

  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const clean = String(data.message || data.exception || `Frappe API error ${res.status}`)
      .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    const e = new Error(res.status === 403 ? "Perlu login untuk fitur ini." : clean);
    e.status = res.status;
    throw e;
  }

  return Object.prototype.hasOwnProperty.call(data, "message")
    ? data.message
    : data;
}

async function ensureSession() {
  if (RN_FRAPPE_SESSION) return RN_FRAPPE_SESSION;

  RN_FRAPPE_SESSION = await frappeCall(
    "rescue_net.api_ai.session_info"
  );

  const form = getForm();

  if (form?.user_id) {
    form.user_id.value = RN_FRAPPE_SESSION.user;
    form.user_id.readOnly = true;
  }

  if (form?.organization_id && RN_FRAPPE_SESSION.organization_id) {
    form.organization_id.value =
      RN_FRAPPE_SESSION.organization_id;
  }

  return RN_FRAPPE_SESSION;
}

/* ---- Provider catalogue (OpenAI / Claude / Gemini) ---- */
let RN_AI_PROVIDERS = [];

function fillModels(form) {
  const prov = form.querySelector("[data-ai-provider]");
  const model = form.querySelector("[data-ai-model]");
  if (!prov || !model) return;
  const spec = RN_AI_PROVIDERS.find(p => p.provider === prov.value);
  const models = spec ? spec.models : [];
  model.innerHTML = models.map(m =>
    `<option value="${m}"${spec && m === spec.default_model ? " selected" : ""}>${m}</option>`).join("");
  const key = form.querySelector("input[name='api_key']");
  if (key && spec) key.placeholder = "Paste API key (" + spec.key_hint + ")";
}

async function loadProviders() {
  try {
    RN_AI_PROVIDERS = await frappeCall("rescue_net.api_ai.ai_providers");
  } catch (err) {
    // backend without the multi-provider endpoint yet: OpenAI only
    RN_AI_PROVIDERS = [{ provider: "openai", label: "OpenAI", default_model: "gpt-4o-mini",
      models: ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"], key_hint: "sk-..." }];
  }
  document.querySelectorAll("form").forEach(form => {
    const prov = form.querySelector("[data-ai-provider]");
    if (!prov) return;
    prov.innerHTML = RN_AI_PROVIDERS.map(p => `<option value="${p.provider}">${p.label}</option>`).join("");
    prov.addEventListener("change", () => fillModels(form));
    fillModels(form);
  });
}

function providerLabel(p) {
  return (RN_AI_PROVIDERS.find(x => x.provider === p) || {}).label || p || "-";
}

/* ---- Platform key (System Manager) ---- */
async function platformCheck() {
  const d = await frappeCall("rescue_net.api_ai.get_platform_key_status");
  document.getElementById("platformKeySection").hidden = false;
  const rows = (d.providers || []).map(p =>
    `<div><span>${providerLabel(p.provider)}</span><b>${p.key_exists ? p.masked_key + " · " + p.model_name : "Belum diatur"}</b></div>`);
  rows.unshift(`<div><span>Provider aktif</span><b>${d.active_provider ? providerLabel(d.active_provider) + " · " + d.active_model : "Tidak ada (pakai aturan kata kunci)"}</b></div>`);
  document.getElementById("platformKeyStatus").innerHTML = rows.join("");
}

async function platformSave(e) {
  e.preventDefault();
  const f = document.getElementById("platformKeyForm");
  const msg = document.getElementById("platformKeyMsg");
  msg.textContent = "Menyimpan…";
  await frappeCall("rescue_net.api_ai.save_platform_key", {
    provider: f.provider.value, model_name: f.model_name.value,
    api_key: f.api_key.value.trim(), api_key_label: f.api_key_label.value.trim()
  }, true);
  f.api_key.value = "";
  msg.textContent = "Tersimpan terenkripsi.";
  await platformCheck();
}

function platformProvider() {
  return document.getElementById("platformKeyForm").provider.value;
}

function getForm() {
  return document.getElementById("aiKeyForm");
}

function renderKeyStatus(data) {
  const el = document.getElementById("keyStatus");

  if (!data.key_exists) {
    el.innerHTML = `
      <div><span>User</span><b>${data.user_id || "-"}</b></div>
      <div><span>Provider</span><b>${providerLabel(data.provider)}</b></div>
      <div><span>Key</span><b>Not configured</b></div>
      <div><span>Status</span><b>No active AI key</b></div>
    `;
    return;
  }

  const s = data.setting || {};

  el.innerHTML = `
    <div><span>User</span><b>${s.user_id}</b></div>
    <div><span>Organization</span><b>${s.organization_id || "personal"}</b></div>
    <div><span>Provider</span><b>${providerLabel(s.provider)}</b></div>
    <div><span>Model</span><b>${s.model_name}</b></div>
    <div><span>Masked Key</span><b>${data.masked_key}</b></div>
    <div><span>Label</span><b>${s.api_key_label || "-"}</b></div>
    <div><span>Status</span><b>${s.status}</b></div>
  `;
}

async function checkKeyStatus() {
  const session = await ensureSession();
  const form = getForm();

  statusMsg("Checking Frappe AI key status...");

  const data = await frappeCall(
    "rescue_net.api_ai.get_user_key_status",
    {
      user_id: session.user,
      provider: form.provider.value
    }
  );

  renderKeyStatus(data);
  statusMsg("Frappe AI key status loaded.");
}

async function saveKey(e) {
  e.preventDefault();

  const form = getForm();

  const session = await ensureSession();

  const payload = {
    user_id: session.user,
    organization_id: form.organization_id.value.trim() || null,
    provider: form.provider.value,
    model_name: form.model_name.value,
    api_key: form.api_key.value.trim(),
    api_key_label: form.api_key_label.value.trim()
  };

  statusMsg("Saving encrypted AI key to Frappe...");

  const data = await frappeCall(
    "rescue_net.api_ai.save_user_key",
    payload,
    true
  );

  form.api_key.value = "";
  renderKeyStatus({
    key_exists: true,
    masked_key: "****" + (data.setting.api_key_last4 || ""),
    setting: data.setting
  });

  statusMsg("AI key saved encrypted. Secret key cleared from form.");
}

async function deleteKey() {
  const session = await ensureSession();
  const form = getForm();
  const provider = form.provider.value;

  if (!confirm(`Delete AI key for ${session.user}/${provider}?`)) {
    return;
  }

  statusMsg("Deleting Frappe AI key...");

  await frappeCall(
    "rescue_net.api_ai.delete_user_key",
    {
      user_id: session.user,
      provider
    },
    true
  );

  await checkKeyStatus();
  statusMsg("AI key deleted.");
}

/* ---- Uji Koneksi (personal) ---- */
async function testKey() {
  const session = await ensureSession();
  const form = getForm();
  const el = document.getElementById("testKeyMsg");
  el.textContent = "Menguji…";
  const r = await frappeCall("rescue_net.api_ai.test_ai_key",
    { user_id: session.user, provider: form.provider.value }, true);
  el.textContent = (r.ok ? "✓ " : "✗ ") + (r.message || "");
}

/* ---- Org key section ---- */
function orgId() {
  return (RN_FRAPPE_SESSION && RN_FRAPPE_SESSION.organization_id) || "";
}
function renderOrgStatus(d) {
  const el = document.getElementById("orgKeyStatus");
  if (!d || !d.key_exists) {
    el.innerHTML = `<div><span>Organisasi</span><b>${orgId() || "-"}</b></div>` +
      `<div><span>Kunci</span><b>Belum diatur</b></div>`;
    return;
  }
  const s = d.setting || {};
  el.innerHTML = `<div><span>Organisasi</span><b>${s.organization_id}</b></div>` +
    `<div><span>Provider</span><b>${providerLabel(s.provider)}</b></div>` +
    `<div><span>Model</span><b>${s.model_name}</b></div>` +
    `<div><span>Masked</span><b>${d.masked_key}</b></div>` +
    `<div><span>Status</span><b>${s.status}</b></div>`;
}
async function orgCheck() {
  if (!orgId()) return;
  const d = await frappeCall("rescue_net.api_ai.get_org_key_status",
    { organization_id: orgId(), provider: document.getElementById("orgKeyForm").provider.value });
  renderOrgStatus(d);
}
async function orgSave(e) {
  e.preventDefault();
  const f = document.getElementById("orgKeyForm");
  document.getElementById("orgKeyMsg").textContent = "Menyimpan…";
  await frappeCall("rescue_net.api_ai.save_org_key", {
    organization_id: orgId(), provider: f.provider.value,
    model_name: f.model_name.value, api_key: f.api_key.value.trim(),
    api_key_label: f.api_key_label.value.trim(),
  }, true);
  f.api_key.value = "";
  document.getElementById("orgKeyMsg").textContent = "Tersimpan terenkripsi.";
  await orgCheck();
}
async function orgTest() {
  document.getElementById("orgKeyMsg").textContent = "Menguji…";
  const r = await frappeCall("rescue_net.api_ai.test_ai_key",
    { organization_id: orgId(), provider: document.getElementById("orgKeyForm").provider.value }, true);
  document.getElementById("orgKeyMsg").textContent = (r.ok ? "✓ " : "✗ ") + (r.message || "");
}
async function orgDelete() {
  if (!confirm("Hapus kunci AI organisasi " + orgId() + "?")) return;
  await frappeCall("rescue_net.api_ai.delete_org_key",
    { organization_id: orgId(), provider: document.getElementById("orgKeyForm").provider.value }, true);
  await orgCheck();
}

/* ---- Usage summary ---- */
function renderUsage(u, scope) {
  const el = document.getElementById("aiUsage");
  el.innerHTML =
    `<div><span>Cakupan</span><b>${scope}</b></div>` +
    `<div><span>Panggilan (${u.days} hari)</span><b>${u.calls}</b></div>` +
    `<div><span>Berhasil / Error</span><b>${u.ok} / ${u.errors}</b></div>` +
    `<div><span>Total token</span><b>${(u.total_tokens || 0).toLocaleString("id-ID")}</b></div>` +
    `<div><span>Sumber kunci (user / org)</span><b>${u.by_key_source.user} / ${u.by_key_source.organization}</b></div>`;
}
async function usageUser() {
  const s = await ensureSession();
  const u = await frappeCall("rescue_net.api_ai.ai_usage_summary", { user_id: s.user, days: 30 });
  renderUsage(u, "Pemakaian Anda");
}
async function usageOrg() {
  const u = await frappeCall("rescue_net.api_ai.ai_usage_summary", { organization_id: orgId(), days: 30 });
  renderUsage(u, "Organisasi " + orgId());
}

document.addEventListener("DOMContentLoaded", async () => {
  const form = getForm();
  form.addEventListener("submit", saveKey);
  await loadProviders().catch(err => statusMsg(err.message));
  form.provider.addEventListener("change", () => checkKeyStatus().catch(err => statusMsg(err.message)));
  document.getElementById("orgKeyForm").provider.addEventListener("change", () => orgCheck().catch(() => {}));

  // Platform key: the section appears only when the System Manager check passes.
  platformCheck().then(() => {
    const pf = document.getElementById("platformKeyForm");
    const pmsg = document.getElementById("platformKeyMsg");
    pf.addEventListener("submit", e => platformSave(e).catch(err => { pmsg.textContent = "✗ " + err.message; }));
    document.getElementById("platformTestBtn").addEventListener("click", async () => {
      pmsg.textContent = "Menguji…";
      try {
        const r = await frappeCall("rescue_net.api_ai.test_platform_key", { provider: platformProvider() }, true);
        pmsg.textContent = (r.ok ? "✓ " : "✗ ") + (r.message || "");
      } catch (err) { pmsg.textContent = "✗ " + err.message; }
    });
    document.getElementById("platformDeleteBtn").addEventListener("click", async () => {
      if (!confirm("Hapus kunci AI platform untuk " + providerLabel(platformProvider()) + "?")) return;
      try {
        await frappeCall("rescue_net.api_ai.delete_platform_key", { provider: platformProvider() }, true);
        await platformCheck();
      } catch (err) { pmsg.textContent = "✗ " + err.message; }
    });
  }).catch(() => {});

  document.getElementById("checkKeyBtn").addEventListener("click", () => {
    checkKeyStatus().catch(err => statusMsg(err.message));
  });
  document.getElementById("testKeyBtn").addEventListener("click", () => {
    testKey().catch(err => { document.getElementById("testKeyMsg").textContent = "✗ " + err.message; });
  });
  document.getElementById("deleteKeyBtn").addEventListener("click", () => {
    deleteKey().catch(err => statusMsg(err.message));
  });
  document.getElementById("usageUserBtn").addEventListener("click", () => {
    usageUser().catch(err => statusMsg(err.message));
  });

  ensureSession().then(() => {
    if (orgId()) {
      document.getElementById("orgKeySection").hidden = false;
      document.getElementById("usageOrgBtn").hidden = false;
      const f = document.getElementById("orgKeyForm");
      if (f.organization_id) f.organization_id.value = orgId();
      f.addEventListener("submit", e => orgSave(e).catch(err => {
        document.getElementById("orgKeyMsg").textContent = "✗ " + err.message;
      }));
      document.getElementById("orgCheckBtn").addEventListener("click", () => orgCheck().catch(e => {}));
      document.getElementById("orgTestBtn").addEventListener("click", () => orgTest().catch(e => {}));
      document.getElementById("orgDeleteBtn").addEventListener("click", () => orgDelete().catch(e => {}));
      document.getElementById("usageOrgBtn").addEventListener("click", () => usageOrg().catch(e => statusMsg(e.message)));
      orgCheck().catch(e => {});
    }
  }).catch(() => {});

  checkKeyStatus().catch(err => statusMsg(err.message));
});
