let MEDICAL_CONTEXT_CACHE = null;
let RESOLVED_POSKO_ID = null;

// Mirror of rescue_net.rn_medical...CASE_TRANSITIONS (backend is the source
// of truth and re-validates; this only decides which options we offer).
const CASE_TRANSITIONS = {
  active: ["stabilized", "referred", "evacuating", "discharged", "deceased", "closed"],
  stabilized: ["referred", "evacuating", "admitted", "discharged", "closed"],
  referred: ["evacuating", "admitted", "closed"],
  evacuating: ["admitted", "discharged", "deceased", "closed"],
  admitted: ["discharged", "deceased", "closed"],
  discharged: ["closed"],
  deceased: ["closed"],
  closed: []
};

const CASE_STATUS_LABEL = {
  active: "Aktif / ditangani",
  stabilized: "Stabil",
  referred: "Dirujuk",
  evacuating: "Evakuasi",
  admitted: "Masuk RS",
  discharged: "Pulang",
  deceased: "Meninggal",
  closed: "Ditutup"
};

function caseStatusLabel(s) {
  return CASE_STATUS_LABEL[s] || s || "n/a";
}

function getMedicalPoskoId() {
  const params =
    new URLSearchParams(
      window.location.search
    );

  return (
    params.get("id") ||
    "posko-sim-medis"
  );
}

function statusMsg(msg) {
  const el =
    document.getElementById(
      "medicalStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}

function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  ) ? "n/a" : v;
}

function rowId(row) {
  return (
    row?.name ||
    row?.id ||
    row?.legacy_id ||
    ""
  );
}

function evidenceLink(
  objectType,
  objectId,
  label = "Add Evidence"
) {
  if (!objectId) {
    return "";
  }

  return (
    `<br><a href="evidence.html?` +
    `object_type=${encodeURIComponent(objectType)}` +
    `&object_id=${encodeURIComponent(objectId)}` +
    `&node_id=${encodeURIComponent(getMedicalPoskoId())}` +
    `">${label}</a>`
  );
}

