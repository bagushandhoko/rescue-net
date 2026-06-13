const RN_API_BASE = window.RN_API_BASE || (location.protocol === "https:" ? location.origin + "/rescue-net-api" : "http://192.168.100.32:8092");

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

function buildOperationalRecommendations(ctx, resources, recoveryProjects) {
  const s = ctx.summary || {};
  const recommendations = [];

  const unavailableResources = resources.filter(r => r.status && r.status !== "available");
  const transportAssets = resources.filter(r => ["transport", "vehicle"].includes(String(r.resource_type || r.category || "").toLowerCase()));
  const medicalAssets = resources.filter(r => String(r.resource_type || r.category || "").toLowerCase().includes("medical"));
  const recoveryActive = recoveryProjects.filter(p => !["completed", "cancelled"].includes(String(p.status || "").toLowerCase()));

  if (Number(s.open_logistic_need_count || 0) > 0 && transportAssets.length > 0) {
    recommendations.push(`Gunakan ${transportAssets.length} aset transport terdaftar untuk prioritas open logistic needs. Cocokkan kapasitas dan PIC sebelum assignment.`);
  }

  if (Number(s.medical_case_count || 0) > 0 && medicalAssets.length > 0) {
    recommendations.push(`Ada ${s.medical_case_count} kasus medis dan ${medicalAssets.length} resource medis terdata. Prioritaskan ketersediaan stok medis dan rujukan pasien berat.`);
  }

  if (unavailableResources.length > 0) {
    recommendations.push(`${unavailableResources.length} resource tidak available. Command center perlu cek status ketersediaan sebelum membuat rencana distribusi.`);
  }

  if (recoveryActive.length > 0) {
    recommendations.push(`${recoveryActive.length} recovery/reconstruction project aktif. Sinkronkan kebutuhan alat kerja, relawan teknis, evidence, dan verifikasi progress.`);
  }

  if (Number(s.shelter_need_count || 0) > 0 && Number(s.shelter_occupancy_count || 0) > 0) {
    recommendations.push(`Shelter memiliki kebutuhan terbuka. Bandingkan occupancy, kapasitas, air, sanitasi, dan distribusi bantuan sebelum perpindahan pengungsi.`);
  }

  return recommendations;
}

function renderResourceRecoverySources(resources, recoveryProjects) {
  const resourceCards = resources.slice(0, 8).map(r => card(
    safe(r.resource_name),
    `Type: ${safe(r.resource_type)}<br>Owner: ${safe(r.owner_type)} / ${safe(r.owner_id)}<br>Status: ${safe(r.status)}<br>Capacity: ${safe(r.capacity_description)}`,
    "resource"
  ));

  const recoveryCards = recoveryProjects.slice(0, 8).map(p => card(
    safe(p.project_name),
    `Type: ${safe(p.project_type)}<br>Location: ${safe(p.location)}<br>Progress: ${safe(p.progress_percent)}%<br>Status: ${safe(p.status)}`,
    "recovery"
  ));

  return [...resourceCards, ...recoveryCards];
}

async function loadAiContext() {
  const eventId = getEventId();
  setText("aiStatus", "Loading AI context...");

  const [ctx, resources, recoveryProjects] = await Promise.all([
    api(`/ai/context/${eventId}`),
    api(`/resource-profiles?disaster_event_id=${encodeURIComponent(eventId)}`),
    api(`/recovery-projects?disaster_event_id=${encodeURIComponent(eventId)}`)
  ]);
  const s = ctx.summary || {};
  const operationalRecommendations = buildOperationalRecommendations(ctx, resources || [], recoveryProjects || []);
  const combinedRecommendations = [
    ...(ctx.recommendations || []),
    ...operationalRecommendations
  ];

  setText("aiKpiPosko", safe(s.posko_count));
  setText("aiKpiNeeds", Number(s.open_logistic_need_count || 0) + Number(s.shelter_need_count || 0));
  setText("aiKpiAlerts", (ctx.alerts || []).length);
  setText("aiKpiPrograms", Number(s.donor_program_count || 0) + Number((recoveryProjects || []).length));

  document.getElementById("aiAlerts").innerHTML = (ctx.alerts || []).length
    ? ctx.alerts.slice(0, 10).map(a => card(
        `${safe(a.type)} · ${safe(a.level)}`,
        `${safe(a.message)}<br>Source: ${safe(a.source_table)} / ${safe(a.source_id)}`,
        safe(a.level)
      )).join("")
    : card("No alerts", "Belum ada alert.", "ok");

  document.getElementById("aiRecommendations").innerHTML = combinedRecommendations.length
    ? combinedRecommendations.map((r, i) => card(`Recommendation ${i + 1}`, r, i < (ctx.recommendations || []).length ? "AI" : "Ops")).join("")
    : card("No recommendation", "Belum ada rekomendasi.", "empty");

  const sourceCards = (ctx.sources || []).slice(0, 20).map(src => card(
        safe(src.source_table),
        `ID: ${safe(src.source_id)}`,
        "source"
      ));
  const resourceRecoveryCards = renderResourceRecoverySources(resources || [], recoveryProjects || []);

  document.getElementById("aiSources").innerHTML = (sourceCards.length || resourceRecoveryCards.length)
    ? [...sourceCards, ...resourceRecoveryCards].join("")
    : card("No sources", "Belum ada source.", "empty");

  setText("aiStatus", `AI context loaded: ${safe(ctx.generated_at)} | resources=${(resources || []).length} | recovery=${(recoveryProjects || []).length}`);
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
