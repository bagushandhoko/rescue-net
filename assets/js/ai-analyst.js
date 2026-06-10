const RN_API_BASE = window.RN_API_BASE || "http://192.168.100.32:8092";

function getEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || params.get("id") || "event-sim-001";
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function card(title, body, chip = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">${chip ? `<span class="chip warning">${chip}</span>` : ""}</div>
      </div>
    </article>
  `;
}

async function loadAiContext() {
  const eventId = getEventId();
  setText("aiStatus", "Loading AI context...");

  const ctx = await api(`/ai/context/${eventId}`);
  const s = ctx.summary || {};

  setText("aiKpiPosko", safe(s.posko_count));
  setText("aiKpiNeeds", Number(s.open_logistic_need_count || 0) + Number(s.shelter_need_count || 0));
  setText("aiKpiAlerts", (ctx.alerts || []).length);
  setText("aiKpiPrograms", safe(s.donor_program_count));

  document.getElementById("aiAlerts").innerHTML = (ctx.alerts || []).length
    ? ctx.alerts.slice(0, 10).map(a => card(
        `${safe(a.type)} · ${safe(a.level)}`,
        `${safe(a.message)}<br>Source: ${safe(a.source_table)} / ${safe(a.source_id)}`,
        safe(a.level)
      )).join("")
    : card("No alerts", "Belum ada alert.", "ok");

  document.getElementById("aiRecommendations").innerHTML = (ctx.recommendations || []).length
    ? ctx.recommendations.map((r, i) => card(`Recommendation ${i + 1}`, r, "AI")).join("")
    : card("No recommendation", "Belum ada rekomendasi.", "empty");

  document.getElementById("aiSources").innerHTML = (ctx.sources || []).length
    ? ctx.sources.slice(0, 20).map(src => card(
        safe(src.source_table),
        `ID: ${safe(src.source_id)}`,
        "source"
      )).join("")
    : card("No sources", "Belum ada source.", "empty");

  setText("aiStatus", `AI context loaded: ${safe(ctx.generated_at)}`);
}

function setupAiAsk() {
  const form = document.getElementById("aiAskForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();
    setText("aiAnswer", "Asking AI...");

    try {
      const payload = {
        user_id: form.user_id.value.trim(),
        disaster_event_id: getEventId(),
        provider: "openai",
        question: form.question.value.trim()
      };

      const res = await api("/ai/ask", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      setText("aiAnswer", res.answer || res.message || JSON.stringify(res, null, 2));
    } catch (err) {
      setText("aiAnswer", err.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupAiAsk();

  const refresh = document.getElementById("refreshAiContext");
  if (refresh) refresh.addEventListener("click", () => loadAiContext().catch(err => setText("aiStatus", err.message)));

  loadAiContext().catch(err => setText("aiStatus", err.message));
});