function card(
  title,
  body,
  chip = ""
) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(title)}</h4>
          <p>${body}</p>
        </div>
        <div class="chips">
          ${
            chip
              ? `<span class="chip warning">${safe(chip)}</span>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}

function renderStock(items) {
  const el =
    document.getElementById(
      "medicalStock"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(s => card(
          s.item_name,
          `Current stock: <b>${
            safe(
              s.quantity ??
              s.current_quantity
            )
          }</b> ${safe(s.unit)}`,
          s.stock_state || s.unit
        )).join("")
      : card(
          "Belum ada stok medis",
          "Belum ada Stock Observation untuk Posko ini.",
          "empty"
        );
}

const MEDICAL_LOGIN_NOTICE = card(
  "Login diperlukan",
  "Data medis (kasus, pemakaian obat/alat) hanya untuk pengguna yang sudah login.",
  "empty"
);

// Inline "update status" control for one case. Only the transitions the
// backend will accept are offered; a terminal status shows no control.
function statusControl(id, current) {
  const next = CASE_TRANSITIONS[current] || [];

  if (!next.length) {
    return (
      `<p class="rn-status-done"><small>Status final: ` +
      `${caseStatusLabel(current)} (tidak bisa diubah)</small></p>`
    );
  }

  const opts = next
    .map(s => `<option value="${s}">${caseStatusLabel(s)}</option>`)
    .join("");

  return `
    <div class="rn-status-ctl" data-case="${safe(id)}" data-current="${safe(current)}">
      <select class="rn-status-select" aria-label="Status baru">
        <option value="">— ubah status —</option>
        ${opts}
      </select>
      <input class="rn-status-note" type="text" placeholder="catatan (opsional)">
      <button type="button" class="rn-status-btn">Perbarui</button>
    </div>
  `;
}

function renderCases(items) {
  const el =
    document.getElementById(
      "medicalCases"
    );

  if (!el) return;

  if (items === null) {
    el.innerHTML = MEDICAL_LOGIN_NOTICE;
    return;
  }

  if (!items.length) {
    el.innerHTML = card(
      "Belum ada kasus medis",
      "Catat kasus medis pertama.",
      "empty"
    );
    return;
  }

  el.innerHTML = items
    .map(c => {
      const id = rowId(c);
      const current = c.case_status || c.status;

      return `
        <article class="event-card">
          <div class="event-main">
            <div>
              <h4>${safe(c.patient_code)}${c.patient_name ? " · " + safe(c.patient_name) : ""}</h4>
              <p>Complaint: ${safe(c.complaint)}<br>
              Severity: ${safe(c.severity)} · Triage: ${safe(c.triage_status)}<br>
              Treatment: ${safe(c.treatment_notes)}<br>
              Case ID: ${safe(id)}${evidenceLink("medical_case", id)}</p>
              ${statusControl(id, current)}
              <p class="rn-case-actions">
                <button type="button" class="rn-card-btn" data-case="${safe(id)}">
                  Buka kartu pasien
                </button>
              </p>
            </div>
            <div class="chips">
              <span class="chip warning">${caseStatusLabel(current)}</span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

// ---- Posko needs: kategori kebutuhan logistik bencana ---------------------

// Keep in sync with rescue_net.api_medical.NEED_KINDS and the RN Logistic Need
// need_kind Select options.
const NEED_KIND_LABEL = {
  obat: "Obat & Bahan Medis",
  alat: "Alat & Peralatan Medis",
  logistik: "Logistik Umum",
  makanan_air: "Makanan & Air",
  sanitasi: "Sanitasi & Higiene",
  lainnya: "Lainnya"
};

const NEED_KIND_ORDER =
  ["obat", "alat", "logistik", "makanan_air", "sanitasi", "lainnya"];

function needKindLabel(k) {
  return NEED_KIND_LABEL[k] || k || "Lainnya";
}

function needCard(n) {
  return card(
    n.item_name,
    `Butuh: <b>${safe(n.quantity)}</b> ${safe(n.unit)}` +
    (n.need_status ? `<br>Status: ${safe(n.need_status)}` : ""),
    n.urgency || "need"
  );
}

// `needs` is the flat list from posko_needs; null = login required.
function renderNeeds(needs) {
  const el = document.getElementById("needList");
  if (!el) return;

  if (needs === null) {
    el.innerHTML =
      card("Login diperlukan", "Kebutuhan hanya untuk tim posko.", "empty");
    return;
  }

  if (!needs.length) {
    el.innerHTML =
      card("Belum ada kebutuhan", "Tambah lewat tombol “+ Tambah Kebutuhan”.", "empty");
    return;
  }

  const byKind = {};
  needs.forEach(n => {
    const k = NEED_KIND_LABEL[n.need_kind] ? n.need_kind : "lainnya";
    (byKind[k] = byKind[k] || []).push(n);
  });

  const kinds = NEED_KIND_ORDER.filter(k => byKind[k] && byKind[k].length);

  el.innerHTML = kinds
    .map(k =>
      `<div class="rn-need-group"><h4>${needKindLabel(k)} ` +
      `<span class="chip">${byKind[k].length}</span></h4>` +
      byKind[k].map(needCard).join("") +
      `</div>`
    )
    .join("");
}

async function loadPoskoNeeds(poskoId) {
  try {
    const res =
      await RN_FRAPPE.call(
        "rescue_net.api_medical.posko_needs",
        { posko: poskoId }
      );
    renderNeeds(res.needs || []);
  } catch (e) {
    renderNeeds(null);
  }
}

function setupNeedForm() {
  const form =
    document.getElementById("needForm");

  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const posko =
      RESOLVED_POSKO_ID || getMedicalPoskoId();

    try {
      await RN_FRAPPE.call(
        "rescue_net.api_medical.add_posko_need",
        {
          posko,
          item_name: form.item_name.value.trim(),
          quantity: Number(form.quantity.value || 0),
          unit: form.unit.value.trim(),
          need_kind: form.need_kind.value,
          urgency: form.urgency.value
        },
        { method: "POST" }
      );

      statusMsg("Kebutuhan ditambahkan.");
      form.item_name.value = "";
      form.hidden = true;
      await loadPoskoNeeds(posko);
    } catch (err) {
      statusMsg(err.message || "Gagal menambah kebutuhan.");
    }
  });
}

