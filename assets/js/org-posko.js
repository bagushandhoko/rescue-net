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

  target.innerHTML =
    items.length
      ? items.map(p => card(
          p.title ||
          p.posko_name ||
          p.name,

          `ID: ${safe(p.name)}<br>` +
          `Type: ${safe(p.posko_type)}<br>` +
          `Organization: ${safe(p.organization)}<br>` +
          `Address: ${safe(p.address)}`,

          p.operational_status ||
          p.verification_status
        )).join("")
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

  const [
    organizations,
    poskos
  ] = await Promise.all([
    RN_FRAPPE.call(
      "rescue_net.api_community_cluster." +
      "list_organizations",
      {}
    ),

    RN_FRAPPE.call(
      "rescue_net.api_community_cluster." +
      "list_poskos",
      {}
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

  renderOrganizations(
    orgRows
  );

  renderPoskos(
    poskoRows
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
      poskoRows.length;
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
      poskoRows
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
