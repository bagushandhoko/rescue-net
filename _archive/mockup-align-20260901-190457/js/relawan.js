const RELAWAN_DEFAULT_POSKO =
  new URLSearchParams(
    location.search
  ).get("posko") ||
  "posko-sim-logistik";


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function statusMsg(msg) {
  const el =
    document.querySelector(
      "[data-relawan-status]"
    ) ||
    document.getElementById(
      "relawanStatus"
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


function renderSummary(ctx) {
  const target =
    document.querySelector(
      "[data-relawan-summary]"
    ) ||
    document.getElementById(
      "relawanSummary"
    );

  if (!target) return;

  const profiles =
    ctx.profiles || [];

  const assignments =
    ctx.assignments || [];

  const available =
    profiles.filter(
      x =>
        x.availability_status ===
        "available"
    ).length;

  target.innerHTML = `
    <div>
      <span>Volunteers</span>
      <b>${profiles.length}</b>
    </div>

    <div>
      <span>Available</span>
      <b>${available}</b>
    </div>

    <div>
      <span>Assignments</span>
      <b>${assignments.length}</b>
    </div>

    <div>
      <span>Mode</span>
      <b>${safe(ctx.mode)}</b>
    </div>
  `;
}


function renderVolunteers(items) {
  const target =
    document.querySelector(
      "[data-relawan-list]"
    ) ||
    document.getElementById(
      "relawanList"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(v => card(
          v.volunteer_name,
          `Skill: ${safe(v.main_skill)}<br>` +
          `Tags: ${safe(v.skill_tags)}<br>` +
          `Location: ${safe(v.current_location)}<br>` +
          `Contact: ${safe(v.contact)}`,
          v.availability_status
        )).join("")
      : card(
          "Belum ada volunteer",
          "Belum ada RN Volunteer Profile.",
          "empty"
        );
}


function renderAssignments(items) {
  const target =
    document.querySelector(
      "[data-relawan-assignments]"
    ) ||
    document.getElementById(
      "relawanAssignments"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(a => card(
          a.task_title,
          `Volunteer: ${safe(a.volunteer)}<br>` +
          `Posko: ${safe(a.posko)}<br>` +
          `Priority: ${safe(a.priority)}<br>` +
          `${safe(a.assignment_notes)}`,
          a.assignment_status
        )).join("")
      : card(
          "Belum ada assignment",
          "Belum ada RN Volunteer Assignment.",
          "empty"
        );
}


function fillVolunteerSelect(items) {
  const select =
    document.querySelector(
      "[name='volunteer_id']"
    );

  if (!select) return;

  select.innerHTML =
    `<option value="">Select volunteer</option>` +
    items.map(v => `
      <option value="${v.name}">
        ${safe(v.volunteer_name)}
      </option>
    `).join("");
}


async function loadRelawan() {
  statusMsg(
    "Loading volunteers from Frappe..."
  );

  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_volunteer.dashboard",
      {
        posko:
          RELAWAN_DEFAULT_POSKO
      }
    );

  renderSummary(ctx);
  renderVolunteers(
    ctx.profiles || []
  );
  renderAssignments(
    ctx.assignments || []
  );
  fillVolunteerSelect(
    ctx.profiles || []
  );

  statusMsg(
    "Loaded from Frappe"
  );
}


function setupVolunteerForm() {
  const form =
    document.querySelector(
      "[data-create-relawan]"
    ) ||
    document.getElementById(
      "relawanForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const tags =
        form.skill_tags.value
          .trim();

      const mainSkill =
        (
          tags.split(
            /[,;|]/
          )[0] ||
          "general"
        ).trim();

      await RN_FRAPPE.call(
        "rescue_net.api_volunteer.create_profile",
        {
          volunteer_name:
            form.volunteer_name.value
              .trim(),

          main_skill:
            mainSkill,

          contact:
            form.contact.value.trim(),

          skill_tags:
            tags,

          current_location:
            form.current_location.value
              .trim(),

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Volunteer profile saved."
      );

      form.reset();

      await loadRelawan();
    }
  );
}


function setupAssignmentForm() {
  const form =
    document.querySelector(
      "[data-create-relawan-assignment]"
    ) ||
    document.getElementById(
      "assignmentForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_volunteer.create_assignment",
        {
          volunteer:
            form.volunteer_id.value,

          posko:
            form.assigned_to_id.value
              .trim(),

          task_title:
            form.task_name.value
              .trim(),

          assignment_type:
            form.assigned_to_type.value ||
            "posko",

          priority:
            form.priority.value ||
            "normal",

          assignment_notes:
            form.task_description.value
              .trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Volunteer assignment saved."
      );

      form.reset();

      await loadRelawan();
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

    setupVolunteerForm();
    setupAssignmentForm();

    const btn =
      document.querySelector(
        "[data-refresh-relawan]"
      ) ||
      document.getElementById(
        "refreshRelawan"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () =>
          loadRelawan()
            .catch(
              err =>
                statusMsg(err.message)
            )
      );
    }

    loadRelawan()
      .catch(
        err =>
          statusMsg(err.message)
      );
  }
);