// ---- Patient card modal (history timeline + add note) ---------------------

function fmtTime(s) {
  if (!s) return "";
  return String(s).replace("T", " ").slice(0, 16);
}

function caseCardHtml(data) {
  const c = data.case || {};
  const hist = data.history || [];

  const rows = hist.length
    ? hist
        .map(h => {
          const when = fmtTime(h.observed_at);
          const by = safe(h.author_name);

          if (h.update_type === "status") {
            return (
              `<li><b>${caseStatusLabel(h.previous_status)} ` +
              `&rarr; ${caseStatusLabel(h.new_status)}</b>` +
              (h.note ? `<br><span>${safe(h.note)}</span>` : "") +
              `<br><small>${when} &middot; ${by}</small></li>`
            );
          }

          return (
            `<li>Catatan: ${safe(h.note)}` +
            `<br><small>${when} &middot; ${by}</small></li>`
          );
        })
        .join("")
    : `<li><small>Belum ada riwayat.</small></li>`;

  return `
    <h3 style="margin:0 0 .25rem">${safe(c.patient_code)}${c.patient_name ? " · " + safe(c.patient_name) : ""}</h3>
    <p style="margin:.1rem 0">${safe(c.complaint)}</p>
    <p style="margin:.1rem 0"><small>Severity: ${safe(c.severity)} &middot;
      Triage: ${safe(c.triage_status)} &middot;
      Umur: ${safe(c.age_group)} &middot; ${safe(c.gender)}</small></p>
    <p style="margin:.1rem 0"><b>Status: ${caseStatusLabel(c.case_status)}</b></p>
    <hr>
    <h4 style="margin:.4rem 0">Riwayat</h4>
    <ul class="rn-card-history"
        style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.5rem">
      ${rows}
    </ul>
    <hr>
    <form class="rn-card-note-form" data-case="${safe(c.name)}">
      <textarea class="rn-card-note" rows="2"
        placeholder="Tambah catatan pasien..."
        style="width:100%;box-sizing:border-box"></textarea>
      <button type="submit">Tambah catatan</button>
    </form>
  `;
}

function openCaseCard(id) {
  statusMsg("Membuka kartu pasien...");

  return RN_FRAPPE.call(
    "rescue_net.api_medical.case_card",
    { medical_case: id }
  )
    .then(data => {
      let overlay =
        document.getElementById("rnCaseCardOverlay");

      if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "rnCaseCardOverlay";
        overlay.style.cssText =
          "position:fixed;inset:0;background:rgba(0,0,0,.5);" +
          "display:flex;align-items:flex-start;justify-content:center;" +
          "padding:4vh 1rem;z-index:9999;overflow:auto";

        overlay.addEventListener("click", e => {
          if (e.target === overlay) { overlay.remove(); return; }
          if (e.target.closest(".rn-card-close")) overlay.remove();
        });

        overlay.addEventListener("submit", async e => {
          const form = e.target.closest(".rn-card-note-form");
          if (!form) return;
          e.preventDefault();

          const caseId = form.getAttribute("data-case");
          const ta = form.querySelector(".rn-card-note");
          const note = (ta && ta.value.trim()) || "";

          if (!note) { statusMsg("Catatan kosong."); return; }

          try {
            await RN_FRAPPE.call(
              "rescue_net.api_medical.add_case_note",
              { medical_case: caseId, note },
              { method: "POST" }
            );
            await openCaseCard(caseId);
          } catch (err) {
            statusMsg(err.message || "Gagal menambah catatan.");
          }
        });

        document.body.appendChild(overlay);
      }

      overlay.innerHTML = `
        <div style="background:#fff;color:#111;max-width:560px;width:100%;
          border-radius:12px;padding:1.25rem;box-shadow:0 10px 40px rgba(0,0,0,.3)">
          <div style="display:flex;justify-content:flex-end">
            <button type="button" class="rn-card-close" aria-label="Tutup"
              style="font-size:1.2rem;background:none;border:none;cursor:pointer">
              &times;
            </button>
          </div>
          <div class="rn-card-body">${caseCardHtml(data)}</div>
        </div>
      `;

      statusMsg("Kartu pasien dibuka.");
    })
    .catch(err =>
      statusMsg(err.message || "Gagal membuka kartu pasien.")
    );
}

