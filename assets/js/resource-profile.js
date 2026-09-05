/* ============================================================
 * New dashboard (matches "Profil Sumber Daya.png"): calls
 * rescue_net.api_resource_tools.resource_profile_board (guest,
 * defaults to the logged-in user or a seeded demo volunteer) +
 * self-service writes add_personal_resource / add_personal_support_need /
 * api_volunteer.update_profile. Legacy multi-category directory
 * (Organizations/Posko/Volunteers/Tools) kept inside <details>,
 * still calls api_resource_tools.dashboard / api_ai.context /
 * api_volunteer.control_centre_volunteers.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_resource_tools.resource_profile_board";
  var BOARD = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function getUserParam() { return new URLSearchParams(window.location.search).get("user") || null; }
  function shortDate(s) { return s ? String(s).slice(0, 10) : "-"; }
  function initials(name) {
    var parts = String(name || "?").trim().split(/\s+/);
    return ((parts[0] || "")[0] || "") + ((parts[1] || "")[0] || "");
  }

  function renderChips(chips) {
    $("#chipPeran").textContent = chips.peran_utama || "-";
    $("#chipPeranSub").textContent = chips.peran_tipe || "";
    $("#chipTrust").textContent = chips.trust_label || "-";
    $("#chipEmailLabel").textContent = chips.email_verified ? "Terverifikasi" : "Belum";
    $("#chipPhoneLabel").textContent = chips.phone_verified ? "Terverifikasi" : "Belum";
    $("#chipIdLabel").textContent = chips.id_verified ? "Terverifikasi" : "Belum";
  }

  function renderIdentity(identity) {
    $("#profileAvatar").textContent = initials(identity.name).toUpperCase();
    $("#profileName").textContent = identity.name || "-";
    $("#profileAktif").textContent = identity.aktif ? "Aktif" : "Tidak Aktif";
    $("#profileAktif").className = "chip " + (identity.aktif ? "ok" : "");
    $("#profileRoleOrg").textContent = (identity.role || "-") + (identity.organization ? " — " + identity.organization : "");
    $("#profileLocation").innerHTML = '<span class="rn-inline-icon" data-icon="map-pin"></span>' + esc(identity.location || "-");
    $("#profileEmailLine").textContent = identity.email || "";
    $("#profilePhoneLine").textContent = identity.phone || "";
    $("#profileAbout").textContent = identity.about || "-";
    $("#profileJoined").textContent = identity.joined_at ? "Bergabung sejak " + shortDate(identity.joined_at) : "";
    var editForm = $("#editProfilForm");
    editForm.current_location.value = identity.location === "-" ? "" : (identity.location || "");
    editForm.notes.value = identity.about === "-" ? "" : (identity.about || "");
  }

  function itemRow(title, sub, chipLabel, icon) {
    return (
      '<div class="rn-pr-item">' +
      '<span class="rn-pr-item-main">' +
      (icon ? '<span class="rn-pr-item-icon" data-icon="' + icon + '"></span>' : "") +
      "<span><b>" + esc(title) + "</b><small>" + esc(sub || "") + "</small></span>" +
      "</span>" +
      (chipLabel ? '<span class="chip">' + esc(chipLabel) + "</span>" : "") + "</div>"
    );
  }

  function skillIcon(label) {
    var l = String(label || "").toLowerCase();
    if (/driver|kendara|motor|mobil|truk/.test(l)) return "truck";
    if (/radio|komunikasi/.test(l)) return "radio";
    if (/perawat|medis|kesehatan|p3k|pertolongan/.test(l)) return "cross";
    if (/dapur|masak|logistik pangan/.test(l)) return "pot";
    return "wrench";
  }

  function renderSkills(skills) {
    var el = $("#skillList");
    el.innerHTML = skills.length
      ? skills.map(function (s) { return itemRow(s.label, "", s.status_label, skillIcon(s.label)); }).join("")
      : '<p class="rn-muted">Belum ada keahlian tercatat.</p>';
    document.dispatchEvent(new CustomEvent("rn:icons-refresh"));
  }

  function renderResourceList(elId, rows, icon) {
    var el = $(elId);
    el.innerHTML = rows.length
      ? rows.map(function (r) {
          var sub = [r.capacity_description, r.current_location].filter(Boolean).join(" · ");
          var qty = (r.quantity && r.quantity != 1) ? (r.quantity + " " + (r.unit || "")) : "";
          return itemRow(r.resource_name + (qty ? " · " + qty : ""), sub, r.availability_status === "available" ? "Tersedia" : r.availability_status, icon);
        }).join("")
      : '<p class="rn-muted">Belum ada data.</p>';
    document.dispatchEvent(new CustomEvent("rn:icons-refresh"));
  }

  function renderLines(elId, lines, icon) {
    var el = $(elId);
    el.innerHTML = lines.length
      ? lines.map(function (l) { return itemRow(l, "", "", icon); }).join("")
      : '<p class="rn-muted">Belum ada data.</p>';
    document.dispatchEvent(new CustomEvent("rn:icons-refresh"));
  }

  var PRIORITY_LABEL = { normal: "Normal", urgent: "Urgent", critical: "Kritis" };
  function renderNeeds(rows) {
    var el = $("#kebutuhanList");
    el.innerHTML = rows.length
      ? rows.map(function (r) {
          return itemRow(r.tool_name, r.needed_for || "", r.request_status === "requested" ? "Dibutuhkan" : r.request_status, "wrench");
        }).join("")
      : '<p class="rn-muted">Belum ada kebutuhan diajukan.</p>';
    document.dispatchEvent(new CustomEvent("rn:icons-refresh"));
  }

  function toggleForm(formId) {
    var form = document.getElementById(formId);
    if (!form) return;
    document.querySelectorAll(".rn-pr-add-form.is-open").forEach(function (f) {
      if (f !== form) f.classList.remove("is-open");
    });
    form.classList.toggle("is-open");
  }

  function setupToggles() {
    document.querySelectorAll("[data-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () { toggleForm(btn.getAttribute("data-toggle")); });
    });
  }

  function msgEl(form) { return form.querySelector(".rn-pr-add-msg"); }

  function setupResourceForms() {
    ["kendaraanForm", "fasilitasForm", "barangForm"].forEach(function (id) {
      var form = document.getElementById(id);
      if (!form) return;
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var msg = msgEl(form);
        msg.textContent = "Menyimpan…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_resource_tools.add_personal_resource", {
            resource_name: form.resource_name.value.trim(),
            category: form.getAttribute("data-category"),
            resource_type: form.getAttribute("data-rtype"),
            quantity: form.quantity ? (Number(form.quantity.value) || 1) : 1,
            unit: form.unit ? (form.unit.value.trim() || "unit") : "unit",
            capacity_description: form.capacity_description ? form.capacity_description.value.trim() : null,
            current_location: form.current_location ? form.current_location.value.trim() : null,
          }, { method: "POST" });
          form.reset();
          form.classList.remove("is-open");
          await loadBoard();
        } catch (err) {
          msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
        }
      });
    });
  }

  function combinedList(rawText, newLine) {
    var lines = (rawText || "").split("\n").map(function (l) { return l.trim(); }).filter(Boolean);
    lines.push(newLine);
    return lines.join("\n");
  }

  function setupSkillForm() {
    var form = document.getElementById("skillForm");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = msgEl(form);
      if (!BOARD || !BOARD.volunteer_profile) {
        msg.textContent = "Belum ada profil relawan untuk akun ini.";
        return;
      }
      var newSkill = form.label.value.trim();
      var combined = (BOARD.raw.skill_tags ? BOARD.raw.skill_tags + ", " : "") + newSkill;
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_volunteer.update_profile", {
          volunteer: BOARD.volunteer_profile,
          skill_tags: combined,
        }, { method: "POST" });
        form.reset();
        form.classList.remove("is-open");
        await loadBoard();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  function setupWilayahForm() {
    var form = document.getElementById("wilayahForm");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = msgEl(form);
      if (!BOARD || !BOARD.volunteer_profile) {
        msg.textContent = "Belum ada profil relawan untuk akun ini.";
        return;
      }
      var line = form.area.value.trim() + " - " + form.peran.value;
      var combined = combinedList(BOARD.raw.service_areas, line);
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_volunteer.update_profile", {
          volunteer: BOARD.volunteer_profile,
          service_areas: combined,
        }, { method: "POST" });
        form.reset();
        form.classList.remove("is-open");
        await loadBoard();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  function setupJadwalForm() {
    var form = document.getElementById("jadwalForm");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = msgEl(form);
      if (!BOARD || !BOARD.volunteer_profile) {
        msg.textContent = "Belum ada profil relawan untuk akun ini.";
        return;
      }
      var line = form.hari.value.trim() + ": " + form.jam.value.trim();
      var combined = combinedList(BOARD.raw.availability_schedule, line);
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_volunteer.update_profile", {
          volunteer: BOARD.volunteer_profile,
          availability_schedule: combined,
        }, { method: "POST" });
        form.reset();
        form.classList.remove("is-open");
        await loadBoard();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  function setupKebutuhanForm() {
    var form = document.getElementById("kebutuhanForm");
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = msgEl(form);
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_resource_tools.add_personal_support_need", {
          tool_name: form.tool_name.value.trim(),
          needed_for: form.needed_for.value.trim(),
          priority: form.priority.value,
        }, { method: "POST" });
        form.reset();
        form.classList.remove("is-open");
        await loadBoard();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  function setupEditProfil() {
    var btn = $("#editProfilBtn");
    var form = $("#editProfilForm");
    var cancel = $("#editProfilCancel");
    btn.addEventListener("click", function () { form.classList.toggle("is-open"); });
    cancel.addEventListener("click", function () { form.classList.remove("is-open"); });
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#editProfilMsg");
      if (!BOARD || !BOARD.volunteer_profile) {
        msg.textContent = "Belum ada profil relawan untuk akun ini — tidak bisa diedit lewat form ini.";
        return;
      }
      msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_volunteer.update_profile", {
          volunteer: BOARD.volunteer_profile,
          current_location: form.current_location.value.trim(),
          notes: form.notes.value.trim(),
        }, { method: "POST" });
        form.classList.remove("is-open");
        await loadBoard();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  async function loadBoard() {
    var params = {};
    var u = getUserParam();
    if (u) params.user_account = u;
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, params);
    BOARD = data;
    $("#resourceUpdated").textContent = "Profil · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    $("#resourceStatus").textContent = data.can_edit ? "Ini profil Anda — bisa diedit." : "Melihat profil " + (data.identity.name || "") + " (mode lihat).";
    $("#resourceLastUpdated").textContent = "Data terakhir diperbarui: " + String(data.generated_at || "").slice(0, 16).replace("T", " ") + " WIB";

    renderChips(data.chips || {});
    renderIdentity(data.identity || {});
    renderSkills(data.skills || []);
    renderResourceList("#kendaraanList", data.kendaraan || [], "truck");
    renderResourceList("#fasilitasList", data.fasilitas || [], "building");
    renderResourceList("#barangList", data.barang_bantuan || [], "box");
    renderLines("#wilayahList", data.service_areas || [], "map-pin");
    renderLines("#jadwalList", data.schedule || [], "clock");
    renderNeeds(data.support_needs || []);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    setupToggles();
    setupResourceForms();
    setupSkillForm();
    setupWilayahForm();
    setupJadwalForm();
    setupKebutuhanForm();
    setupEditProfil();
    loadBoard().catch(function (err) { console.error("[resource profile board]", err); $("#resourceStatus").textContent = "Gagal memuat: " + err.message; });
  });
})();

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
    ).catch(
      () => ({
        organizations: [],
        resources: []
      })
    ),

    RN_FRAPPE.call(
      "rescue_net.api_ai.context",
      {
        disaster_event_id:
          eventId
      }
    ).catch(
      () => ({
        poskos: []
      })
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

  setText("kpiOrg", organizations.length);
  setText("kpiPosko", poskos.length);
  setText("kpiVolunteer", volunteerRows.filter(v => v.availability_status === "available").length);
  setText("kpiResource", resourceRows.length);

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
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
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
                console.error(err)
            )
      );
    }

    loadResourceProfile()
      .catch(
        err =>
          console.error(err)
      );
  }
);
