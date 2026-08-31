const params = new URLSearchParams(window.location.search);
const DISASTER_ID = params.get("event") || params.get("disaster_event_id") || "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("evidenceStatus");
  if (el) el.textContent = msg;
}


async function rnFileToBase64(file) {
  const buffer =
    await file.arrayBuffer();

  const bytes =
    new Uint8Array(buffer);

  let binary = "";

  const chunk = 0x8000;

  for (
    let i = 0;
    i < bytes.length;
    i += chunk
  ) {
    binary +=
      String.fromCharCode(
        ...bytes.subarray(
          i,
          Math.min(
            i + chunk,
            bytes.length
          )
        )
      );
  }

  return btoa(binary);
}


async function api(path, options = {}) {
  const method =
    String(
      options.method || "GET"
    ).toUpperCase();

  const url =
    new URL(
      path,
      location.origin
    );

  if (
    url.pathname === "/evidence"
    && method === "GET"
  ) {
    const params =
      new URLSearchParams(
        location.search
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "evidence_context",
      {
        disaster_event:
          params.get("event")
          || null
      }
    );
  }

  if (
    url.pathname === "/evidence/upload"
    && method === "POST"
  ) {
    if (
      !(
        options.body
        instanceof FormData
      )
    ) {
      throw new Error(
        "Evidence upload membutuhkan FormData."
      );
    }

    const formData =
      options.body;

    const file =
      formData.get("file");

    if (
      !(file instanceof File)
    ) {
      throw new Error(
        "Evidence file tidak ditemukan."
      );
    }

    const contentBase64 =
      await rnFileToBase64(file);

    return await RN_FRAPPE.call(
      "rescue_net.api_frontend_bridge."
      + "upload_evidence",
      {
        filename:
          file.name,

        content_base64:
          contentBase64,

        disaster_event:
          formData.get(
            "disaster_event_id"
          ),

        node_id:
          formData.get(
            "node_id"
          )
          || null,

        linked_object_type:
          formData.get(
            "linked_object_type"
          )
          || null,

        linked_object_id:
          formData.get(
            "linked_object_id"
          )
          || null,

        evidence_type:
          formData.get(
            "evidence_type"
          )
          || "photo",

        uploaded_by:
          formData.get(
            "uploaded_by"
          )
          || null,

        caption:
          formData.get(
            "caption"
          )
          || null
      },
      {
        method: "POST"
      }
    );
  }

  throw new Error(
    "Unsupported Evidence route: "
    + method
    + " "
    + url.pathname
  );
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