// Delegated handler: the listener lives on the #medicalCases container, which
// survives loadMedical() re-renders (only its innerHTML is replaced).
function setupCaseStatusControls() {
  const el =
    document.getElementById(
      "medicalCases"
    );

  if (!el || el.dataset.statusWired) return;
  el.dataset.statusWired = "1";

  el.addEventListener("click", async e => {
    const cardBtn = e.target.closest(".rn-card-btn");
    if (cardBtn) {
      openCaseCard(cardBtn.getAttribute("data-case"));
      return;
    }

    const btn = e.target.closest(".rn-status-btn");
    if (!btn) return;

    const ctl = btn.closest(".rn-status-ctl");
    if (!ctl) return;

    const id = ctl.getAttribute("data-case");
    const sel = ctl.querySelector(".rn-status-select");
    const note = ctl.querySelector(".rn-status-note");
    const newStatus = sel && sel.value;

    if (!newStatus) {
      statusMsg("Pilih status baru dulu.");
      return;
    }

    btn.disabled = true;

    try {
      await RN_FRAPPE.call(
        "rescue_net.api_medical.update_case_status",
        {
          medical_case: id,
          new_status: newStatus,
          treatment_notes: (note && note.value.trim()) || null
        },
        { method: "POST" }
      );

      statusMsg("Status pasien diperbarui.");
      await loadMedical();
    } catch (err) {
      statusMsg(err.message || "Gagal memperbarui status.");
      btn.disabled = false;
    }
  });
}

// ---- Pasien aktif & kondisi terakhir (owner 2026-10-18) ----
// Data = api_medical.dashboard (operator / pengelola posko saja). "Kondisi
// terakhir" = status kasus + triase/tingkat + catatan penanganan terakhir +
// evakuasi terbaru, dengan waktu pembaruan terakhir.
const CASE_DONE = new Set(["discharged", "deceased", "closed"]);
const TRIAGE_RANK = { red: 0, yellow: 1, green: 2, black: 3 };
const TRIAGE_LABEL = { red: "Merah · gawat", yellow: "Kuning · sedang", green: "Hijau · ringan", black: "Hitam" };
const CASE_LABEL = {
  active: "Ditangani", stabilized: "Stabil", referred: "Dirujuk",
  evacuating: "Sedang dievakuasi", admitted: "Dirawat di faskes"
};
const SEVERITY_LABEL = { mild: "ringan", minor: "ringan", moderate: "sedang", severe: "berat", critical: "kritis" };
const AGE_LABEL = { infant: "bayi", child: "anak", adolescent: "remaja", adult: "dewasa", elderly: "lansia" };
const GENDER_LABEL = { male: "L", female: "P", other: "lainnya" };
const EVAC_LABEL = {
  requested: "diminta", assigned: "armada ditugaskan", en_route_pickup: "menuju penjemputan",
  patient_on_board: "pasien di kendaraan", arrived_hospital: "tiba di faskes",
  handover_complete: "sudah diserahterimakan", cancelled: "batal"
};

function escHtml(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g, ch =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
}

