/* ============================================================
 * Jaringan Verifikator — external verifier network for independent poskos.
 * Backend: rescue_net.api_verifier.*
 * ============================================================ */
(function () {
  "use strict";
  var A = "rescue_net.api_verifier.";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function call(m, args, opts) { return window.RN_FRAPPE.call(A + m, args || {}, opts || {}); }
  function fmtDate(s) { return s ? String(s).slice(0, 16).replace("T", " ") : "-"; }

  var TYPE_LABEL = {
    government: "Pemerintah", community_leader: "Tokoh Masyarakat",
    religious_leader: "Tokoh Agama", professional: "Profesional",
    public_figure: "Tokoh Publik", other: "Lainnya",
  };
  var METHOD_LABEL = { site_visit: "Kunjungan langsung", network_vouch: "Rekomendasi jaringan", document_review: "Telaah dokumen" };

  var DIRECTORY = [];

  function verifierCard(v, opts) {
    opts = opts || {};
    var chips = '<span class="vf-chip ' + (v.verifier_type === "government" ? "gov" : "") + '">' + esc(TYPE_LABEL[v.verifier_type] || v.verifier_type) + "</span> " +
      '<span class="vf-chip ' + (v.verifier_status === "active" ? "active" : "pending") + '">' + esc(v.verifier_status) + "</span>";
    var actions = "";
    if (opts.approvable) {
      actions = '<div class="vf-actions" data-vid="' + esc(v.name) + '">' +
        '<button type="button" class="btn primary mini" data-va="approve">Setujui</button>' +
        '<button type="button" class="btn ghost mini" data-va="reject">Tolak</button>' +
        '<span class="rn-muted vf-msg"></span></div>';
    }
    return '<article class="vf-card">' +
      "<h4>" + esc(v.title) + "</h4>" +
      '<div class="rn-row" style="margin:2px 0 6px">' + chips + "</div>" +
      '<div class="vf-meta">' + esc(v.position_title || "-") + " · " + esc(v.wilayah || "-") + "</div>" +
      (v.public_role_description ? '<div class="vf-meta" style="margin-top:4px">' + esc(v.public_role_description) + "</div>" : "") +
      '<div class="vf-meta" style="margin-top:4px">Trust ' + (v.trust_level || 0) + " · " + (v.endorsement_count || 0) + " endorsement</div>" +
      actions +
      "</article>";
  }

  function renderDirectory(filter) {
    var f = (filter || "").trim().toLowerCase();
    var list = f ? DIRECTORY.filter(function (v) { return (v.wilayah || "").toLowerCase().indexOf(f) !== -1 || (v.title || "").toLowerCase().indexOf(f) !== -1; }) : DIRECTORY;
    $("#vfDirectory").innerHTML = list.length ? list.map(function (v) { return verifierCard(v); }).join("")
      : '<p class="vf-empty">Belum ada verifikator' + (f ? " untuk \"" + esc(filter) + "\"" : "") + ".</p>";
  }

  function reqCard(r, opts) {
    opts = opts || {};
    var head = esc(r.posko_title || r.object_id) + ' <span class="rn-muted">(' + esc(METHOD_LABEL[r.method] || r.method) + ")</span>";
    var actions = "";
    if (opts.endorsable) {
      actions = '<div class="vf-actions" data-rid="' + esc(r.name) + '" data-posko="' + esc(r.object_id) + '" data-method="' + esc(r.method) + '">' +
        (r.method === "network_vouch"
          ? '<input class="vf-vouch" placeholder="direkomendasikan via (nama)" style="max-width:180px">'
          : "") +
        '<input class="vf-stmt" placeholder="pernyataan singkat" style="max-width:220px">' +
        '<button type="button" class="btn primary mini" data-endorse>Endorse posko</button>' +
        '<span class="rn-muted vf-msg"></span></div>';
    }
    return '<article class="vf-card"><h4>' + head + "</h4>" +
      '<div class="vf-meta">Wilayah: ' + esc(r.wilayah || "-") + " · status: " + esc(r.status) + " · " + fmtDate(r.creation) + "</div>" +
      (r.notes ? '<div class="vf-meta" style="margin-top:4px">' + esc(r.notes) + "</div>" : "") +
      actions + "</article>";
  }

  async function loadInbox() {
    var d;
    try { d = await call("verifier_inbox"); } catch (e) { return null; }
    if (!d || !d.is_verifier) return d;
    if (d.verifier && d.verifier.verifier_status !== "active") {
      $("#vfInboxSection").hidden = false;
      $("#vfInbox").innerHTML = '<p class="vf-empty">Profil verifikator Anda berstatus <b>' + esc(d.verifier.verifier_status) + "</b>. Menunggu persetujuan.</p>";
      return d;
    }
    var direct = d.direct_requests || [], open = d.wilayah_open_requests || [];
    $("#vfInboxCount").textContent = direct.length + " langsung · " + open.length + " terbuka";
    $("#vfInbox").innerHTML =
      (direct.length ? "<h4 class=\"rn-md-detail-h\">Ditujukan ke Anda</h4>" + direct.map(function (r) { return reqCard(r, { endorsable: true }); }).join("") : "") +
      (open.length ? "<h4 class=\"rn-md-detail-h\">Terbuka di wilayah Anda</h4>" + open.map(function (r) { return reqCard(r, { endorsable: true }); }).join("") : "") ||
      '<p class="vf-empty">Tidak ada permintaan verifikasi saat ini.</p>';
    $("#vfInboxSection").hidden = false;
    wireEndorse();
    return d;
  }

  function wireEndorse() {
    document.querySelectorAll("[data-endorse]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var box = btn.closest("[data-rid]");
        var msg = box.querySelector(".vf-msg");
        var vouch = box.querySelector(".vf-vouch");
        var stmt = box.querySelector(".vf-stmt");
        msg.textContent = " memproses…";
        try {
          var r = await call("endorse_posko", {
            request: box.getAttribute("data-rid"),
            posko: box.getAttribute("data-posko"),
            method: box.getAttribute("data-method"),
            statement: stmt ? stmt.value.trim() : "",
            vouched_via: vouch ? vouch.value.trim() : "",
          }, { method: "POST" });
          msg.textContent = " ✓ " + r.verification_status + " (" + r.trusted_verifier_count + " verifikator)";
          setTimeout(load, 800);
        } catch (err) {
          msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    });
  }

  async function loadMyPoskoRequests() {
    var d;
    try { d = await call("my_verification_requests"); } catch (e) { return; }
    var reqs = (d && d.requests) || [];
    var sel = $("#vfRequestForm [name=posko]");
    var poskoIds = [];
    reqs.forEach(function (r) { if (poskoIds.indexOf(r.object_id) === -1) poskoIds.push(r.object_id); });
    // also let the operator pick a posko even with no prior request: use request rows' poskos
    var seen = {};
    sel.innerHTML = "";
    reqs.forEach(function (r) {
      if (seen[r.object_id]) return; seen[r.object_id] = 1;
      var o = document.createElement("option");
      o.value = r.object_id; o.textContent = r.posko_title || r.object_id;
      sel.appendChild(o);
    });
    if (!sel.children.length) {
      sel.innerHTML = '<option value="">(tidak ada posko yang Anda kelola / minta verifikasi lewat halaman posko)</option>';
    }
    $("#vfMyRequests").innerHTML = reqs.length
      ? reqs.map(function (r) { return reqCard(r); }).join("")
      : '<p class="vf-empty">Belum ada permintaan verifikasi.</p>';
    $("#vfMyPoskoSection").hidden = reqs.length === 0 && sel.children.length === 0;
  }

  function wireRequestForm() {
    var form = $("#vfRequestForm");
    var msg = form.querySelector("[data-req-msg]");
    // populate verifier dropdown from directory
    var vsel = form.querySelector("[name=verifier]");
    DIRECTORY.forEach(function (v) {
      var o = document.createElement("option");
      o.value = v.name; o.textContent = v.title + " — " + (v.wilayah || "");
      vsel.appendChild(o);
    });
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var posko = form.posko.value;
      if (!posko) { msg.textContent = "Pilih posko dulu."; return; }
      msg.textContent = "mengirim…";
      try {
        var r = await call("request_posko_verification", {
          posko: posko, verifier: form.verifier.value || null,
          method: form.method.value, note: form.note.value.trim() || null,
        }, { method: "POST" });
        msg.textContent = "terkirim (" + r.status + ", wilayah: " + (r.wilayah || "-") + ")";
        loadMyPoskoRequests();
      } catch (err) { msg.textContent = "gagal: " + ((err && err.message) || err); }
    });
  }

  async function loadPending(canApprove) {
    if (!canApprove) { $("#vfApproveSection").hidden = true; return; }
    var d;
    try { d = await call("verifier_directory", { status: "pending" }); } catch (e) { return; }
    var list = (d && d.verifiers) || [];
    $("#vfPendingCount").textContent = list.length + " menunggu";
    $("#vfPending").innerHTML = list.length
      ? '<div class="vf-grid">' + list.map(function (v) { return verifierCard(v, { approvable: true }); }).join("") + "</div>"
      : '<p class="vf-empty">Tidak ada permohonan menunggu.</p>';
    $("#vfApproveSection").hidden = false;
    document.querySelectorAll("#vfPending [data-va]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var box = btn.closest("[data-vid]");
        var msg = box.querySelector(".vf-msg");
        msg.textContent = " memproses…";
        try {
          await call("approve_verifier", { verifier: box.getAttribute("data-vid"), action: btn.getAttribute("data-va") }, { method: "POST" });
          setTimeout(load, 600);
        } catch (err) { msg.textContent = " gagal: " + ((err && err.message) || err); }
      });
    });
  }

  function wireApplyForm() {
    var form = $("#vfApplyForm");
    var msg = form.querySelector("[data-apply-msg]");
    var ssel = form.querySelector("[name=sponsor_verifier]");
    DIRECTORY.forEach(function (v) {
      if (v.verifier_status !== "active") return;
      var o = document.createElement("option");
      o.value = v.name; o.textContent = v.title;
      ssel.appendChild(o);
    });
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      msg.textContent = "mengirim…";
      try {
        var r = await call("apply_as_verifier", {
          display_name: form.display_name.value.trim(),
          verifier_type: form.verifier_type.value,
          position_title: form.position_title.value.trim() || null,
          wilayah: form.wilayah.value.trim(),
          phone: form.phone.value.trim() || null,
          email: form.email.value.trim() || null,
          public_role_description: form.public_role_description.value.trim() || null,
          sponsor_verifier: form.sponsor_verifier.value || null,
        }, { method: "POST" });
        msg.textContent = "terkirim — status " + r.verifier_status + (r.has_sponsor ? " (dengan sponsor)" : "");
        form.reset();
        setTimeout(load, 800);
      } catch (err) { msg.textContent = "gagal: " + ((err && err.message) || err); }
    });
  }

  var WIRED = false;

  async function load() {
    var dir;
    try { dir = await call("verifier_directory", {}); } catch (e) { dir = { verifiers: [] }; }
    DIRECTORY = (dir && dir.verifiers) || [];
    renderDirectory($("#vfSearch").value);

    var inbox = await loadInbox();
    await loadMyPoskoRequests();

    // approval rights: System Manager OR active verifier trust>=2
    var canApprove = false;
    if (inbox && inbox.is_verifier && inbox.verifier && inbox.verifier.verifier_status === "active" && (inbox.verifier.trust_level || 0) >= 2) canApprove = true;
    try {
      var sess = window.RN_SESSION_ROLE || {};
      if (sess.is_system_manager || sess.role === "system_manager") canApprove = true;
    } catch (e) {}
    await loadPending(canApprove);

    var role = inbox && inbox.is_verifier
      ? (inbox.verifier ? "Verifikator · " + (inbox.verifier.verifier_status) : "Verifikator")
      : "Publik";
    $("#vfRole").textContent = role;
    $("#vfStatus").textContent = DIRECTORY.length + " verifikator aktif di direktori.";

    if (!WIRED) {
      WIRED = true;
      wireRequestForm();
      wireApplyForm();
      $("#vfSearch").addEventListener("input", function () { renderDirectory(this.value); });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();
