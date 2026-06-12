const RN_API_BASE = "http://192.168.100.32:8092";

async function rnFetch(path, options = {}) {
  const res = await fetch(`${RN_API_BASE}${path}`, {
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

function severityClass(severity) {
  if (severity === "critical") return "danger";
  if (severity === "urgent") return "warning";
  return "neutral";
}

function setText(selector, value) {
  const el = document.querySelector(selector);
  if (el) el.textContent = value;
}

function formatNumber(value) {
  return new Intl.NumberFormat("id-ID").format(Number(value || 0));
}

async function loadActiveDisasters() {
  const target = document.querySelector("[data-rn-disasters]");
  if (!target) return;

  try {
    const disasters = await rnFetch("/disasters");

    target.innerHTML = disasters.map((d, index) => `
      <article class="event-card ${index === 0 ? "selected" : ""}" onclick="window.location.href=\`pages/disaster-detail.html?id=${d.id}\`" style="cursor:pointer">
        <div class="event-main">
          <div>
            <h4>${index === 0 ? "▾" : "▸"} ${d.name}</h4>
            <p>${d.location} · <b class="text-${severityClass(d.severity)}">${d.severity}</b> · ${d.status}</p>
          </div>
          <div class="chips">
            <span class="chip ${severityClass(d.severity)}">${d.disaster_type}</span>
            <span class="chip neutral">${d.id}</span>
          </div>
        </div>
      </article>
    `).join("");

  } catch (err) {
    target.innerHTML = `
      <article class="event-card">
        <h4>API belum terbaca</h4>
        <p>${err.message}</p>
      </article>
    `;
  }
}

async function loadWelcomeLiveMetrics() {
  if (!document.body.classList.contains("home-page")) return;

  try {
    const [disasters, ctx] = await Promise.all([
      rnFetch("/disasters"),
      rnFetch("/ai/context/event-sim-001")
    ]);
    const summary = ctx.summary || {};
    const critical = disasters.filter(d => d.severity === "critical").length;
    const needs = Number(summary.open_logistic_need_count || 0) + Number(summary.shelter_need_count || 0);
    const blockedFlows = (ctx.distribution_flows || []).filter(f => {
      const status = String(f.status || "").toLowerCase();
      return status.includes("blocked") || status.includes("delayed") || status.includes("pending");
    }).length;

    setText("[data-rn-live-active-disasters]", formatNumber(disasters.length));
    setText("[data-rn-live-active-note]", `${critical} critical`);
    setText("[data-rn-live-critical-needs]", formatNumber(needs));
    setText("[data-rn-live-volunteers]", formatNumber(summary.volunteer_count || 0));
    setText("[data-rn-live-blocked-flows]", formatNumber(blockedFlows || summary.distribution_flow_count || 0));

    setText("[data-rn-live-severity]", critical > 0 ? "CRITICAL" : "ACTIVE");
    setText("[data-rn-live-posko]", formatNumber(summary.posko_count || 0));
    setText("[data-rn-live-organizations]", formatNumber(summary.organization_count || 0));
    setText("[data-rn-live-logistic-needs]", formatNumber(summary.open_logistic_need_count || 0));
    setText("[data-rn-live-aid-offers]", formatNumber(summary.aid_offer_count || 0));
    setText("[data-rn-live-distribution-flows]", formatNumber(summary.distribution_flow_count || 0));
    setText("[data-rn-live-sources]", formatNumber((ctx.sources || []).length));

  } catch (err) {
    setText("[data-rn-live-active-note]", "API belum terbaca");
    console.error("[Welcome Metrics]", err);
  }
}

function setupCreateDisasterForm() {
  const form = document.querySelector("[data-rn-create-disaster]");
  const msg = document.querySelector("[data-rn-form-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      name: form.name.value.trim(),
      disaster_type: form.disaster_type.value.trim(),
      location: form.location.value.trim(),
      severity: form.severity.value,
      status: "active"
    };

    if (!payload.name || !payload.disaster_type || !payload.location) {
      if (msg) msg.textContent = "Lengkapi nama, jenis, dan lokasi bencana.";
      return;
    }

    try {
      if (msg) msg.textContent = "Menyimpan...";
      await rnFetch("/disasters", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      form.reset();
      if (msg) msg.textContent = "Bencana berhasil ditambahkan ke PostgreSQL.";
      await loadActiveDisasters();

    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}


function setupQuickEventButtons() {
  const form = document.querySelector("[data-rn-create-disaster]");
  if (!form) return;

  document.querySelectorAll("[data-fill-event]").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.getAttribute("data-fill-event");

      if (type === "earthquake") {
        form.name.value = "Gempa Aceh Barat 2026";
        form.disaster_type.value = "earthquake";
        form.location.value = "Aceh Barat, Aceh";
        form.severity.value = "critical";
      }

      if (type === "flood") {
        form.name.value = "Banjir Luwu 2026";
        form.disaster_type.value = "flood";
        form.location.value = "Luwu Utara, Sulawesi Selatan";
        form.severity.value = "urgent";
      }

      if (type === "landslide") {
        form.name.value = "Longsor Bogor 2026";
        form.disaster_type.value = "landslide";
        form.location.value = "Bogor, Jawa Barat";
        form.severity.value = "urgent";
      }
    });
  });
}


document.addEventListener("DOMContentLoaded", () => {
  loadActiveDisasters();
  loadWelcomeLiveMetrics();
  setupCreateDisasterForm();
  setupQuickEventButtons();
});
