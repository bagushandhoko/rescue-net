const RN_API_BASE = (location.protocol === "https:" ? location.origin + "/rescue-net-api" : "http://192.168.100.32:8092");

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

function chip(type) {
  if (type === "official" || type === "official_verified") return "danger";
  if (type === "trusted" || type === "local_trusted") return "warning";
  return "neutral";
}

async function loadEcosystem() {
  const disasterId = "event-aceh-2025";
  const status = document.querySelector("[data-eco-status]");

  try {
    if (status) status.textContent = "Loading ecosystem data...";

    const [members, resources, shares, requests] = await Promise.all([
      rnFetch(`/ecosystem-members/${disasterId}`),
      rnFetch(`/resources/${disasterId}`),
      rnFetch(`/resource-shares/${disasterId}`),
      rnFetch(`/resource-requests`)
    ]);

    renderMembers(members);
    renderResources(resources);
    renderShares(shares);
    renderRequests(requests);

    if (status) status.textContent = `Loaded ${members.length} members, ${resources.length} resources, ${requests.length} requests.`;
  } catch (err) {
    if (status) status.textContent = err.message;
  }
}

function renderMembers(items) {
  const target = document.querySelector("[data-eco-members]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(m => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${m.member_id}</h4>
          <p>${m.member_type} · role: ${m.role_in_disaster}</p>
          <p>verification: ${m.verification_status}</p>
        </div>
        <div class="chips">
          <span class="chip ${chip(m.trust_level)}">${m.trust_level}</span>
          <span class="chip neutral">${m.status}</span>
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada ecosystem member</h4></article>`;
}

function renderResources(items) {
  const target = document.querySelector("[data-eco-resources]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(r => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${r.name}</h4>
          <p>${r.resource_type} · owner: ${r.owner_type}/${r.owner_id}</p>
          <p>${r.description || ""}</p>
          <p>location: ${r.location || "n/a"}</p>
        </div>
        <div class="chips">
          <span class="chip ${chip(r.trust_level)}">${r.trust_level}</span>
          <span class="chip neutral">${r.visibility_scope}</span>
          <span class="chip warning">${r.access_policy}</span>
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada shared resource</h4></article>`;
}

function renderShares(items) {
  const target = document.querySelector("[data-eco-shares]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(s => `
    <article class="event-card">
      <h4>${s.resource_name || s.resource_id}</h4>
      <p>${s.resource_type || "resource"} · owner: ${s.owner_id || "n/a"}</p>
      <p>shared scope: ${s.shared_to_scope} · access: ${s.access_policy}</p>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada resource share</h4></article>`;
}

function renderRequests(items) {
  const target = document.querySelector("[data-eco-requests]");
  if (!target) return;

  target.innerHTML = items.length ? items.map(r => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${r.resource_name || r.resource_id}</h4>
          <p>requested by: ${r.requested_by_type}/${r.requested_by_id}</p>
          <p>${r.request_reason || ""}</p>
          <p>time: ${r.requested_time || "n/a"}</p>
        </div>
        <div class="chips">
          <span class="chip warning">${r.status}</span>
          <span class="chip neutral">${r.id}</span>
        </div>
      </div>
    </article>
  `).join("") : `<article class="event-card"><h4>Belum ada resource request</h4></article>`;
}

function setupRequestForm() {
  const form = document.querySelector("[data-resource-request-form]");
  const msg = document.querySelector("[data-resource-request-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      resource_id: form.resource_id.value.trim(),
      requested_by_type: form.requested_by_type.value.trim(),
      requested_by_id: form.requested_by_id.value.trim(),
      request_reason: form.request_reason.value.trim(),
      requested_quantity: Number(form.requested_quantity.value || 1),
      requested_time: form.requested_time.value.trim()
    };

    try {
      if (msg) msg.textContent = "Mengirim request...";
      await rnFetch("/resource-requests", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      if (msg) msg.textContent = "Resource request berhasil dibuat.";
      await loadEcosystem();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadEcosystem();
  setupRequestForm();

  const btn = document.querySelector("[data-refresh-ecosystem]");
  if (btn) btn.addEventListener("click", loadEcosystem);
});
