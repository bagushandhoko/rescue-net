const RN_API_BASE = "http://192.168.100.32:8092";
const DISASTER_ID = "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("mapStatus");
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

function mapLinks(p) {
  if (p.latitude === null || p.latitude === undefined || p.longitude === null || p.longitude === undefined) {
    return "";
  }
  const lat = p.latitude;
  const lng = p.longitude;
  return `<br><a target="_blank" href="https://www.google.com/maps?q=${lat},${lng}">Google Maps</a> · <a target="_blank" href="https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=15/${lat}/${lng}">OpenStreetMap</a>`;
}

function card(title, body, chip = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">
          ${chip ? `<span class="chip warning">${chip}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderSummary(summary) {
  const el = document.getElementById("mapSummary");
  if (!el) return;

  el.innerHTML = `
    <div><span>Total Points</span><b>${summary.point_count || 0}</b></div>
    <div><span>With Coordinates</span><b>${summary.with_coordinates_count || 0}</b></div>
    <div><span>Posko</span><b>${summary.posko_count || 0}</b></div>
    <div><span>Work Tools</span><b>${summary.work_tool_count || 0}</b></div>
    <div><span>Missing</span><b>${summary.missing_count || 0}</b></div>
    <div><span>Found</span><b>${summary.found_count || 0}</b></div>
  `;
}

function renderPoints(points) {
  const el = document.getElementById("mapPoints");
  if (!el) return;

  el.innerHTML = points.length ? points.map(p => card(
    `${safe(p.label)} · ${safe(p.object_type)}`,
    `Location: ${safe(p.location_text)}<br>
     Coordinates: ${safe(p.latitude)}, ${safe(p.longitude)}<br>
     Object: ${safe(p.object_id)}<br>
     Status: ${safe(p.point_status)}<br>
     Description: ${safe(p.description)}${mapLinks(p)}`,
    safe(p.priority || p.point_status)
  )).join("") : card("Belum ada map point", "Tambahkan titik peta atau isi data posko/lokasi.", "empty");
}

async function loadMap() {
  statusMsg("Loading map context...");
  const ctx = await api(`/map-context/${DISASTER_ID}`);
  renderSummary(ctx.summary || {});
  renderPoints(ctx.points || []);
  statusMsg("Loaded: " + ctx.generated_at);
}

function setupForm() {
  const form = document.getElementById("mapPointForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: DISASTER_ID,
      object_type: form.object_type.value.trim(),
      object_id: form.object_id.value.trim() || null,
      label: form.label.value.trim(),
      description: form.description.value.trim(),
      latitude: form.latitude.value ? Number(form.latitude.value) : null,
      longitude: form.longitude.value ? Number(form.longitude.value) : null,
      location_text: form.location_text.value.trim(),
      point_status: form.point_status.value || "active",
      priority: form.priority.value || "normal",
      created_by_user_id: "map-operator"
    };

    statusMsg("Saving map point...");
    await api("/map-points", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    statusMsg("Map point saved.");
    await loadMap();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupForm();
  const btn = document.getElementById("refreshMap");
  if (btn) btn.addEventListener("click", () => loadMap().catch(err => statusMsg(err.message)));
  loadMap().catch(err => statusMsg(err.message));
});
