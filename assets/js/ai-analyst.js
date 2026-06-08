const RN_API_BASE = "http://192.168.100.32:8092";

async function rnFetch(path) {
  const res = await fetch(`${RN_API_BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return await res.json();
}

function renderSummary(summary) {
  const target = document.querySelector("[data-ai-summary]");
  if (!target) return;

  target.innerHTML = `
    <div class="summary-list">
      <div><span>Posko</span><b>${summary.total_poskos ?? 0}</b></div>
      <div><span>Logistic Needs</span><b>${summary.total_logistic_needs ?? 0}</b></div>
      <div><span>Critical Needs</span><b>${summary.critical_needs ?? 0}</b></div>
      <div><span>Urgent Needs</span><b>${summary.urgent_needs ?? 0}</b></div>
      <div><span>Aid Offers</span><b>${summary.total_aid_offers ?? 0}</b></div>
      <div><span>Need Pickup</span><b>${summary.aid_need_pickup ?? 0}</b></div>
      <div><span>Self Delivery</span><b>${summary.aid_self_delivery_planned ?? 0}</b></div>
      <div><span>Transport</span><b>${summary.available_transport_spaces ?? 0}</b></div>
      <div><span>Distribution Flows</span><b>${summary.distribution_flows ?? 0}</b></div>
      <div><span>Volunteers Listed</span><b>${summary.volunteers_listed ?? 0}</b></div>
    </div>
  `;
}

function renderAlerts(alerts) {
  const target = document.querySelector("[data-ai-alerts]");
  if (!target) return;

  if (!alerts || alerts.length === 0) {
    target.innerHTML = `<article class="event-card"><h4>Tidak ada alert</h4><p>Belum ada peringatan kritis dari data saat ini.</p></article>`;
    return;
  }

  target.innerHTML = alerts.map(a => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${a.type}</h4>
          <p>${a.message}</p>
        </div>
        <div class="chips">
          <span class="chip ${a.level === "critical" ? "danger" : "warning"}">${a.level}</span>
          <span class="chip neutral">${a.source_table}/${a.source_id}</span>
        </div>
      </div>
    </article>
  `).join("");
}

function renderRecommendations(recommendations) {
  const target = document.querySelector("[data-ai-recommendations]");
  if (!target) return;

  if (!recommendations || recommendations.length === 0) {
    target.innerHTML = `<article class="event-card"><h4>Belum ada rekomendasi</h4><p>Data belum cukup untuk membuat rekomendasi otomatis.</p></article>`;
    return;
  }

  target.innerHTML = recommendations.map(r => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>Recommendation · ${r.priority}</h4>
          <p>${r.message}</p>
        </div>
        <div class="chips">
          <span class="chip ${r.priority === "high" ? "danger" : "neutral"}">${r.priority}</span>
        </div>
      </div>
    </article>
  `).join("");
}

function renderSources(sources) {
  const target = document.querySelector("[data-ai-sources]");
  if (!target) return;

  const limited = (sources || []).slice(0, 20);

  target.innerHTML = limited.map(s => `
    <div class="source-row">
      <span>${s.source_table}</span>
      <b>${s.source_id}</b>
    </div>
  `).join("");
}

async function loadAIContext() {
  const status = document.querySelector("[data-ai-status]");
  const disasterSelect = document.querySelector("[data-ai-disaster]");
  const disasterId = disasterSelect ? disasterSelect.value : "event-aceh-2025";

  try {
    if (status) status.textContent = "Loading AI context...";
    const data = await rnFetch(`/ai/context/${disasterId}`);

    const title = document.querySelector("[data-ai-disaster-title]");
    if (title && data.disaster) {
      title.textContent = `${data.disaster.name} · ${data.disaster.location}`;
    }

    renderSummary(data.summary || {});
    renderAlerts(data.alerts || []);
    renderRecommendations(data.recommendations || []);
    renderSources(data.sources || []);

    if (status) status.textContent = `Context generated at ${data.generated_at}`;
  } catch (err) {
    if (status) status.textContent = err.message;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadAIContext();

  const btn = document.querySelector("[data-refresh-ai-context]");
  if (btn) btn.addEventListener("click", loadAIContext);

  const disasterSelect = document.querySelector("[data-ai-disaster]");
  if (disasterSelect) disasterSelect.addEventListener("change", loadAIContext);
});
