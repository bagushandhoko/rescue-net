function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function currentEventParam() {
  const p = new URLSearchParams(location.search);
  return (
    p.get("event") ||
    p.get("disaster_event_id") ||
    ""
  );
}


// Public per-event posko list (guest-allowed), normalised to the shape
// renderPoskos expects, with Control Centre sharing mode included.
async function publicEventPoskos() {
  const event = currentEventParam();
  if (!event) return [];

  let points = [];
  try {
    const res = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.event_poskos",
      { disaster_event: event }
    );
    points = Array.isArray(res) ? res : (res.points || res.items || []);
  } catch (e) {
    return [];
  }

  return points.map(pt => ({
    name: pt.posko_id || pt.id || pt.name,
    legacy_id: pt.id,
    title: pt.name,
    posko_type: pt.posko_type,
    organization: pt.organization,
    address: pt.address,
    operational_status: pt.status,
    verification_status: pt.status,
    share_mode: pt.share_mode,
    detail_allowed: pt.detail_allowed
  }));
}


// Tag each posko row with { share_mode, detail_allowed } from the
// Control Centre visibility rules for the active event.
async function mergeShareMode(poskoRows) {
  const event = currentEventParam();
  if (!event || !poskoRows || !poskoRows.length) return;

  let points = [];
  try {
    const res = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.event_poskos",
      { disaster_event: event }
    );
    points = Array.isArray(res) ? res : (res.points || res.items || []);
  } catch (e) {
    return;
  }

  const byKey = {};
  points.forEach(pt => {
    [pt.posko_id, pt.id, pt.name].forEach(k => {
      if (k) byKey[String(k)] = pt;
    });
  });

  poskoRows.forEach(p => {
    const hit =
      byKey[String(p.name)] ||
      byKey[String(p.legacy_id)] ||
      byKey[String(p.id)];
    if (hit) {
      p.share_mode = hit.share_mode;
      p.detail_allowed = hit.detail_allowed;
    }
  });
}


