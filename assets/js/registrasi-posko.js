/* Registrasi & Verifikasi Posko — pages/registrasi-posko.html (NEW page)
 * Backend: rescue_net.api_control_centre.posko_registry_board /
 * posko_verification_checklist (guest reads) + api_community_cluster.
 * create_posko / submit_posko_verification / delete_posko (login writes).
 */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function fmtTime(t) { return t ? String(t).slice(0, 16).replace("T", " ") : "-"; }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }

  var PAGE_SIZE = 8;
  var state = { rows: [], filtered: [], page: 0, query: "", selected: null };

  function statusPillClass(status) {
    var l = String(status || "").toLowerCase();
    if (["official_verified", "verified"].indexOf(l) !== -1) return "ok";
    if (l === "community_verified") return "ok";
    if (l === "suspicious") return "danger";
    return "warning";
  }

  function statusLabel(status) {
    var map = { self_reported: "Pending", pending: "Pending", official_verified: "Official Verified",
      community_verified: "Community Verified", verified: "Terverifikasi", needs_correction: "Perlu Revisi" };
    return map[status] || status || "-";
  }

  function renderKpi(t) {
    $("#kpiAktif").textContent = fmt(t.posko_aktif);
    $("#kpiPending").textContent = fmt(t.pending_verification);
    $("#kpiOfficial").textContent = fmt(t.official_verified);
    $("#kpiCommunity").textContent = fmt(t.community_verified);
  }

  function applyFilter() {
    var q = state.query.toLowerCase();
    state.filtered = !q ? state.rows : state.rows.filter(function (r) {
      return (r.title + " " + r.lokasi + " " + r.pic).toLowerCase().indexOf(q) !== -1;
    });
    state.page = 0;
    renderTable();
  }

  function renderTable() {
    var total = state.filtered.length;
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    var slice = state.filtered.slice(state.page * PAGE_SIZE, state.page * PAGE_SIZE + PAGE_SIZE);

    var body = $("#registryBody");
    if (!slice.length) {
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Tidak ada posko.</em></td></tr>';
    } else {
      body.innerHTML = slice.map(function (r) {
        var isSel = state.selected === r.name;
        return (
          '<tr class="rn-ba-row' + (isSel ? " is-selected" : "") + '" data-name="' + esc(r.name) + '">' +
          "<td><b>" + esc(r.title) + "</b></td><td>" + esc(r.jenis || "-") + "</td><td>" + esc(r.lokasi) + "</td>" +
          "<td>" + esc(r.pic) + "</td><td>" + fmt(r.kapasitas) + "</td>" +
          '<td><span class="chip ' + statusPillClass(r.status_verifikasi) + '">' + esc(statusLabel(r.status_verifikasi)) + "</span></td>" +
          "<td>" + fmtTime(r.terakhir_diperbarui) + "</td></tr>"
        );
      }).join("");
    }
    body.querySelectorAll("tr[data-name]").forEach(function (tr) {
      tr.addEventListener("click", function () { selectPosko(tr.getAttribute("data-name")); });
    });

    $("#registryShown").textContent = total ? "Menampilkan " + (state.page * PAGE_SIZE + 1) + "-" + Math.min(total, (state.page + 1) * PAGE_SIZE) + " dari " + total : "0 posko";
    var pager = $("#registryPager");
    var btns = [];
    for (var i = 0; i < pages; i++) btns.push('<button type="button" class="rn-ev-page' + (i === state.page ? " is-active" : "") + '" data-page="' + i + '">' + (i + 1) + "</button>");
    pager.innerHTML = btns.join("");
    pager.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () { state.page = Number(btn.getAttribute("data-page")); renderTable(); });
    });
  }

  var CHECKLIST_LABELS = { email: "Email", phone: "Nomor HP", pic: "Identitas PIC", location: "Lokasi Posko", trusted_verifier: "Trusted Verifier" };

  function renderChecklist(data) {
    $("#checklistStatusChip").textContent = statusLabel(data.verification_status);
    $("#checklistStatusChip").className = "chip " + statusPillClass(data.verification_status);
    $("#checklistList").innerHTML = data.items.map(function (it) {
      return '<li class="' + (it.done ? "is-done" : "") + '"><span>' + (it.done ? "✓" : "○") + "</span>" + esc(CHECKLIST_LABELS[it.key] || it.key) +
        (it.value ? "<small>" + esc(it.value) + "</small>" : "") + "</li>";
    }).join("");
    $("#checklistNote").textContent = data.ready_to_submit
      ? "Siap diajukan untuk verifikasi."
      : "Lengkapi Email, No HP, Identitas PIC, dan Lokasi sebelum mengajukan verifikasi.";

    $("#submitVerifBtn").disabled = !(data.ready_to_submit && (data.verification_status === "self_reported" || data.verification_status === "needs_correction"));
    $("#saveDraftBtn").disabled = false;
    $("#deletePoskoBtn").disabled = false;
  }

  async function selectPosko(name) {
    state.selected = name;
    renderTable();
    $("#checklistList").innerHTML = '<li class="rn-muted">Memuat…</li>';
    try {
      var data = await window.RN_FRAPPE.call("rescue_net.api_control_centre.posko_verification_checklist", { posko: name });
      renderChecklist(data);
    } catch (err) {
      $("#checklistList").innerHTML = '<li class="rn-muted">Gagal memuat: ' + esc(err && err.message || err) + "</li>";
    }
  }

  function setupActions() {
    $("#submitVerifBtn").addEventListener("click", async function () {
      if (!state.selected) return;
      var msg = $("#actionMsg2");
      msg.textContent = "Mengajukan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_community_cluster.submit_posko_verification", { posko: state.selected }, { method: "POST" });
        msg.textContent = "Berhasil diajukan.";
        await loadRegistry();
        await selectPosko(state.selected);
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses|diperlukan/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });

    $("#deletePoskoBtn").addEventListener("click", async function () {
      if (!state.selected) return;
      if (!window.confirm("Hapus posko " + state.selected + "? Tindakan ini permanen.")) return;
      var msg = $("#actionMsg2");
      msg.textContent = "Menghapus…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_community_cluster.delete_posko", { posko: state.selected }, { method: "POST" });
        msg.textContent = "Posko dihapus.";
        state.selected = null;
        $("#checklistList").innerHTML = '<li class="rn-muted">Pilih atau simpan posko untuk melihat status.</li>';
        await loadRegistry();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err);
      }
    });

    $("#saveDraftBtn").addEventListener("click", function () {
      $("#actionMsg2").textContent = "Draft sudah otomatis tersimpan sejak posko dibuat (status self_reported).";
    });
  }

  function setupForm() {
    var form = $("#regForm");
    $("#regResetBtn").addEventListener("click", function () { form.reset(); });

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#regFormMsg");
      var fd = new FormData(form);
      var latlng = String(fd.get("latlng") || "").split(",").map(function (s) { return s.trim(); });

      msg.textContent = "Menyimpan…";
      try {
        var res = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.create_posko", {
          title: fd.get("title"),
          posko_type: fd.get("posko_type"),
          address: fd.get("address"),
          disaster_event: fd.get("disaster_event"),
          latitude: latlng[0] || null,
          longitude: latlng[1] || null,
          officer_in_charge_name: fd.get("officer_in_charge_name"),
          officer_in_charge_role: fd.get("officer_in_charge_role"),
          officer_in_charge_phone: fd.get("officer_in_charge_phone"),
          officer_in_charge_email: fd.get("officer_in_charge_email"),
          emergency_contact: fd.get("emergency_contact"),
          facilities: fd.get("facilities"),
          rn_beneficiary_count: fd.get("rn_beneficiary_count"),
          public_detail: fd.get("public_detail"),
        }, { method: "POST" });
        msg.textContent = "Posko tersimpan: " + res.posko;
        form.reset();
        await loadRegistry();
        await selectPosko(res.posko);
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses|diperlukan/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
  }

  async function loadRegistry() {
    var data = await window.RN_FRAPPE.call("rescue_net.api_control_centre.posko_registry_board", { disaster_event: getEventId() });
    state.rows = data.poskos || [];
    $("#regUpdated").textContent = "Posko · Diperbarui " + fmtTime(data.generated_at).slice(11, 16);
    renderKpi(data.totals || {});
    applyFilter();
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    setupForm();
    setupActions();
    $("#poskoSearch").addEventListener("input", function (e) { state.query = e.target.value.trim(); applyFilter(); });

    loadRegistry()
      .then(function () {
        var el = document.getElementById("regStatus");
        if (el) el.textContent = "Dimuat " + state.rows.length + " posko.";
      })
      .catch(function (err) {
        var el = document.getElementById("regStatus");
        if (el) el.textContent = "Gagal memuat: " + (err && err.message || err);
      });
  });
})();