function fmtWhen(v) {
  if (!v) return "-";
  const d = new Date(String(v).replace(" ", "T"));
  if (isNaN(d)) return escHtml(v);
  return d.toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function renderActivePatients(cases, evacuations) {
  const body = document.getElementById("activePatientsBody");
  const count = document.getElementById("activePatientsCount");
  if (!body) return;

  if (cases === null) {
    if (count) count.textContent = "terkunci";
    body.innerHTML = '<tr><td colspan="6">Daftar pasien hanya untuk petugas / pengelola posko medis ini yang sudah login.</td></tr>';
    return;
  }

  const latestEvac = {};
  (evacuations || []).forEach(e => {
    const k = e.medical_case;
    if (!k) return;
    const t = e.handover_at || e.arrived_at || e.departed_at || e.requested_at || "";
    if (!latestEvac[k] || t > latestEvac[k]._t) latestEvac[k] = Object.assign({ _t: t }, e);
  });

  const rows = (cases || [])
    .filter(c => !CASE_DONE.has(c.case_status))
    .sort((a, b) =>
      (TRIAGE_RANK[a.triage_status] ?? 9) - (TRIAGE_RANK[b.triage_status] ?? 9) ||
      String(b.source_updated_at || b.observed_at || "").localeCompare(String(a.source_updated_at || a.observed_at || ""))
    );

  if (count) count.textContent = rows.length + " pasien";

  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6">Tidak ada pasien aktif saat ini.</td></tr>';
    return;
  }

  body.innerHTML = rows.map(c => {
    const meta = [AGE_LABEL[c.age_group], GENDER_LABEL[c.gender]].filter(Boolean).join(" · ");
    const tri = c.triage_status || "";
    const ev = latestEvac[c.name];
    const evText = ev
      ? escHtml(EVAC_LABEL[ev.evacuation_status] || ev.evacuation_status || "-") +
        (ev.destination_facility ? '<span class="rn-md-meta">ke ' + escHtml(ev.destination_facility) + "</span>" : "")
      : "-";
    const note = c.treatment_notes || "";
    const sev = SEVERITY_LABEL[c.severity] || c.severity;
    return "<tr>" +
      '<td><span class="rn-md-code">' + escHtml(c.patient_code || c.name) + "</span>" +
        (c.patient_name ? '<span class="rn-md-meta">' + escHtml(c.patient_name) + "</span>" : "") +
        (meta ? '<span class="rn-md-meta">' + escHtml(meta) + "</span>" : "") +
        (c.complaint ? '<span class="rn-md-meta">' + escHtml(c.complaint) + "</span>" : "") + "</td>" +
      '<td><span class="chip rn-tri-' + escHtml(tri) + '">' + escHtml(TRIAGE_LABEL[tri] || tri || "-") + "</span>" +
        (sev ? '<span class="rn-md-meta">tingkat ' + escHtml(sev) + "</span>" : "") + "</td>" +
      "<td>" + escHtml(CASE_LABEL[c.case_status] || c.case_status || "-") + "</td>" +
      '<td class="rn-md-note">' + (note ? escHtml(note) : '<span class="rn-md-meta">belum ada catatan penanganan</span>') + "</td>" +
      "<td>" + evText + "</td>" +
      '<td class="rn-md-when">' + fmtWhen(c.source_updated_at || c.observed_at) + "</td>" +
      "</tr>";
  }).join("");
}

// Unit 4 (owner): a guest-safe "find your relative" roster for a PUBLIC
// medical posko. Data = api_medical.public_patients — identity + outcome only
// (name, code, age/gender, triase, status, latest evacuation), NEVER the
// complaint, treatment notes or supply use. No card opens here. Shown only
// when the private (petugas) dashboard is locked AND the posko is public.
const PUBLIC_OUTCOME = {
  active: "Masih ditangani", stabilized: "Kondisi stabil", referred: "Dirujuk",
  evacuating: "Sedang dievakuasi", admitted: "Dirawat di faskes",
  discharged: "Sudah dipulangkan", deceased: "Meninggal dunia", closed: "Selesai ditangani"
};

function publicOutcome(c) {
  let t = PUBLIC_OUTCOME[c.case_status] || c.case_status || "-";
  if (c.destination_facility && (c.case_status === "referred" || c.case_status === "admitted" || c.case_status === "evacuating")) {
    t += " ke " + c.destination_facility;
  }
  return t;
}

async function loadPublicPatients(poskoId) {
  if (!poskoId) return;
  let res;
  try {
    res = await RN_FRAPPE.call(
      "rescue_net.api_medical.public_patients",
      { posko: poskoId }
    );
  } catch (e) {
    return; // keep the petugas-only notice already shown
  }
  if (res && res.allowed) renderPublicPatients(res.patients || []);
}

