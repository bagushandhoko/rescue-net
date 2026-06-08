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

async function loadVolunteers() {
  const target = document.querySelector("[data-rn-volunteers]");
  if (!target) return;

  try {
    const volunteers = await rnFetch("/volunteers");

    target.innerHTML = volunteers.map(v => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${v.name}</h4>
            <p>${v.main_skill} · ${v.location} · ${v.availability}</p>
          </div>
          <div class="chips">
            <span class="chip neutral">${v.duration_available || "duration n/a"}</span>
            <span class="chip neutral">${v.verification_status}</span>
          </div>
        </div>
      </article>
    `).join("");

  } catch (err) {
    target.innerHTML = `<article class="event-card"><h4>Gagal load relawan</h4><p>${err.message}</p></article>`;
  }
}

function setupVolunteerForm() {
  const form = document.querySelector("[data-rn-create-volunteer]");
  const msg = document.querySelector("[data-rn-volunteer-message]");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      name: form.name.value.trim(),
      phone: form.phone.value.trim(),
      email: form.email.value.trim(),
      main_skill: form.main_skill.value.trim(),
      location: form.location.value.trim(),
      availability: form.availability.value.trim(),
      duration_available: form.duration_available.value.trim(),
      verification_status: form.verification_status.value
    };

    try {
      if (msg) msg.textContent = "Menyimpan relawan...";
      await rnFetch("/volunteers", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      form.reset();
      if (msg) msg.textContent = "Relawan berhasil disimpan.";
      await loadVolunteers();

    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadVolunteers();
  setupVolunteerForm();
});
