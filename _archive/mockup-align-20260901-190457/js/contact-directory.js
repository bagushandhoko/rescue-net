const DISASTER_ID = "event-aceh-2025";

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

function statusMsg(msg) {
  const el = document.getElementById("contactStatus");
  if (el) el.textContent = msg;
}

function normalizePhone(phone) {
  if (!phone) return "";
  let p = String(phone).replace(/[^\d+]/g, "");
  if (p.startsWith("0")) p = "62" + p.slice(1);
  if (p.startsWith("+")) p = p.slice(1);
  return p;
}

function contactActions(phone, message) {
  const p = normalizePhone(phone);
  if (!p) return "";
  const text = encodeURIComponent(message || "Halo, saya menghubungi dari Rescue-Net.");
  return `
    <div class="form-actions">
      <a class="btn" href="tel:${p}">Call</a>
      <a class="btn primary" target="_blank" href="https://wa.me/${p}?text=${text}">WhatsApp</a>
    </div>
  `;
}

async function api(path) {
  const url =
    new URL(
      path,
      location.origin
    );

  if (
    url.pathname.startsWith(
      "/ai/context/"
    )
  ) {
    const eventId =
      decodeURIComponent(
        url.pathname
          .slice(
            "/ai/context/".length
          )
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          eventId
      }
    );
  }

  if (
    url.pathname.startsWith(
      "/volunteer-context/"
    )
  ) {
    const data =
      await RN_FRAPPE.call(
        "rescue_net.api_volunteer." +
        "control_centre_volunteers",
        {}
      );

    return {
      volunteers:
        data.volunteers ||
        data.profiles ||
        [],
      assignments:
        data.assignments ||
        [],
      summary:
        data
    };
  }

  if (
    url.pathname.startsWith(
      "/donor-program-context/"
    )
  ) {
    const eventId =
      decodeURIComponent(
        url.pathname
          .slice(
            "/donor-program-context/".length
          )
      );

    return await RN_FRAPPE.call(
      "rescue_net.api_donor_program.context",
      {
        disaster_event:
          eventId
      }
    );
  }

  throw new Error(
    "Unsupported Contact route after Frappe cutover: " +
    url.pathname
  );
}

function card(title, body, chip = "", actions = "") {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${title}</h4>
          <p>${body}</p>
          ${actions}
        </div>
        <div class="chips">
          ${chip ? `<span class="chip warning">${chip}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

function uniqueByPhone(items) {
  const seen = new Set();
  const out = [];
  for (const x of items) {
    const p = normalizePhone(x.phone);
    const key = `${p}-${x.name}-${x.role}`;
    if (!p && !x.name) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(x);
  }
  return out;
}

function renderSummary(groups) {
  const el = document.getElementById("contactSummary");
  if (!el) return;

  el.innerHTML = `
    <div><span>Officers</span><b>${groups.officers.length}</b></div>
    <div><span>Donors</span><b>${groups.donors.length}</b></div>
    <div><span>Volunteers</span><b>${groups.volunteers.length}</b></div>
    <div><span>Programs</span><b>${groups.programs.length}</b></div>
  `;
}

function renderContacts(id, items, emptyText) {
  const el = document.getElementById(id);
  if (!el) return;

  el.innerHTML = items.length ? items.map(c => card(
    safe(c.name),
    `Phone: ${safe(c.phone)}<br>Role: ${safe(c.role)}<br>Source: ${safe(c.source)}<br>Object: ${safe(c.object_id)}<br>Notes: ${safe(c.notes)}`,
    safe(c.role),
    contactActions(c.phone, `Halo ${safe(c.name)}, saya menghubungi terkait Rescue-Net ${safe(c.source)} ${safe(c.object_id)}.`)
  )).join("") : card("Belum ada kontak", emptyText, "empty");
}

async function loadContacts() {
  statusMsg("Loading contacts...");

  const [ai, volunteers, donorPrograms] = await Promise.all([
    api(`/ai/context/${DISASTER_ID}`),
    api(`/volunteer-context/${DISASTER_ID}`),
    api(`/donor-program-context/${DISASTER_ID}`).catch(() => ({ programs: [] }))
  ]);

  const officers = [];

  for (const p of ai.poskos || []) {
    officers.push({
      name: p.officer_in_charge_name,
      phone: p.officer_in_charge_phone,
      role: p.officer_in_charge_role || "posko_officer",
      source: "posko",
      object_id: p.id,
      notes: p.name
    });
  }

  for (const f of ai.distribution_flows || []) {
    officers.push({
      name: f.officer_in_charge_name,
      phone: f.officer_in_charge_phone,
      role: f.officer_in_charge_role || "distribution_officer",
      source: "distribution_flow",
      object_id: f.id,
      notes: f.status
    });
  }

  const donors = (ai.aid_offers || []).map(a => ({
    name: a.donor_name,
    phone: a.donor_contact,
    role: "donor",
    source: "aid_offer",
    object_id: a.id,
    notes: `${safe(a.item_name)} ${safe(a.quantity)} ${safe(a.unit)}`
  }));

  const vols = (volunteers.volunteers || []).map(v => ({
    name: v.volunteer_name,
    phone: v.contact,
    role: v.availability_status || "volunteer",
    source: "volunteer",
    object_id: v.id,
    notes: v.skill_tags
  }));

  const programs = (donorPrograms.programs || []).map(p => ({
    name: p.contact_person,
    phone: p.contact_phone,
    role: "program_pic",
    source: "donor_program",
    object_id: p.id,
    notes: p.program_name
  }));

  const groups = {
    officers: uniqueByPhone(officers),
    donors: uniqueByPhone(donors),
    volunteers: uniqueByPhone(vols),
    programs: uniqueByPhone(programs)
  };

  renderSummary(groups);
  renderContacts("officerContacts", groups.officers, "Belum ada Officer in Charge dengan nomor HP.");
  renderContacts("donorContacts", groups.donors, "Belum ada donor contact.");
  renderContacts("volunteerContacts", groups.volunteers, "Belum ada volunteer contact.");
  renderContacts("programContacts", groups.programs, "Belum ada PIC program.");

  statusMsg("Loaded: " + new Date().toISOString());
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("refreshContacts");
  if (btn) btn.addEventListener("click", () => loadContacts().catch(err => statusMsg(err.message)));
  loadContacts().catch(err => statusMsg(err.message));
});