function renderPublicPatients(patients) {
  const body = document.getElementById("activePatientsBody");
  const count = document.getElementById("activePatientsCount");
  const hint = document.getElementById("activePatientsHint");
  if (!body) return;

  if (hint) {
    hint.textContent =
      "Daftar publik untuk membantu keluarga menemukan korban: nama, kondisi, dan tujuan rujukan. " +
      "Keluhan dan catatan penanganan hanya untuk petugas posko.";
  }
  if (count) count.textContent = patients.length + " pasien";

  if (!patients.length) {
    body.innerHTML = '<tr><td colspan="6">Belum ada data pasien yang dipublikasikan posko ini.</td></tr>';
    return;
  }

  const rank = c => (TRIAGE_RANK[c.triage_status] ?? 9);
  const rows = patients.slice().sort((a, b) =>
    rank(a) - rank(b) ||
    String(b.updated_at || "").localeCompare(String(a.updated_at || ""))
  );

  body.innerHTML = rows.map(c => {
    const name = c.patient_name ? escHtml(c.patient_name) : '<span class="rn-md-meta">tanpa nama</span>';
    const meta = [AGE_LABEL[c.age_group], GENDER_LABEL[c.gender]].filter(Boolean).join(" · ");
    const tri = c.triage_status || "";
    const evText = c.evacuation_status
      ? escHtml(EVAC_LABEL[c.evacuation_status] || c.evacuation_status) +
        (c.destination_facility ? '<span class="rn-md-meta">ke ' + escHtml(c.destination_facility) + "</span>" : "")
      : "-";
    return "<tr>" +
      "<td><strong>" + name + "</strong>" +
        '<span class="rn-md-meta">' + escHtml(c.patient_code || "") + "</span>" +
        (meta ? '<span class="rn-md-meta">' + escHtml(meta) + "</span>" : "") + "</td>" +
      '<td><span class="chip rn-tri-' + escHtml(tri) + '">' + escHtml(TRIAGE_LABEL[tri] || tri || "-") + "</span></td>" +
      "<td>" + escHtml(CASE_LABEL[c.case_status] || PUBLIC_OUTCOME[c.case_status] || c.case_status || "-") + "</td>" +
      '<td class="rn-md-note">' + escHtml(publicOutcome(c)) + "</td>" +
      "<td>" + evText + "</td>" +
      '<td class="rn-md-when">' + fmtWhen(c.updated_at) + "</td>" +
      "</tr>";
  }).join("");
}

function wireKpiLinks() {
  document.querySelectorAll(".kpi-card[data-go]").forEach(card => {
    const go = () => {
      const el = document.querySelector(card.dataset.go);
      if (el) (el.closest(".panel") || el).scrollIntoView({ behavior: "smooth", block: "start" });
    };
    card.addEventListener("click", go);
    card.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
    });
  });
}

function renderUses(items) {
  const el =
    document.getElementById(
      "medicalUses"
    );

  if (!el) return;

  if (items === null) {
    el.innerHTML = MEDICAL_LOGIN_NOTICE;
    return;
  }

  el.innerHTML =
    items.length
      ? items.map(u => {
          const id = rowId(u);

          return card(
            u.item_name,
            `${safe(u.quantity)} ${safe(u.unit)}<br>` +
            `Case: ${safe(u.medical_case)}<br>` +
            `${safe(u.notes)}` +
            evidenceLink(
              "medical_supply_use",
              id
            ),
            id
          );
        }).join("")
      : card(
          "Belum ada pemakaian medis",
          "Belum ada obat/alat dipakai.",
          "empty"
        );
}

function renderMovements() {
  const el =
    document.getElementById(
      "medicalMovements"
    );

  if (!el) return;

  el.innerHTML =
    card(
      "Stock Observation",
      "Stok medis sekarang membaca RN Stock Observation canonical.",
      "Frappe"
    );
}

// api_medical.dashboard is actor-gated (rn_actor()) and returns PII
// (officer_in_charge_phone) — it's not meant to be guest-accessible like
// api_logistics.dashboard. Fail it gracefully to null instead of letting
// it abort the whole Promise.all and strand the page on "Loading...".
async function fetchMedicalOrLocked(poskoId) {
  try {
    return await RN_FRAPPE.call(
      "rescue_net.api_medical.dashboard",
      {
        posko: poskoId
      }
    );
  } catch (err) {
    if (
      err &&
      (err.status === 403 ||
        /permission|not permitted|login|not whitelisted/i.test(err.message || ""))
    ) {
      return null;
    }
    throw err;
  }
}

