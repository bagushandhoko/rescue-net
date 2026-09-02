/* ============================================================
 * New dashboard (matches organisasi & posko.png): calls
 * rescue_net.api_control_centre.org_posko_board / org_detail (guest).
 * Legacy create-org/create-posko forms + lists kept in <details>,
 * unchanged, still calling api_community_cluster.*.
 * ============================================================ */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
  function fmtTime(t) { return t ? String(t).slice(0, 16).replace("T", " ") : "-"; }

  var state = { orgs: [], view: "tree", selected: null };
  var BOARD_CACHE = null;

  function statusPillClass(status) {
    var l = String(status || "").toLowerCase();
    if (["verified", "official_verified", "community_verified"].indexOf(l) !== -1) return "ok";
    if (l === "pending" || l === "self_reported") return "warning";
    if (l === "critical") return "danger";
    return "";
  }

  function renderKpi(t) {
    $("#kpiOrgAktif").textContent = fmt(t.organisasi_aktif);
    $("#kpiPoskoAktif").textContent = fmt(t.posko_aktif);
    $("#kpiPendingVerif").textContent = fmt(t.pending_verifikasi);
    $("#kpiAnggota").textContent = fmt(t.anggota_terdaftar);
  }

  function orgCardHtml(o) {
    var isSel = state.selected === o.name;
    return (
      '<div class="rn-op-org' + (isSel ? " is-selected" : "") + '" data-org="' + esc(o.name) + '">' +
      "<div class=\"rn-op-org-head\"><b>" + esc(o.title) + '</b><span class="chip ' + statusPillClass(o.verification_status) + '">' + esc(o.verification_status) + "</span></div>" +
      '<small>' + fmt(o.posko_count) + " posko · " + fmt(o.member_count) + " anggota</small>" +
      "</div>"
    );
  }

  function renderTree(orgs) {
    var el = $("#orgTree");
    if (!orgs.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada organisasi dengan posko untuk event ini.</p>';
      return;
    }
    if (state.view === "list") {
      el.innerHTML = '<div class="rn-op-list">' + orgs.map(orgCardHtml).join("") + "</div>";
    } else {
      el.innerHTML = '<div class="rn-op-tree">' + orgs.map(function (o) {
        var isSel = state.selected === o.name;
        var poskoRows = (o.poskos || []).map(function (p) {
          return (
            '<a class="rn-op-posko-row" href="' + esc(p.href) + '">' +
            "<span>" + esc(p.title) + "</span>" +
            '<span class="chip ' + statusPillClass(p.status) + '">' + esc(p.status) + "</span></a>"
          );
        }).join("");
        return (
          '<div class="rn-op-tree-node' + (isSel ? " is-selected" : "") + '">' +
          '<div class="rn-op-tree-org" data-org="' + esc(o.name) + '">' +
          "<b>" + esc(o.title) + '</b><span class="chip ' + statusPillClass(o.verification_status) + '">' + fmt(o.posko_count) + " posko</span>" +
          "</div>" +
          '<div class="rn-op-tree-poskos">' + (poskoRows || '<span class="rn-muted">Belum ada posko.</span>') + "</div>" +
          "</div>"
        );
      }).join("") + "</div>";
    }
    el.querySelectorAll("[data-org]").forEach(function (node) {
      node.addEventListener("click", function (e) {
        if (e.target.closest(".rn-op-posko-row")) return;
        selectOrg(node.getAttribute("data-org"));
      });
    });
  }

  function renderDetail(detail) {
    var org = detail.org;
    var poskos = detail.poskos || [];
    var members = detail.members || [];
    var programs = detail.programs || [];
    var checklist = detail.checklist || {};

    var poskoRows = poskos.length
      ? poskos.map(function (p) {
          return '<div class="rn-op-detail-row"><b>' + esc(p.title) + '</b><span class="chip ' + statusPillClass(p.operational_status) + '">' + esc(p.operational_status) + "</span></div>";
        }).join("")
      : '<p class="rn-muted">Belum ada posko.</p>';

    var memberRows = members.length
      ? members.map(function (m) { return '<div class="rn-op-detail-row"><b>' + esc(m.title || m.name) + "</b><small>" + esc(m.role || "-") + "</small></div>"; }).join("")
      : '<p class="rn-muted">Belum ada anggota terdaftar.</p>';

    var programRows = programs.length
      ? programs.map(function (p) { return '<div class="rn-op-detail-row"><b>' + esc(p.program_name) + '</b><span class="chip">' + esc(p.status) + "</span></div>"; }).join("")
      : '<p class="rn-muted">Belum ada program.</p>';

    var checklistHtml = ["identitas_organisasi", "kontak_person", "trusted_verifier"].map(function (k) {
      var labels = { identitas_organisasi: "Identitas Organisasi", kontak_person: "Kontak Person Terisi", trusted_verifier: "Punya Trusted Verifier" };
      var ok = checklist[k];
      return '<li class="' + (ok ? "is-done" : "") + '">' + (ok ? "✓" : "○") + " " + labels[k] + "</li>";
    }).join("");

    $("#orgDetailPanel").innerHTML =
      '<div class="rn-op-detail-head"><h3>' + esc(org.title) + '</h3><span class="chip ' + statusPillClass(org.verification_status) + '">' + esc(org.verification_status) + "</span></div>" +
      '<p class="rn-muted">' + esc(org.organization_type) + " · " + esc(org.contact_person || "-") + "</p>" +
      '<div class="rn-tabs rn-op-detail-tabs">' +
      '<button type="button" class="rn-tab is-active" data-tab="ringkasan">Ringkasan</button>' +
      '<button type="button" class="rn-tab" data-tab="posko">Posko (' + poskos.length + ')</button>' +
      '<button type="button" class="rn-tab" data-tab="anggota">Anggota (' + members.length + ')</button>' +
      '<button type="button" class="rn-tab" data-tab="program">Program (' + programs.length + ')</button>' +
      "</div>" +
      '<div class="rn-op-tabpane" data-pane="ringkasan">' +
      '<div class="rn-va-trust"><span>Trust Level</span><b>' + esc(org.trust_level) + "</b>" +
      "<span>Verifier Terpercaya</span><b>" + fmt(org.trusted_verifier_count) + "</b></div>" +
      '<ul class="rn-op-checklist">' + checklistHtml + "</ul>" +
      '<p class="rn-muted">Terakhir diperbarui: ' + fmtTime(org.modified) + "</p>" +
      "</div>" +
      '<div class="rn-op-tabpane" data-pane="posko" hidden>' + poskoRows + "</div>" +
      '<div class="rn-op-tabpane" data-pane="anggota" hidden>' + memberRows + "</div>" +
      '<div class="rn-op-tabpane" data-pane="program" hidden>' + programRows + "</div>";

    $("#orgDetailPanel").querySelectorAll(".rn-op-detail-tabs .rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        $("#orgDetailPanel").querySelectorAll(".rn-op-detail-tabs .rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        $("#orgDetailPanel").querySelectorAll(".rn-op-tabpane").forEach(function (p) { p.hidden = p.getAttribute("data-pane") !== tab.getAttribute("data-tab"); });
      });
    });
  }

  async function selectOrg(name) {
    state.selected = name;
    renderTree(state.orgs);
    $("#orgDetailPanel").innerHTML = '<p class="rn-muted">Memuat…</p>';
    try {
      var detail = await window.RN_FRAPPE.call("rescue_net.api_control_centre.org_detail", { organization: name });
      renderDetail(detail);
    } catch (err) {
      $("#orgDetailPanel").innerHTML = '<p class="rn-muted">Gagal memuat: ' + esc(err && err.message || err) + "</p>";
    }
  }

  function setupViewTabs() {
    document.querySelectorAll("#treeViewTabs .rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll("#treeViewTabs .rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        state.view = tab.getAttribute("data-view");
        renderTree(state.orgs);
      });
    });
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call("rescue_net.api_control_centre.org_posko_board", { disaster_event: getEventId() });
    BOARD_CACHE = data;
    state.orgs = data.orgs || [];
    $("#orgUpdated").textContent = "Organisasi · Diperbarui " + fmtTime(data.generated_at).slice(11, 16);
    renderKpi(data.totals || {});
    renderTree(state.orgs);
    if (state.orgs.length && !state.selected) selectOrg(state.orgs[0].name);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    setupViewTabs();
    loadBoard()
      .then(function () {
        var el = document.getElementById("orgStatus");
        if (el) el.textContent = "Dimuat " + state.orgs.length + " organisasi.";
      })
      .catch(function (err) {
        var el = document.getElementById("orgStatus");
        if (el) el.textContent = "Gagal memuat: " + (err && err.message || err);
      });
  });
})();

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
      const el = form.elements;
      const val = n => (el[n] && el[n].value || "").trim();

      const title = val("name") || val("posko_name") || val("title");
      const poskoType = val("node_type") || val("posko_type");
      const address = val("location") || val("address");

      if (!title || !poskoType || !address) {
        statusMsg("Nama Posko, tipe, dan alamat wajib diisi.");
        return;
      }

      const functions = [];
      if (el.fn_logistics && el.fn_logistics.checked) functions.push("logistics");
      if (el.fn_shelter && el.fn_shelter.checked) functions.push("shelter");
      if (el.fn_kitchen && el.fn_kitchen.checked) functions.push("kitchen");
      if (!functions.length && ["logistics", "shelter", "kitchen"].includes(poskoType)) {
        functions.push(poskoType);
      }
      const logisticsRole = val("logistics_role");

      statusMsg("Menyimpan posko…");

      const created = await RN_FRAPPE.call(
        "rescue_net.api_community_cluster.create_posko",
        {
          title,
          posko_type: poskoType,
          address,
          organization: val("organization_id") || val("organization") || null
        },
        { method: "POST" }
      );

      // apply functions + logistics role
      const poskoId =
        (created && (created.name || created.posko || created.id)) || title;
      try {
        await RN_FRAPPE.call(
          "rescue_net.api_control_centre.set_posko_functions",
          {
            posko: poskoId,
            functions: JSON.stringify(functions),
            logistics_role: logisticsRole || ""
          },
          { method: "POST" }
        );
      } catch (fe) {
        statusMsg("Posko dibuat, tapi gagal set fungsi: " + (fe.message || fe));
      }

      form.reset();
      statusMsg("Posko tersimpan" + (functions.length ? " (fungsi: " + functions.join(", ") + ")" : "") + ".");
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
