let MEDICAL_CONTEXT_CACHE = null;

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

  el.innerHTML =
    items.length
      ? items.map(c => {
          const id = rowId(c);

          return card(
            c.patient_code,
            `Complaint: ${safe(c.complaint)}<br>` +
            `Severity: ${safe(c.severity)} · ` +
            `Triage: ${safe(c.triage_status)}<br>` +
            `Treatment: ${safe(c.treatment_notes)}<br>` +
            `Case ID: ${safe(id)}` +
            evidenceLink(
              "medical_case",
              id
            ),
            c.case_status ||
            c.status
          );
        }).join("")
      : card(
          "Belum ada kasus medis",
          "Catat kasus medis pertama.",
          "empty"
        );
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
  const poskoId =
    getMedicalPoskoId();

  statusMsg(
    "Loading medical context..."
  );

  const [
    medical,
    logistics
  ] = await Promise.all([
    fetchMedicalOrLocked(poskoId),

    RN_FRAPPE.call(
      "rescue_net.api_logistics.dashboard",
      {
        posko: poskoId
      }
    )
  ]);

  const medicalLocked = medical === null;

  const posko =
    medical?.poskos?.[0] ||
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
  renderCases(ctx.cases);
  renderUses(ctx.supply_uses);
  renderMovements();

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

            complaint:
              form.complaint.value.trim(),

            age_group:
              form.age_group.value.trim(),

            patient_kind:
              form.patient_kind ? form.patient_kind.value : "manusia",

            gender:
              form.gender.value.trim(),

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

      await loadMedical();
    }
  );
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