async function loadMedical() {
  const requestedId =
    getMedicalPoskoId();

  statusMsg(
    "Loading medical context..."
  );

  // Try the posko in the URL first. If it is forbidden or empty for this
  // user (e.g. a stale "?id=posko-sim-medis" link that is not theirs), fall
  // back to "my accessible medical poskos" (dashboard with no posko) so an
  // operator always lands on their own posko's patients instead of an empty
  // or login-locked view.
  let medical =
    await fetchMedicalOrLocked(requestedId);

  if (
    medical === null ||
    !(medical.poskos && medical.poskos.length)
  ) {
    const mine =
      await fetchMedicalOrLocked(null);

    if (mine && mine.poskos && mine.poskos.length) {
      medical = mine;
    }
  }

  const medicalLocked = medical === null;

  const resolvedPosko =
    medical && medical.poskos && medical.poskos[0];

  const poskoId =
    (resolvedPosko && resolvedPosko.name) ||
    requestedId;

  RESOLVED_POSKO_ID = poskoId;

  // Stock is secondary: keep patient data visible even if logistics fails.
  let logistics = { poskos: [], stocks: [] };
  try {
    logistics =
      await RN_FRAPPE.call(
        "rescue_net.api_logistics.dashboard",
        {
          posko: poskoId
        }
      );
  } catch (e) {
    /* stock optional */
  }

  const posko =
    resolvedPosko ||
    logistics.poskos?.[0] ||
    {
      name: poskoId
    };

  const ctx = {
    posko,
    cases:
      medicalLocked ? null : (medical.cases || []),
    supply_uses:
      medicalLocked ? null : (medical.supply_uses || []),
    evacuations:
      medicalLocked ? null : (medical.evacuations || []),
    stocks:
      logistics.stocks || []
  };

  MEDICAL_CONTEXT_CACHE = ctx;

  const title =
    document.getElementById(
      "medicalTitle"
    );

  const subtitle =
    document.getElementById(
      "medicalSubtitle"
    );

  if (title) {
    title.textContent =
      posko.title ||
      posko.name ||
      poskoId;
  }

  if (subtitle) {
    subtitle.textContent =
      `${safe(posko.posko_type)} · ` +
      `${safe(posko.operational_status)} · ` +
      `${safe(posko.verification_status)}`;
  }

  // KPI (owner 2026-10-18): angka yang berguna + bisa diklik ke bagiannya.
  const setKpi = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const setHint = (id, v) => { const el = document.getElementById(id); if (el && v) el.textContent = v; };
  if (ctx.cases) {
    const active = ctx.cases.filter(c => !CASE_DONE.has(c.case_status));
    setKpi("kpiActive", active.length);
    setKpi("kpiRed", active.filter(c => c.triage_status === "red").length);
    setHint("kpiActiveHint", ctx.cases.length + " kasus tercatat total");
  } else {
    setKpi("kpiActive", "-");
    setKpi("kpiRed", "-");
    setHint("kpiActiveHint", "khusus petugas posko");
    setHint("kpiRedHint", "khusus petugas posko");
    setHint("kpiUsesHint", "khusus petugas posko");
  }
  setKpi("kpiStock", ctx.stocks.length);
  setKpi("kpiUses", ctx.supply_uses ? ctx.supply_uses.length : "-");

  renderStock(ctx.stocks);
  renderActivePatients(ctx.cases, ctx.evacuations);
  // Locked for this (guest/non-petugas) viewer? Try the public family-finding
  // roster so a relative can still look for a victim by name + outcome.
  if (medicalLocked && poskoId) {
    loadPublicPatients(poskoId);
  }
  renderCases(ctx.cases);
  renderUses(ctx.supply_uses);
  renderMovements();

  if (medicalLocked) {
    renderNeeds(null);
  } else {
    loadPoskoNeeds(poskoId);
  }

  const caseForm =
    document.getElementById(
      "caseForm"
    );

  if (
    caseForm &&
    caseForm.posko_id
  ) {
    caseForm.posko_id.value =
      poskoId;
  }

  const useForm =
    document.getElementById(
      "supplyUseForm"
    );

  if (
    useForm &&
    useForm.medical_case_id &&
    !useForm.medical_case_id.value &&
    ctx.cases && ctx.cases.length
  ) {
    useForm.medical_case_id.value =
      rowId(ctx.cases[0]);
  }

  statusMsg(
    "Loaded from Frappe"
  );
}

