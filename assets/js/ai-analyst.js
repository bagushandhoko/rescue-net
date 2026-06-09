const RN_API_BASE = "http://192.168.100.32:8092";

function statusMsg(msg) {
  const el = document.getElementById("aiStatus");
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
  return document.getElementById("aiAskForm");
}

function renderContextSummary(summary) {
  const el = document.getElementById("contextSummary");
  if (!summary) {
    el.innerHTML = `<div><span>Status</span><b>No summary</b></div>`;
    return;
  }

  el.innerHTML = Object.entries(summary).map(([k, v]) => `
    <div><span>${k}</span><b>${v}</b></div>
  `).join("");
}

async function loadContextSummary() {
  const form = getForm();
  const disasterId = form.disaster_event_id.value.trim();

  statusMsg("Loading AI context summary...");
  const ctx = await api(`/ai/context/${encodeURIComponent(disasterId)}`);

  renderContextSummary(ctx.summary || {});
  statusMsg("Context summary loaded.");
}

async function askAi(e) {
  e.preventDefault();

  const form = getForm();

  const payload = {
    user_id: form.user_id.value.trim(),
    disaster_event_id: form.disaster_event_id.value.trim(),
    provider: form.provider.value,
    question: form.question.value.trim()
  };

  statusMsg("Asking AI Analyst...");
  document.getElementById("answerTitle").textContent = "Processing...";
  document.getElementById("aiAnswer").textContent = "AI is analyzing Rescue-Net context...";

  const data = await api("/ai/ask", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  document.getElementById("answerTitle").textContent = "AI Analyst Response";
  document.getElementById("aiAnswer").textContent = data.answer || "No answer.";
  document.getElementById("keyUsed").textContent = data.key_used || "BYOK";

  renderContextSummary(data.context_summary || {});
  statusMsg("AI answer ready.");
}

document.addEventListener("DOMContentLoaded", () => {
  const form = getForm();
  form.addEventListener("submit", e => {
    askAi(e).catch(err => {
      statusMsg(err.message);
      document.getElementById("answerTitle").textContent = "AI request failed";
      document.getElementById("aiAnswer").textContent = err.message;
    });
  });

  document.getElementById("loadContextBtn").addEventListener("click", () => {
    loadContextSummary().catch(err => statusMsg(err.message));
  });

  loadContextSummary().catch(err => statusMsg(err.message));
});
