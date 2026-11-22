/* ============================================================
 * verifikasi-hub.js — one page for Pengajuan Verifikasi / Verifikator / Data Hasil Verifikasi.
 * - group + submenu tabs (hash routing: #pengajuan/antrian, #verifikator/direktori, #hasil/endorsement)
 * - a search + status filter bar above every list (client-side, re-applied when the list re-renders)
 * - "Endorsement" results table: rescue_net.api_verifier.endorsements_overview (server-side search)
 * The pages' original scripts (verification-approval.js, verifikator.js) keep rendering into the same ids.
 * ============================================================ */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function esc(s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  var DEFAULT = { pengajuan: "antrian", verifikator: "direktori", hasil: "endorsement" };
  var LAST = {};

  /* ---------- tabs ---------- */
  function show(group, sub, push) {
    if (!DEFAULT[group]) group = "pengajuan";
    var valid = $$('.vx-sub-btn[data-group="' + group + '"]').map(function (b) { return b.getAttribute("data-sub"); });
    if (valid.indexOf(sub) === -1) sub = LAST[group] || DEFAULT[group];
    LAST[group] = sub;
    $$(".vx-group-btn").forEach(function (b) { var on = b.getAttribute("data-group") === group; b.classList.toggle("is-active", on); b.setAttribute("aria-selected", on); });
    $$(".vx-subnav").forEach(function (n) { n.hidden = n.getAttribute("data-group") !== group; });
    $$(".vx-sub-btn").forEach(function (b) { b.classList.toggle("is-active", b.getAttribute("data-group") === group && b.getAttribute("data-sub") === sub); });
    $$(".vx-pane").forEach(function (p) { p.hidden = !(p.getAttribute("data-group") === group && p.getAttribute("data-sub") === sub); });
    if (push !== false) { try { history.replaceState(null, "", location.pathname + location.search + "#" + group + "/" + sub); } catch (e) {} }
    emptyState();
    if (group === "hasil" && sub === "endorsement") loadEndorsements();
  }

  function fromHash() {
    var h = (location.hash || "").replace(/^#/, "").split("/");
    var group = h[0] || "pengajuan";
    if (new URLSearchParams(location.search).get("cari") && !h[0]) { group = "verifikator"; h = ["verifikator", "direktori"]; }
    show(group, h[1] || LAST[group] || DEFAULT[group], false);
  }

  /* a pane whose sections the page's own scripts hid (e.g. verifier inbox for a non-verifier) says so */
  function emptyState() {
    $$(".vx-pane:not([hidden])").forEach(function (pane) {
      var note = $(".vx-empty", pane);
      var anyVisible = $$(".panel, .kpi-grid, form, .content-grid, .vx-table-wrap, details", pane).some(function (el) {
        return !el.closest("[hidden]") && el.offsetParent !== null;
      });
      if (!anyVisible && !note) {
        note = document.createElement("p");
        note.className = "vx-empty rn-muted";
        note.textContent = "Bagian ini tidak tersedia untuk peran Anda saat ini (masuk sebagai verifikator atau pengelola untuk melihatnya).";
        pane.appendChild(note);
      } else if (anyVisible && note) { note.remove(); }
    });
  }

  /* ---------- filters ---------- */
  function applyFilter(bar) {
    var targets = (bar.getAttribute("data-vx-for") || "").split(",").map(function (s) { return $(s.trim()); }).filter(Boolean);
    var q = (($("[data-vx-q]", bar) || {}).value || "").trim().toLowerCase();
    var st = (($("[data-vx-s]", bar) || {}).value || "").toLowerCase();
    var shown = 0, total = 0;
    targets.forEach(function (t) {
      Array.prototype.forEach.call(t.children, function (el) {
        if (el.classList.contains("rn-muted") && !el.children.length) return;   // plain "kosong" message
        total++;
        var text = el.textContent.toLowerCase();
        var ok = (!q || text.indexOf(q) !== -1) && (!st || text.indexOf(st) !== -1);
        el.hidden = !ok;
        if (ok) shown++;
      });
    });
    var c = $("[data-vx-count]", bar);
    if (c) c.textContent = total ? (q || st ? shown + " dari " + total : total + " item") : "";
  }

  function wireFilters() {
    $$(".vx-filter[data-vx-for]").forEach(function (bar) {
      var run = function () { applyFilter(bar); };
      $$("input,select", bar).forEach(function (el) { el.addEventListener(el.tagName === "INPUT" ? "input" : "change", run); });
      (bar.getAttribute("data-vx-for") || "").split(",").forEach(function (sel) {
        var t = $(sel.trim());
        if (t && window.MutationObserver) new MutationObserver(function () { setTimeout(run, 0); badges(); }).observe(t, { childList: true });
      });
      run();
    });
  }

  /* ---------- counts on submenu buttons ---------- */
  function badges() {
    $$(".vx-sub-btn[data-count-for]").forEach(function (b) {
      var t = $(b.getAttribute("data-count-for"));
      var n = 0;
      if (t) {
        if (t.children && t.children.length && t.id !== "queueCount") n = Array.prototype.filter.call(t.children, function (el) { return el.tagName !== "P" && !el.classList.contains("rn-muted"); }).length;
        if (t.id === "queueCount") n = parseInt(t.textContent, 10) || 0;
        if (t.tagName === "TBODY") n = $$("tr[data-name], tr.vx-row", t).length;
      }
      var bd = $(".vx-badge", b);
      if (bd) { bd.textContent = n; bd.hidden = !n; }
    });
  }

  /* ---------- Objek Terverifikasi: one table, filter by type / status / text ---------- */
  function applyObjects() {
    var body = $("#vxObjectsBody"); if (!body) return;
    var q = (($("#vxObjectsQ") || {}).value || "").trim().toLowerCase();
    var type = ($("#vxObjectsType") || {}).value || "";
    var st = ($("#vxObjectsStatus") || {}).value || "";
    var rows = $$("tr.vx-row", body), shown = 0;
    rows.forEach(function (tr) {
      var ok = (!type || tr.dataset.type === type) && (!st || tr.dataset.vgroup === st) && (!q || tr.textContent.toLowerCase().indexOf(q) !== -1);
      tr.hidden = !ok; if (ok) shown++;
    });
    var c = $("#vxObjectsCount");
    if (c && rows.length) c.textContent = (q || type || st) ? shown + " dari " + rows.length + " objek" : rows.length + " objek";
  }
  function wireObjects() {
    ["#vxObjectsQ", "#vxObjectsType", "#vxObjectsStatus"].forEach(function (sel) {
      var el = $(sel); if (el) el.addEventListener(el.tagName === "INPUT" ? "input" : "change", applyObjects);
    });
    window.addEventListener("vx:objects", function () { applyObjects(); badges(); });
  }

  /* ---------- Endorsement results (Data Hasil Verifikasi) ---------- */
  var timer = null;
  function loadEndorsements() {
    var body = $("#vxEndorseBody");
    if (!body || !window.RN_FRAPPE) return;
    var args = { q: ($("#vxEndorseQ") || {}).value || "", target_type: ($("#vxEndorseType") || {}).value || null, status: ($("#vxEndorseStatus") || {}).value || "active", limit: 300 };
    window.RN_FRAPPE.call("rescue_net.api_verifier.endorsements_overview", args).then(function (d) {
      var rows = (d && d.rows) || [];
      $("#vxEndorseCount").textContent = rows.length + " endorsement";
      body.innerHTML = rows.length ? rows.map(function (r) {
        var who = '<b>' + esc(r.verifier || "-") + "</b>" + (r.position ? "<br><small>" + esc(r.position) + (r.wilayah ? " · " + esc(r.wilayah) : "") + "</small>" : "");
        var link = r.verifier ? '<a href="verification-approval.html?cari=' + encodeURIComponent(r.verifier) + '#verifikator/direktori">' + who + "</a>" : who;
        return '<tr class="vx-row"><td>' + esc(r.target) + "<br><small>" + (r.target_type === "posko" ? "Posko" : "Pelapor") + "</small>" +
          (r.statement ? "<br><small>“" + esc(r.statement) + "”</small>" : "") + "</td><td>" + link + "</td><td>" + esc(r.verifier_type || "-") + "</td><td>" + esc(r.method || "-") +
          "</td><td>" + esc(r.verified_at || "-") + '</td><td><span class="chip ' + (r.status === "active" ? "ok" : "danger") + '">' + (r.status === "active" ? "Aktif" : "Dicabut") + "</span></td>" +
          "<td>" + (r.can_revoke && r.status === "active" ? '<button type="button" class="btn mini" data-vx-revoke="' + esc(r.endorsement) + '">Cabut</button>' : "") + "</td></tr>";
      }).join("") : '<tr><td colspan="7"><em class="rn-muted">Tidak ada endorsement yang cocok.</em></td></tr>';
      badges();
    }).catch(function (e) {
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Gagal memuat: ' + esc(e && e.message || e) + "</em></td></tr>";
    });
  }
  function wireEndorse() {
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-vx-revoke]"); if (!b) return;
      var reason = prompt("Alasan mencabut endorsement (wajib):");
      if (!reason || !reason.trim()) return;
      b.disabled = true;
      window.RN_FRAPPE.call("rescue_net.api_verifier.revoke_endorsement", { endorsement: b.getAttribute("data-vx-revoke"), reason: reason.trim() }, { method: "POST" })
        .then(loadEndorsements).catch(function (err) { alert(err && err.message || err); b.disabled = false; });
    });
    var f = function () { clearTimeout(timer); timer = setTimeout(loadEndorsements, 250); };
    ["#vxEndorseQ", "#vxEndorseType", "#vxEndorseStatus"].forEach(function (s) {
      var el = $(s); if (el) el.addEventListener(el.tagName === "INPUT" ? "input" : "change", f);
    });
  }

  function init() {
    $$(".vx-group-btn").forEach(function (b) { b.addEventListener("click", function () { var g = b.getAttribute("data-group"); show(g, LAST[g] || DEFAULT[g]); }); });
    $$(".vx-sub-btn").forEach(function (b) { b.addEventListener("click", function () { show(b.getAttribute("data-group"), b.getAttribute("data-sub")); }); });
    window.addEventListener("hashchange", fromHash);
    wireFilters();
    wireEndorse();
    wireObjects();
    fromHash();
    badges();
    // the page's own scripts fill lists / unhide sections asynchronously
    [800, 2000, 4000].forEach(function (ms) { setTimeout(function () { emptyState(); badges(); $$(".vx-filter[data-vx-for]").forEach(applyFilter); }, ms); });
    // deep link from a report/posko panel: ?cari=<verifier> -> directory (verifikator.js reads the same param)
    var cari = new URLSearchParams(location.search).get("cari");
    if (cari) { var inp = $("#vfSearch"); if (inp && !inp.value) inp.value = cari; }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
