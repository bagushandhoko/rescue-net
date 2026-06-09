const RN_API_BASE = "http://192.168.100.32:8092";
let SF_CONTEXT_CACHE = null;

function statusMsg(msg) {
  const el = document.getElementById("sfStatus");
  if (el) el.textContent = msg;
}

function getDisasterId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event") || "event-aceh-2025";
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
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

function renderMissing(items) {
  const el = document.getElementById("missingReports");
  el.innerHTML = items.length ? items.map(m => card(
    `${m.person_code} · ${safe(m.person_name)}`,
    `Last seen: ${safe(m.last_seen_location)} · ${safe(m.last_seen_time)}<br>Reporter: ${safe(m.reporter_relation)} · ${safe(m.reporter_contact)}<br>${safe(m.description)}<br>Clothing: ${safe(m.clothing_description)}`,
    m.status
  )).join("") : card("Belum ada laporan hilang", "Tambahkan missing report.", "empty");
}

function renderFound(items) {
  const el = document.getElementById("foundReports");
  el.innerHTML = items.length ? items.map(f => card(
    `${f.person_code} · ${safe(f.person_name)}`,
    `Found: ${safe(f.found_location)} · ${safe(f.found_time)}<br>Current: ${safe(f.current_location)}<br>Condition: ${safe(f.condition_notes)}<br>Clothing: ${safe(f.clothing_description)}`,
    f.status
  )).join("") : card("Belum ada laporan ditemukan", "Tambahkan found report.", "empty");
}


function renderMatches(items) {
  const el = document.getElementById("matches");
  el.innerHTML = items.length ? items.map(m => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(m.missing_person_code)} ↔ ${safe(m.found_person_code)}</h4>
          <p>Score: ${safe(m.match_score)}<br>Reason: ${safe(m.match_reason)}<br>Missing: ${safe(m.missing_person_name)} · Found: ${safe(m.found_person_name)}</p>
        </div>
        <div class="chips">
          <span class="chip warning">${m.status}</span>
          ${m.status !== "reunited" ? `<button class="btn primary" type="button" onclick="updateMatchStatus('${m.id}', 'reunited')">Mark Reunited</button>` : ""}
          ${m.status === "candidate" ? `<button class="btn" type="button" onclick="updateMatchStatus('${m.id}', 'investigating')">Investigating</button>` : ""}
          ${m.status !== "rejected" && m.status !== "reunited" ? `<button class="btn" type="button" onclick="updateMatchStatus('${m.id}', 'rejected')">Reject</button>` : ""}
        </div>
      </div>
    </article>
  `).join("") : card("Belum ada match", "Match bisa dibuat manual/AI-ready nanti.", "empty");
}

async function updateMatchStatus(matchId, status) {
  const notes = status === "reunited"
    ? prompt("Reunion notes", "Keluarga sudah dikonfirmasi dan dipertemukan.")
    : prompt("Review notes", "");

  statusMsg("Updating match status...");
  await api(`/search-found-matches/${matchId}/status`, {
    method: "POST",
    body: JSON.stringify({
      status,
      reviewed_by: "search-found-operator",
      reunion_notes: notes || ""
    })
  });

  statusMsg("Match status updated.");
  await loadSearchFound();
}


async function loadSearchFound() {
  const disasterId = getDisasterId();
  statusMsg("Loading Search & Found context...");

  const ctx = await api(`/search-found-context/${disasterId}`);
  SF_CONTEXT_CACHE = ctx;

  const missing = ctx.missing_person_reports || [];
  const found = ctx.found_person_reports || [];
  const matches = ctx.matches || [];
  const summary = ctx.summary || {};

  document.getElementById("kpiMissing").textContent = summary.missing_count || missing.length;
  document.getElementById("kpiFound").textContent = summary.found_count || found.length;
  document.getElementById("kpiMatches").textContent = summary.match_count || matches.length;
  document.getElementById("kpiReunited").textContent = summary.reunited_count || 0;

  renderMissing(missing);
  renderFound(found);
  renderMatches(matches);
  renderManualMatchPanel();

  const missingForm = document.getElementById("missingForm");
  if (missingForm && missingForm.disaster_event_id) missingForm.disaster_event_id.value = disasterId;

  statusMsg("Loaded: " + ctx.generated_at);
}

function setupMissingForm() {
  const form = document.getElementById("missingForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      reporter_name: form.reporter_name.value.trim(),
      reporter_contact: form.reporter_contact.value.trim(),
      reporter_relation: form.reporter_relation.value.trim(),
      person_code: form.person_code.value.trim(),
      person_name: form.person_name.value.trim(),
      age_group: form.age_group.value.trim(),
      gender: form.gender.value.trim(),
      last_seen_location: form.last_seen_location.value.trim(),
      last_seen_time: form.last_seen_time.value.trim(),
      description: form.description.value.trim(),
      clothing_description: form.clothing_description.value.trim(),
      special_notes: form.special_notes.value.trim(),
      created_by_user_id: "search-found-operator"
    };

    statusMsg("Saving missing report...");
    await api("/missing-person-reports", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    statusMsg("Missing report saved.");
    await loadSearchFound();
  });
}

function setupFoundForm() {
  const form = document.getElementById("foundForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const disasterId = getDisasterId();

    const payload = {
      disaster_event_id: disasterId,
      finder_name: form.finder_name.value.trim(),
      finder_contact: form.finder_contact.value.trim(),
      person_code: form.person_code.value.trim(),
      person_name: form.person_name.value.trim(),
      age_group: form.age_group.value.trim(),
      gender: form.gender.value.trim(),
      found_location: form.found_location.value.trim(),
      found_time: form.found_time.value.trim(),
      current_location: form.current_location.value.trim(),
      condition_notes: form.condition_notes.value.trim(),
      description: form.description.value.trim(),
      clothing_description: form.clothing_description.value.trim(),
      created_by_user_id: "search-found-operator"
    };

    statusMsg("Saving found report...");
    await api("/found-person-reports", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    statusMsg("Found report saved.");
    await loadSearchFound();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupMissingForm();
  setupFoundForm();

  const btn = document.getElementById("refreshSf");
  if (btn) btn.addEventListener("click", () => loadSearchFound().catch(err => statusMsg(err.message)));

  loadSearchFound().catch(err => statusMsg(err.message));
});
