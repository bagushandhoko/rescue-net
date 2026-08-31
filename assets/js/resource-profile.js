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


function setText(id, value) {
  const el =
    document.getElementById(id);

  if (el) {
    el.textContent = value;
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


async function loadResourceProfile() {
  const eventId =
    getEventId();

  setText(
    "resourceStatus",
    "Loading Frappe resources..."
  );

  const [
    resources,
    ai,
    volunteers
  ] = await Promise.all([
    RN_FRAPPE.call(
      "rescue_net.api_resource_tools.dashboard",
      {
        disaster_event:
          eventId
      }
    ),

    RN_FRAPPE.call(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          eventId
      }
    ),

    RN_FRAPPE.call(
      "rescue_net.api_volunteer.control_centre_volunteers",
      {}
    ).catch(
      () => ({
        profiles: []
      })
    )
  ]);

  const organizations =
    resources.organizations || [];

  const poskos =
    ai.poskos || [];

  const volunteerRows =
    volunteers.profiles ||
    volunteers.volunteers ||
    [];

  const resourceRows =
    resources.resources || [];

  const organizationList =
    document.getElementById(
      "organizationList"
    );

  if (organizationList) {
    organizationList.innerHTML =
      organizations.length
        ? organizations.map(o => card(
            o.organization_name ||
            o.title ||
            o.name,
            `Type: ${safe(o.organization_type)}`,
            o.verification_status
          )).join("")
        : card(
            "Organization data",
            "Resource dashboard belum mengirim koleksi organization terpisah.",
            "Frappe"
          );
  }

  const poskoList =
    document.getElementById(
      "poskoList"
    );

  if (poskoList) {
    poskoList.innerHTML =
      poskos.length
        ? poskos.map(p => card(
            p.title ||
            p.posko_name ||
            p.name,
            `${safe(p.location || p.address)}<br>` +
            `${safe(p.operational_status)}`,
            p.verification_status
          )).join("")
        : card(
            "Belum ada Posko",
            "Tidak ada Posko pada event.",
            "empty"
          );
  }

  const volunteerList =
    document.getElementById(
      "volunteerList"
    );

  if (volunteerList) {
    volunteerList.innerHTML =
      volunteerRows.length
        ? volunteerRows.map(v => card(
            v.volunteer_name,
            `Skill: ${safe(v.main_skill)}<br>` +
            `Location: ${safe(v.current_location)}`,
            v.availability_status
          )).join("")
        : card(
            "Belum ada volunteer",
            "Tidak ada Volunteer Profile.",
            "empty"
          );
  }

  const resourceList =
    document.getElementById(
      "resourceList"
    );

  if (resourceList) {
    resourceList.innerHTML =
      resourceRows.length
        ? resourceRows.map(r => card(
            r.resource_name,
            `${safe(r.quantity)} ${safe(r.unit)}<br>` +
            `Type: ${safe(r.resource_type)}<br>` +
            `Location: ${safe(r.current_location)}<br>` +
            `Coverage: ${safe(r.coverage_area)}`,
            r.availability_status
          )).join("")
        : card(
            "Belum ada Resource Profile",
            "Tidak ada resource pada event ini.",
            "empty"
          );
  }

  setText(
    "resourceStatus",
    "Loaded from Frappe"
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      setText(
        "resourceStatus",
        "Frappe client tidak tersedia."
      );
      return;
    }

    const refresh =
      document.getElementById(
        "refreshResource"
      );

    if (refresh) {
      refresh.addEventListener(
        "click",
        () =>
          loadResourceProfile()
            .catch(
              err =>
                setText(
                  "resourceStatus",
                  err.message
                )
            )
      );
    }

    loadResourceProfile()
      .catch(
        err =>
          setText(
            "resourceStatus",
            err.message
          )
      );
  }
);
