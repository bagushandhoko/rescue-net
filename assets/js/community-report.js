const RN_API_BASE = "http://192.168.100.32:8092";

async function rnFetch(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return await res.json();
}

function trustLabel(score) {
  if (score >= 86) return "verified/trusted";
  if (score >= 61) return "high confidence";
  if (score >= 31) return "medium confidence";
  return "low confidence";
}

function reportCard(report) {
  return `
    <article class="event-card community-report-item">
      <div class="event-main">
        <div>
          <h4>${report.title}</h4>
          <p>${report.location_text} ?? <b>${report.report_type}</b> ?? ${report.status}</p>
          <p>${report.description}</p>
          <small>${report.reporter_role} ?? ${trustLabel(report.trust_score)} (${report.trust_score})</small>
        </div>
        <div class="chips">
          <span class="chip ${report.priority === "critical" ? "danger" : report.priority === "urgent" ? "warning" : "neutral"}">${report.priority}</span>
          <span class="chip neutral">${report.id}</span>
        </div>
      </div>
      <div class="community-report-actions">
        <button class="btn" type="button" data-report-action="needs_verification" data-report-id="${report.id}">Triage</button>
        <button class="btn" type="button" data-report-action="verified" data-report-id="${report.id}">Verify</button>
        <button class="btn" type="button" data-report-action="escalated" data-report-id="${report.id}">Escalate</button>
        <button class="btn" type="button" data-report-action="rejected" data-report-id="${report.id}">Reject</button>
        <button class="btn primary" type="button" data-report-convert="${report.id}">Convert Logistik</button>
      </div>
    </article>
  `;
}

async function loadCommunityReports() {
  const target = document.querySelector("[data-community-report-list]");
  if (!target) return;
  target.innerHTML = "<p class=\"subtitle\">Loading laporan masyarakat...</p>";
  try {
    const status = document.querySelector("[data-community-status-filter]")?.value || "";
    const reports = await rnFetch(`/community-reports?disaster_event_id=event-sim-001${status ? `&status=${status}` : ""}`);
    target.innerHTML = reports.length
      ? reports.map(reportCard).join("")
      : "<p class=\"subtitle\">Belum ada laporan pada filter ini.</p>";
  } catch (err) {
    target.innerHTML = `<p class="subtitle">${err.message}</p>`;
  }
}

function setupCommunityReportForm() {
  const form = document.querySelector("[data-community-report-form]");
  const msg = document.querySelector("[data-community-report-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      disaster_event_id: "event-sim-001",
      reporter_name: form.reporter_name.value.trim(),
      reporter_phone: form.reporter_phone.value.trim(),
      reporter_role: form.reporter_role.value,
      reporter_verification_level: form.reporter_phone.value.trim() ? "phone_verified" : "anonymous",
      report_type: form.report_type.value,
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      location_text: form.location_text.value.trim(),
      affected_people_count: Number(form.affected_people_count.value || 0),
      priority: form.priority.value,
      urgent_needs: form.urgent_needs.value.trim(),
      evidence_url: form.evidence_url.value.trim(),
      evidence_caption: form.evidence_caption.value.trim(),
      consent_to_contact: form.consent_to_contact.checked
    };

    if (!payload.reporter_name || !payload.title || !payload.description || !payload.location_text) {
      if (msg) msg.textContent = "Lengkapi nama, judul, lokasi, dan deskripsi laporan.";
      return;
    }

    try {
      if (msg) msg.textContent = "Mengirim laporan...";
      const data = await rnFetch("/public/community-reports", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      form.reset();
      if (msg) msg.textContent = `Laporan masuk: ${data.community_report.id}. Status awal submitted/belum terverifikasi.`;
      await loadCommunityReports();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

function setupCommunityReportActions() {
  document.addEventListener("click", async (e) => {
    const statusButton = e.target.closest("[data-report-action]");
    const convertButton = e.target.closest("[data-report-convert]");

    if (statusButton) {
      const id = statusButton.getAttribute("data-report-id");
      const status = statusButton.getAttribute("data-report-action");
      await rnFetch(`/community-reports/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          verifier_id: "operator-web",
          verifier_role: "command_center",
          notes: `Marked ${status} from operator UI`
        })
      });
      await loadCommunityReports();
    }

    if (convertButton) {
      const id = convertButton.getAttribute("data-report-convert");
      await rnFetch(`/community-reports/${id}/convert`, {
        method: "POST",
        body: JSON.stringify({
          target_type: "logistic_need",
          quantity_needed: 1,
          unit: "paket",
          notes: "Converted from Laporan Masyarakat"
        })
      });
      await loadCommunityReports();
    }
  });

  document.querySelector("[data-community-status-filter]")?.addEventListener("change", loadCommunityReports);
}

document.addEventListener("DOMContentLoaded", () => {
  setupCommunityReportForm();
  setupCommunityReportActions();
  loadCommunityReports();
});

