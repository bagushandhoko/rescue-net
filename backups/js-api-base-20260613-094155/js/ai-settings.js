const RN_API_BASE = "http://192.168.100.32:8092";

function statusMsg(msg) {
  const el = document.getElementById("aiSettingsStatus");
  if (el) el.textContent = msg;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function getForm() {
  return document.getElementById("aiKeyForm");
}

function renderKeyStatus(data) {
  const el = document.getElementById("keyStatus");

  if (!data.key_exists) {
    el.innerHTML = `
      <div><span>User</span><b>${data.user_id || "-"}</b></div>
      <div><span>Provider</span><b>${data.provider || "openai"}</b></div>
      <div><span>Key</span><b>Not configured</b></div>
      <div><span>Status</span><b>No active AI key</b></div>
    `;
    return;
  }

  const s = data.setting || {};

  el.innerHTML = `
    <div><span>User</span><b>${s.user_id}</b></div>
    <div><span>Organization</span><b>${s.organization_id || "personal"}</b></div>
    <div><span>Provider</span><b>${s.provider}</b></div>
    <div><span>Model</span><b>${s.model_name}</b></div>
    <div><span>Masked Key</span><b>${data.masked_key}</b></div>
    <div><span>Label</span><b>${s.api_key_label || "-"}</b></div>
    <div><span>Status</span><b>${s.status}</b></div>
  `;
}

async function checkKeyStatus() {
  const form = getForm();
  const userId = form.user_id.value.trim();
  const provider = form.provider.value;

  statusMsg("Checking AI key status...");
  const data = await api(`/ai/user-key/${encodeURIComponent(userId)}?provider=${encodeURIComponent(provider)}`);
  renderKeyStatus(data);
  statusMsg("Key status loaded.");
}

async function saveKey(e) {
  e.preventDefault();

  const form = getForm();

  const payload = {
    user_id: form.user_id.value.trim(),
    organization_id: form.organization_id.value.trim() || null,
    provider: form.provider.value,
    model_name: form.model_name.value,
    api_key: form.api_key.value.trim(),
    api_key_label: form.api_key_label.value.trim()
  };

  statusMsg("Saving encrypted AI key...");
  const data = await api("/ai/user-key", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  form.api_key.value = "";
  renderKeyStatus({
    key_exists: true,
    masked_key: "****" + (data.setting.api_key_last4 || ""),
    setting: data.setting
  });

  statusMsg("AI key saved encrypted. Secret key cleared from form.");
}

async function deleteKey() {
  const form = getForm();
  const userId = form.user_id.value.trim();
  const provider = form.provider.value;

  if (!confirm(`Delete AI key for ${userId}/${provider}?`)) return;

  statusMsg("Deleting AI key...");
  await api(`/ai/user-key/${encodeURIComponent(userId)}?provider=${encodeURIComponent(provider)}`, {
    method: "DELETE"
  });

  statusMsg("AI key deleted.");
  await checkKeyStatus();
}

document.addEventListener("DOMContentLoaded", () => {
  const form = getForm();
  form.addEventListener("submit", saveKey);

  document.getElementById("checkKeyBtn").addEventListener("click", () => {
    checkKeyStatus().catch(err => statusMsg(err.message));
  });

  document.getElementById("deleteKeyBtn").addEventListener("click", () => {
    deleteKey().catch(err => statusMsg(err.message));
  });

  checkKeyStatus().catch(err => statusMsg(err.message));
});
