const RN_FRAPPE_BASE = location.origin + "/rescue-net-frappe/api/method";
let RN_FRAPPE_SESSION = null;

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
    throw new Error(
      data.message ||
      data.exception ||
      `Frappe API error ${res.status}`
    );
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

  const form = document.getElementById("aiAskForm");

  if (form?.user_id) {
    form.user_id.value = RN_FRAPPE_SESSION.user;
    form.user_id.readOnly = true;
  }

  return RN_FRAPPE_SESSION;
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

  const unavailableResources = resources.filter(r => {
    const status = r.availability_status || r.status || "";
    return status && status !== "available";
  });
  const transportAssets = resources.filter(r => ["transport", "vehicle"].includes(String(r.resource_type || r.category || "").toLowerCase()));
  const medicalAssets = resources.filter(r => String(r.resource_type || r.category || "").toLowerCase().includes("medical"));
  const recoveryActive = recoveryProjects.filter(p => !["completed", "cancelled"].includes(String(p.status || "").toLowerCase()));

  if (Number(s.open_need_count ?? s.open_needs_count ?? 0) > 0 && transportAssets.length > 0) {
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
    `Type: ${safe(r.resource_type)}<br>Owner: ${safe(r.owner_type)} / ${safe(r.owner_id)}<br>Status: ${safe(r.availability_status || r.status)}<br>Capacity: ${safe(r.capacity_description)}`,
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

  await ensureSession();

  const ctx = await frappeCall(
    "rescue_net.api_ai.context",
    {
      disaster_event_id: eventId
    }
  );

  const resources = ctx.resource_profiles || [];
  const recoveryProjects = ctx.recovery_projects || [];
  const s = ctx.summary || {};
  const operationalRecommendations = buildOperationalRecommendations(ctx, resources || [], recoveryProjects || []);
  const combinedRecommendations = [
    ...(ctx.recommendations || []),
    ...operationalRecommendations
  ];

  setText("aiKpiPosko", safe(s.posko_count));
  setText(
    "aiKpiNeeds",
    Number(s.open_need_count ?? s.open_needs_count ?? 0)
  );
  setText("aiKpiAlerts", (ctx.alerts || []).length);
  setText(
    "aiKpiPrograms",
    Number(s.program_count || 0) +
    Number(recoveryProjects.length || 0)
  );

  document.getElementById("aiAlerts").innerHTML = (ctx.alerts || []).length
    ? ctx.alerts.slice(0, 10).map(a => card(
        safe(a.type),
        safe(a.message),
        safe(a.level || "alert")
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
      const session = await ensureSession();

      const res = await frappeCall(
        "rescue_net.api_ai.ask",
        {
          user_id: session.user,
          disaster_event_id: getEventId(),
          provider: "openai",
          question: form.question.value.trim()
        },
        true
      );

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
