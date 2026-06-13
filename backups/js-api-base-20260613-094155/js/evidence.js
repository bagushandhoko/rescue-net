const RN_API_BASE = "http://192.168.100.32:8092";
const params = new URLSearchParams(window.location.search);
const DISASTER_ID = params.get("event") || params.get("disaster_event_id") || "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("evidenceStatus");
  if (el) el.textContent = msg;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, options);
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
        <div class="chips">
          ${chip ? `<span class="chip warning">${chip}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderEvidence(items) {
  const el = document.getElementById("evidenceList");
  if (!el) return;

  el.innerHTML = items.length ? items.map(e => {
    const fileUrl = e.file_url || e.url || e.path || "";
    const link = fileUrl ? `<br><a href="${fileUrl}" target="_blank">Open File</a>` : "";
    return card(
      `${safe(e.evidence_type)} · ${safe(e.linked_object_type)}`,
      `Object: ${safe(e.linked_object_id)}<br>
       Disaster: ${safe(e.disaster_event_id)}<br>
       Node: ${safe(e.node_id)}<br>
       Uploaded by: ${safe(e.uploaded_by)}<br>
       File: ${safe(e.filename || e.original_filename || e.file_path)}${link}`,
      safe(e.created_at)
    );
  }).join("") : card("Belum ada evidence", "Upload foto/dokumen bukti untuk object terkait.", "empty");
}

async function loadEvidence() {
  statusMsg("Loading evidence...");
  const data = await api("/evidence");
  const items = Array.isArray(data) ? data : (data.evidence || data.items || []);
  renderEvidence(items);
  statusMsg(`Loaded ${items.length} evidence item(s).`);
}

function applyEvidenceDeepLink(form) {
  if (!form) return;

  const objectType = params.get("object_type") || params.get("linked_object_type");
  const objectId = params.get("object_id") || params.get("linked_object_id");
  const nodeId = params.get("node") || params.get("node_id");

  form.disaster_event_id.value = DISASTER_ID;
  if (nodeId) form.node_id.value = nodeId;
  if (objectType) form.linked_object_type.value = objectType;
  if (objectId) form.linked_object_id.value = objectId;
}

function setupUploadForm() {
  const form = document.getElementById("evidenceForm");
  if (!form) return;

  applyEvidenceDeepLink(form);

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const fd = new FormData();
    fd.append("file", form.file.files[0]);
    fd.append("disaster_event_id", form.disaster_event_id.value.trim());
    fd.append("node_id", form.node_id.value.trim());
    fd.append("linked_object_type", form.linked_object_type.value.trim());
    fd.append("linked_object_id", form.linked_object_id.value.trim());
    fd.append("evidence_type", form.evidence_type.value.trim());
    fd.append("uploaded_by", form.uploaded_by.value.trim());

    statusMsg("Uploading evidence...");
    await api("/evidence/upload", {
      method: "POST",
      body: fd
    });

    form.reset();
    applyEvidenceDeepLink(form);
    statusMsg("Evidence uploaded.");
    await loadEvidence();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupUploadForm();

  const btn = document.getElementById("refreshEvidence");
  if (btn) btn.addEventListener("click", () => loadEvidence().catch(err => statusMsg(err.message)));

  loadEvidence().catch(err => statusMsg(err.message));
});
