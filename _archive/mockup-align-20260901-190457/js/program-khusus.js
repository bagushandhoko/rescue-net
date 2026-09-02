function getEventId() {
  return (
    new URLSearchParams(
      location.search
    ).get("event") ||
    "event-sim-001"
  );
}


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function rupiah(n) {
  return new Intl.NumberFormat(
    "id-ID"
  ).format(
    Number(n || 0)
  );
}


function setText(id, value) {
  const el =
    document.getElementById(id);

  if (el) {
    el.textContent = value;
  }
}


function programCard(p) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(p.program_name)}</h4>

          <p>
            Type: ${safe(p.program_type)}<br>
            Owner:
            ${safe(p.owner_type)} /
            ${safe(p.owner_id)}<br>
            Target:
            ${rupiah(p.target_amount)}
            ${safe(p.target_unit)}<br>
            Progress:
            ${safe(p.progress_percent)}%
          </p>
        </div>

        <div class="chips">
          <span class="chip warning">
            ${safe(p.program_status || p.status)}
          </span>
        </div>
      </div>
    </article>
  `;
}


async function loadPrograms() {
  const eventId =
    getEventId();

  setText(
    "programStatus",
    "Loading programs from Frappe..."
  );

  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_donor_program.context",
      {
        disaster_event:
          eventId
      }
    );

  const programs =
    ctx.programs || [];

  const target =
    document.getElementById(
      "programList"
    );

  if (target) {
    target.innerHTML =
      programs.length
        ? programs
            .map(programCard)
            .join("")
        : `
          <article class="event-card">
            <h4>Belum ada program</h4>
            <p>
              Belum ada Donor Program pada event ini.
            </p>
          </article>
        `;
  }

  setText(
    "programStatus",
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

      await RN_FRAPPE.call(
        "rescue_net.api_donor_program." +
        "create_program",
        {
          disaster_event:
            getEventId(),

          owner_type:
            form.owner_type?.value ||
            "organization",

          owner_id:
            form.owner_id.value.trim(),

          program_name:
            form.program_name.value.trim(),

          program_type:
            form.program_type.value.trim(),

          target_description:
            form.target_description.value
              .trim(),

          target_amount:
            Number(
              form.target_amount.value || 0
            ),

          target_unit:
            form.target_unit?.value ||
            "IDR",

          location:
            form.location?.value?.trim() ||
            null,

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      setText(
        "programStatus",
        "Program saved."
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

      await RN_FRAPPE.call(
        "rescue_net.api_donor_program." +
        "create_update",
        {
          program:
            form.program_id.value.trim(),

          update_type:
            form.update_type.value.trim(),

          progress_percent:
            Number(
              form.progress_percent.value ||
              0
            ),

          amount_spent:
            Number(
              form.amount_spent.value ||
              0
            ),

          update_title:
            form.update_title.value
              .trim(),

          update_notes:
            form.update_notes.value
              .trim()
        },
        {
          method: "POST"
        }
      );

      setText(
        "programStatus",
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
      setText(
        "programStatus",
        "Frappe client tidak tersedia."
      );
      return;
    }

    setupProgramForm();
    setupUpdateForm();

    const refresh =
      document.getElementById(
        "refreshPrograms"
      );

    if (refresh) {
      refresh.addEventListener(
        "click",
        () =>
          loadPrograms()
            .catch(
              err =>
                setText(
                  "programStatus",
                  err.message
                )
            )
      );
    }

    loadPrograms()
      .catch(
        err =>
          setText(
            "programStatus",
            err.message
          )
      );
  }
);
