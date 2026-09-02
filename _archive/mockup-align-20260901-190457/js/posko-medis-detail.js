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

function renderCases(items) {
  const el =
    document.getElementById(
      "medicalCases"
    );

  if (!el) return;

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

function renderUses(items) {
  const el =
    document.getElementById(
      "medicalUses"
    );

  if (!el) return;

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
    RN_FRAPPE.call(
      "rescue_net.api_medical.dashboard",
      {
        posko: poskoId
      }
    ),

    RN_FRAPPE.call(
      "rescue_net.api_logistics.dashboard",
      {
        posko: poskoId
      }
    )
  ]);

  const posko =
    medical.poskos?.[0] ||
    logistics.poskos?.[0] ||
    {
      name: poskoId
    };

  const ctx = {
    posko,
    cases:
      medical.cases || [],
    supply_uses:
      medical.supply_uses || [],
    evacuations:
      medical.evacuations || [],
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

  const kpiPosko =
    document.getElementById(
      "kpiPosko"
    );

  const kpiStock =
    document.getElementById(
      "kpiStock"
    );

  const kpiCases =
    document.getElementById(
      "kpiCases"
    );

  const kpiUses =
    document.getElementById(
      "kpiUses"
    );

  if (kpiPosko) {
    kpiPosko.textContent =
      safe(posko.posko_type);
  }

  if (kpiStock) {
    kpiStock.textContent =
      ctx.stocks.length;
  }

  if (kpiCases) {
    kpiCases.textContent =
      ctx.cases.length;
  }

  if (kpiUses) {
    kpiUses.textContent =
      ctx.supply_uses.length;
  }

  renderStock(ctx.stocks);
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
    ctx.cases.length
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