function setupCaseForm() {
  const form =
    document.getElementById(
      "caseForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const result =
        await RN_FRAPPE.call(
          "rescue_net.api_medical.create_case",
          {
            posko:
              form.posko_id.value.trim(),

            patient_code:
              form.patient_code.value.trim(),

            patient_name:
              form.patient_name ? form.patient_name.value.trim() : "",

            complaint:
              form.complaint.value.trim(),

            age_group:
              form.age_group.value.trim(),

            patient_kind:
              form.patient_kind ? form.patient_kind.value : "manusia",

            gender:
              form.gender.value.trim(),

            has_disability:
              form.has_disability && form.has_disability.checked ? 1 : 0,

            severity:
              form.severity.value,

            triage_status:
              form.triage_status.value,

            treatment_notes:
              form.treatment_notes.value.trim()
          },
          {
            method: "POST"
          }
        );

      const useForm =
        document.getElementById(
          "supplyUseForm"
        );

      if (
        useForm &&
        useForm.medical_case_id
      ) {
        useForm.medical_case_id.value =
          result.medical_case || "";
      }

      statusMsg(
        "Medical case saved."
      );

      form.hidden = true;
      await loadMedical();
    }
  );
}

function setupSupplyUseForm() {
  const form =
    document.getElementById(
      "supplyUseForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_medical.record_supply_use",
        {
          posko:
            RESOLVED_POSKO_ID ||
            getMedicalPoskoId(),

          medical_case:
            form.medical_case_id
              .value
              .trim() ||
            null,

          item_name:
            form.item_name.value.trim(),

          quantity:
            Number(
              form.quantity.value || 0
            ),

          unit:
            form.unit.value.trim(),

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Medical supply use saved."
      );

      form.hidden = true;
      await loadMedical();
    }
  );
}

// ---- Penerimaan bantuan: masuk ke stok medis ------------------------------

function setupAidForm() {
  const form = document.getElementById("aidForm");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const posko =
      RESOLVED_POSKO_ID || getMedicalPoskoId();

    try {
      await RN_FRAPPE.call(
        "rescue_net.api_medical.record_aid_received",
        {
          posko,
          item_name: form.item_name.value.trim(),
          quantity: Number(form.quantity.value || 0),
          unit: form.unit.value.trim(),
          donor: form.donor.value.trim(),
          notes: form.notes.value.trim()
        },
        { method: "POST" }
      );

      statusMsg("Penerimaan bantuan dicatat (masuk ke stok).");
      form.item_name.value = "";
      form.donor.value = "";
      form.notes.value = "";
      form.hidden = true;
      await loadMedical();
    } catch (err) {
      statusMsg(err.message || "Gagal mencatat penerimaan bantuan.");
    }
  });
}

// Generic "+ Tambah / Tutup" toggles: a button with data-toggle="#formId"
// shows/hides that inline form and focuses its first field.
function setupToggles() {
  document.querySelectorAll("[data-toggle]").forEach(btn => {
    btn.addEventListener("click", () => {
      const target =
        document.querySelector(btn.getAttribute("data-toggle"));
      if (!target) return;

      target.hidden = !target.hidden;
      if (!target.hidden) {
        const first = target.querySelector("input, select, textarea");
        if (first) first.focus();
      }
    });
  });
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      statusMsg(
        "Frappe client tidak tersedia."
      );
      return;
    }

    setupCaseForm();
    setupSupplyUseForm();
    setupCaseStatusControls();
    setupNeedForm();
    setupAidForm();
    setupToggles();
    wireKpiLinks();

    const btn =
      document.getElementById(
        "refreshMedical"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () => loadMedical()
          .catch(
            err =>
              statusMsg(err.message)
          )
      );
    }

    loadMedical().catch(
      err =>
        statusMsg(err.message)
    );
  }
);
