const DISASTER_ID =
  new URLSearchParams(
    location.search
  ).get("event") ||
  "event-sim-001";


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function rupiah(value) {
  return new Intl.NumberFormat(
    "id-ID"
  ).format(
    Number(value || 0)
  );
}


function statusMsg(msg) {
  const el =
    document.getElementById(
      "donorProgramStatus"
    ) ||
    document.getElementById(
      "programStatus"
    );

  if (el) {
    el.textContent = msg;
  }
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


function renderPrograms(items) {
  const target =
    document.getElementById(
      "programList"
    ) ||
    document.getElementById(
      "donorPrograms"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(p => card(
          p.program_name,
          `Type: ${safe(p.program_type)}<br>` +
          `Owner: ${safe(p.owner_type)} / ${safe(p.owner_id)}<br>` +
          `Target: ${rupiah(p.target_amount)} ${safe(p.target_unit)}<br>` +
          `Location: ${safe(p.location)}<br>` +
          `Progress: ${safe(p.progress_percent)}%`,
          p.program_status ||
          p.status
        )).join("")
      : card(
          "Belum ada Donor Program",
          "Belum ada program pada disaster event ini.",
          "empty"
        );
}


function renderUpdates(items) {
  const target =
    document.getElementById(
      "programUpdates"
    ) ||
    document.getElementById(
      "updateList"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(u => card(
          u.update_title,
          `Program: ${safe(u.program)}<br>` +
          `Type: ${safe(u.update_type)}<br>` +
          `Progress: ${safe(u.progress_percent)}%<br>` +
          `Spent: ${rupiah(u.amount_spent)} ${safe(u.amount_unit)}<br>` +
          `${safe(u.update_notes)}`,
          u.verification_status ||
          u.update_type
        )).join("")
      : card(
          "Belum ada program update",
          "Belum ada update untuk program.",
          "empty"
        );
}


function fillProgramSelect(items) {
  const select =
    document.querySelector(
      '#programUpdateForm [name="program_id"]'
    ) ||
    document.querySelector(
      '#programUpdateForm [name="program"]'
    );

  if (!select) return;

  /*
   * Kalau field-nya INPUT biasa jangan mengganti
   * menjadi option list.
   */
  if (
    select.tagName !== "SELECT"
  ) {
    return;
  }

  select.innerHTML =
    `<option value="">Pilih program</option>` +
    items.map(p => `
      <option value="${safe(p.name)}">
        ${safe(p.program_name)}
      </option>
    `).join("");
}


function renderSummary(ctx) {
  const summary =
    ctx.summary || {};

  const mapping = {
    kpiPrograms:
      summary.program_count ??
      (ctx.programs || []).length,

    kpiUpdates:
      summary.update_count ??
      (ctx.updates || []).length,

    kpiActive:
      summary.active_program_count ??
      0
  };

  Object.entries(mapping)
    .forEach(
      ([id, value]) => {
        const el =
          document.getElementById(id);

        if (el) {
          el.textContent =
            value ?? 0;
        }
      }
    );
}


async function loadPrograms() {
  statusMsg(
    "Loading Donor Program from Frappe..."
  );

  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_donor_program.context",
      {
        disaster_event:
          DISASTER_ID
      }
    );

  const programs =
    ctx.programs || [];

  const updates =
    ctx.updates || [];

  renderPrograms(
    programs
  );

  renderUpdates(
    updates
  );

  renderSummary(
    ctx
  );

  fillProgramSelect(
    programs
  );

  statusMsg(
    "Loaded from Frappe"
  );
}


function setupProgramForm() {
  const form =
    document.getElementById(
      "programForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      statusMsg(
        "Saving Donor Program..."
      );

      const result =
        await RN_FRAPPE.call(
          "rescue_net.api_donor_program." +
          "create_program",
          {
            disaster_event:
              DISASTER_ID,

            program_name:
              form.program_name.value
                .trim(),

            program_type:
              form.program_type?.value ||
              "general_relief",

            owner_type:
              form.owner_type?.value ||
              "organization",

            owner_id:
              form.owner_id?.value
                ?.trim() ||
              null,

            target_description:
              form.target_description?.value
                ?.trim() ||
              null,

            target_amount:
              Number(
                form.target_amount?.value ||
                0
              ),

            target_unit:
              form.target_unit?.value
                ?.trim() ||
              "IDR",

            location:
              form.location?.value
                ?.trim() ||
              null,

            contact_person:
              form.contact_person?.value
                ?.trim() ||
              null,

            contact_phone:
              form.contact_phone?.value
                ?.trim() ||
              null,

            notes:
              form.notes?.value
                ?.trim() ||
              null,

            public_visibility:
              form.public_visibility?.value ||
              "summary_public"
          },
          {
            method: "POST"
          }
        );

      console.log(
        "DONOR_PROGRAM_CREATE:",
        result
      );

      statusMsg(
        "Donor Program saved."
      );

      form.reset();

      await loadPrograms();
    }
  );
}


function setupUpdateForm() {
  const form =
    document.getElementById(
      "programUpdateForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const program =
        form.program_id?.value
          ?.trim() ||
        form.program?.value
          ?.trim();

      if (!program) {
        statusMsg(
          "Program ID wajib diisi."
        );
        return;
      }

      statusMsg(
        "Saving Program Update..."
      );

      const result =
        await RN_FRAPPE.call(
          "rescue_net.api_donor_program." +
          "create_update",
          {
            program,

            update_title:
              form.update_title.value
                .trim(),

            update_type:
              form.update_type?.value ||
              "progress",

            progress_percent:
              Number(
                form.progress_percent?.value ||
                0
              ),

            amount_spent:
              Number(
                form.amount_spent?.value ||
                0
              ),

            amount_unit:
              form.amount_unit?.value
                ?.trim() ||
              null,

            update_notes:
              form.update_notes?.value
                ?.trim() ||
              null,

            officer_in_charge_name:
              form.officer_in_charge_name
                ?.value
                ?.trim() ||
              null,

            officer_in_charge_phone:
              form.officer_in_charge_phone
                ?.value
                ?.trim() ||
              null,

            public_visibility:
              form.public_visibility?.value ||
              "summary_public"
          },
          {
            method: "POST"
          }
        );

      console.log(
        "DONOR_PROGRAM_UPDATE:",
        result
      );

      statusMsg(
        "Program update saved."
      );

      form.reset();

      await loadPrograms();
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

    setupProgramForm();
    setupUpdateForm();

    const refresh =
      document.getElementById(
        "refreshPrograms"
      ) ||
      document.getElementById(
        "refreshDonorPrograms"
      );

    if (refresh) {
      refresh.addEventListener(
        "click",
        () =>
          loadPrograms().catch(
            err =>
              statusMsg(
                err.message
              )
          )
      );
    }

    loadPrograms().catch(
      err =>
        statusMsg(
          err.message
        )
    );
  }
);
