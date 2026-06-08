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

async function loadOrganizations() {
  const target = document.querySelector("[data-rn-organizations]");
  const select = document.querySelector("[data-rn-org-select]");
  if (!target) return;

  try {
    const orgs = await rnFetch("/organizations");

    target.innerHTML = orgs.map(org => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${org.name}</h4>
            <p>${org.organization_type} · ${org.trust_level} · ${org.status}</p>
          </div>
          <div class="chips">
            <span class="chip neutral">${org.id}</span>
          </div>
        </div>
      </article>
    `).join("");

    if (select) {
      select.innerHTML = `<option value="">Mandiri / tanpa organisasi</option>` + orgs.map(org => `
        <option value="${org.id}">${org.name}</option>
      `).join("");
    }

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load organisasi</h4><p>${err.message}</p></article>`;
  }
}

async function loadPoskos() {
  const target = document.querySelector("[data-rn-poskos]");
  if (!target) return;

  try {
    const poskos = await rnFetch("/poskos");

    target.innerHTML = poskos.map(posko => `
      <article class="event-card" onclick="window.location.href='posko-detail.html?id=${posko.id}'" style="cursor:pointer">
        <div class="event-main">
          <div>
            <h4>${posko.name}</h4>
            <p>${posko.node_type} · ${posko.location} · ${posko.verification_status} · ${posko.operational_status}</p>
          </div>
          <div class="chips">
            <span class="chip neutral">${posko.disaster_event_id}</span>
            <span class="chip neutral">${posko.id}</span>
          </div>
        </div>
      </article>
    `).join("");

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load posko</h4><p>${err.message}</p></article>`;
  }
}

function setupOrganizationForm() {
  const form = document.querySelector("[data-rn-create-org]");
  const msg = document.querySelector("[data-rn-org-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      name: form.name.value.trim(),
      organization_type: form.organization_type.value.trim(),
      trust_level: form.trust_level.value,
      status: form.status.value
    };

    try {
      if (msg) msg.textContent = "Menyimpan organisasi...";
      await rnFetch("/organizations", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      form.reset();
      if (msg) msg.textContent = "Organisasi berhasil disimpan.";
      await loadOrganizations();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

function setupPoskoForm() {
  const form = document.querySelector("[data-rn-create-posko]");
  const msg = document.querySelector("[data-rn-posko-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      disaster_event_id: form.disaster_event_id.value.trim(),
      organization_id: form.organization_id.value || null,
      name: form.name.value.trim(),
      node_type: form.node_type.value.trim(),
      location: form.location.value.trim(),
      verification_status: form.verification_status.value,
      operational_status: form.operational_status.value
    };

    try {
      if (msg) msg.textContent = "Menyimpan posko...";
      await rnFetch("/poskos", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      form.reset();
      if (msg) msg.textContent = "Posko berhasil disimpan.";
      await loadPoskos();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadOrganizations();
  loadPoskos();
  setupOrganizationForm();
  setupPoskoForm();
});