function statusMsg(msg) {
  const el =
    document.getElementById(
      "orgPoskoStatus"
    ) ||
    document.querySelector(
      "[data-org-posko-status]"
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


function renderOrganizations(items) {
  const target =
    document.querySelector(
      "[data-rn-organizations]"
    ) ||
    document.getElementById(
      "organizationList"
    );

  if (!target) return;

  target.innerHTML =
    items.length
      ? items.map(o => card(
          o.title ||
          o.organization_name ||
          o.name,

          `ID: ${safe(o.name)}<br>` +
          `Type: ${safe(o.organization_type)}<br>` +
          `Contact: ${safe(o.contact_person)}`,

          o.verification_status ||
          o.status
        )).join("")
      : card(
          "Belum ada organisasi",
          "Belum ada RN Organization.",
          "empty"
        );
}


function renderPoskos(items) {
  const target =
    document.querySelector(
      "[data-rn-poskos]"
    ) ||
    document.getElementById(
      "poskoList"
    );

  if (!target) return;

  const event = currentEventParam();

  target.innerHTML =
    items.length
      ? items.map(p => {
          const pid =
            p.name || p.legacy_id || p.id || "";

          const shareTxt =
            p.share_mode === "full"
              ? "koordinasi: detail terbuka"
              : (
                  p.share_mode === "summary"
                    ? "koordinasi: ringkasan (tertutup)"
                    : ""
                );

          const link =
            `posko-detail.html?id=${
              encodeURIComponent(pid)
            }${
              event
                ? "&event=" + encodeURIComponent(event)
                : ""
            }`;

          return card(
            p.title || p.posko_name || p.name,

            `ID: ${safe(p.name)}<br>` +
            `Type: ${safe(p.posko_type)}<br>` +
            `Organization: ${safe(p.organization)}<br>` +
            `Address: ${safe(p.address)}<br>` +
            (
              shareTxt
                ? `<b>${shareTxt}</b><br>`
                : ""
            ) +
            `<a href="${link}">${
              p.detail_allowed
                ? "Buka detail posko →"
                : "Buka ringkasan posko →"
            }</a>`,

            p.operational_status ||
            p.verification_status
          );
        }).join("")
      : card(
          "Belum ada Posko",
          "Belum ada RN Posko.",
          "empty"
        );
}


function fillOrganizationSelect(items) {
  const select =
    document.querySelector(
      '#poskoForm [name="organization"]'
    ) ||
    document.querySelector(
      '[data-create-posko] [name="organization"]'
    );

  if (
    !select ||
    select.tagName !== "SELECT"
  ) {
    return;
  }

  select.innerHTML =
    `<option value="">Tanpa organisasi</option>` +
    items.map(o => `
      <option value="${safe(o.name)}">
        ${safe(o.title || o.name)}
      </option>
    `).join("");
}


async function loadOrgPosko() {
  statusMsg(
    "Loading Organization & Posko from Frappe..."
  );

  // A guest / non-member gets a permission error from the login-scoped
  // endpoints - treat that as "no rows" so the public fallback can run.
  const softCall = (method) =>
    RN_FRAPPE.call(method, {}).catch(() => []);

  const [
    organizations,
    poskos
  ] = await Promise.all([
    softCall(
      "rescue_net.api_community_cluster.list_organizations"
    ),
    softCall(
      "rescue_net.api_community_cluster.list_poskos"
    )
  ]);

  /*
   * Toleransi response:
   * backend dapat mengembalikan array langsung
   * atau object wrapper.
   */
  const orgRows =
    Array.isArray(organizations)
      ? organizations
      : (
          organizations.organizations ||
          organizations.items ||
          []
        );

  const poskoRows =
    Array.isArray(poskos)
      ? poskos
      : (
          poskos.poskos ||
          poskos.items ||
          []
        );

  await mergeShareMode(poskoRows);

  // Fallback: if the (login-scoped) posko list is empty but an event is
  // selected, show every posko of that event from the public endpoint,
  // already carrying the Control Centre sharing mode.
  let poskoDisplay = poskoRows;
  if (!poskoDisplay.length && currentEventParam()) {
    poskoDisplay = await publicEventPoskos();
  }

  renderOrganizations(
    orgRows
  );

  renderPoskos(
    poskoDisplay
  );

  fillOrganizationSelect(
    orgRows
  );

  const orgKpi =
    document.getElementById(
      "kpiOrgCount"
    );

  const poskoKpi =
    document.getElementById(
      "kpiPoskoCount"
    );

  const pendingKpi =
    document.getElementById(
      "kpiPendingCount"
    );

  if (orgKpi) {
    orgKpi.textContent =
      orgRows.length;
  }

  if (poskoKpi) {
    poskoKpi.textContent =
      poskoDisplay.length;
  }

  if (pendingKpi) {
    pendingKpi.textContent =
      orgRows.filter(x => {
        const status = String(
          x.verification_status ||
          x.status ||
          ""
        ).toLowerCase();

        return (
          status === "pending" ||
          status === "unverified"
        );
      }).length;
  }

  statusMsg(
    "Loaded from Frappe"
  );

  return {
    organizations:
      orgRows,
    poskos:
      poskoDisplay
  };
}


function setupOrganizationForm() {
  const form =
    document.querySelector(
      "[data-rn-create-org]"
    ) ||
    document.getElementById(
      "organizationForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const title =
        form.title?.value?.trim() ||
        form.organization_name
          ?.value
          ?.trim();

      if (!title) {
        statusMsg(
          "Nama organisasi wajib diisi."
        );
        return;
      }

      statusMsg(
        "Saving Organization..."
      );

      await RN_FRAPPE.call(
        "rescue_net.api_community_cluster." +
        "create_organization",
        {
          title,

          organization_type:
            form.organization_type
              ?.value ||
            "community",

          contact_person:
            form.contact_person
              ?.value
              ?.trim() ||
            null,

          notes:
            form.notes
              ?.value
              ?.trim() ||
            null
        },
        {
          method: "POST"
        }
      );

      form.reset();

      statusMsg(
        "Organization saved."
      );

      await loadOrgPosko();
    }
  );
}


function setupPoskoForm() {
  const form =
    document.querySelector(
      "[data-rn-create-posko]"
    ) ||
    document.getElementById(
      "poskoForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      const title =
        form.title?.value?.trim() ||
        form.posko_name
          ?.value
          ?.trim();

      const poskoType =
        form.posko_type
          ?.value
          ?.trim();

      const address =
        form.address
          ?.value
          ?.trim();

      if (
        !title ||
        !poskoType ||
        !address
      ) {
        statusMsg(
          "Nama Posko, tipe, dan alamat wajib diisi."
        );
        return;
      }

      statusMsg(
        "Saving Posko..."
      );

      await RN_FRAPPE.call(
        "rescue_net.api_community_cluster." +
        "create_posko",
        {
          title,

          posko_type:
            poskoType,

          address,

          organization:
            form.organization
              ?.value
              ?.trim() ||
            null
        },
        {
          method: "POST"
        }
      );

      form.reset();

      statusMsg(
        "Posko saved."
      );

      await loadOrgPosko();
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

    setupOrganizationForm();
    setupPoskoForm();

    const refresh =
      document.getElementById(
        "refreshOrgPosko"
      ) ||
      document.querySelector(
        "[data-refresh-org-posko]"
      );

    if (refresh) {
      refresh.addEventListener(
        "click",
        () =>
          loadOrgPosko().catch(
            err =>
              statusMsg(
                err.message
              )
          )
      );
    }

    loadOrgPosko().catch(
      err =>
        statusMsg(
          err.message
        )
    );
  }
);
