/* Evidence Center dashboard — pages/evidence.html
 * New dashboard: rescue_net.api_control_centre.evidence_board (guest,
 * event-wide, wraps the unified event_evidence() feed already shared with
 * Control Centre / every posko page's "Bukti" panel).
 * Legacy "Upload Evidence" form keeps calling
 * rescue_net.api_frontend_bridge.upload_evidence (login required).
 */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_control_centre.evidence_board";
  var PAGE_SIZE = 10;
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

  var state = { rows: [], filtered: [], module: "Semua", query: "", page: 0, verif: "", vis: "", mime: "", geo: false, sel: {} };
  var BOARD_CACHE = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function getEventId() { return window.RNUI.eventId(); }

  function statusMsg(msg) {
    var el = $("#evidenceStatus");
    if (el) el.textContent = msg;
  }

  function statusPillClass(status) {
    var l = String(status || "").toLowerCase();
    if (l === "verified" || l === "official_verified" || l === "community_verified") return "ok";
    if (l === "pending") return "warning";
    if (l === "rejected" || l === "flagged") return "danger";
    return "";
  }

  function filename(url) {
    if (!url) return "-";
    var clean = url.split("?")[0];
    var parts = clean.split("/");
    return parts[parts.length - 1] || "-";
  }

  function mimeIcon(mime) {
    if (mime === "video") return "🎬";
    if (mime === "document") return "📄";
    return "🖼️";
  }

  /* ---------- KPI drill ---------- */

  var DRILL_TITLES = {
    evidence_baru: "Evidence Baru (Hari Ini)", pending: "Pending Verifikasi",
    restricted: "Restricted", geotagged: "Geotagged", serah_terima: "Dokumen Serah Terima",
    video: "Video Evidence",
  };
  var DRILL_FIELD = {
    evidence_baru: "evidence_baru_items", pending: "pending_items", restricted: "restricted_items",
    geotagged: "geotagged_items", serah_terima: "serah_terima_items", video: "video_items",
  };

  function drillItemsHtml(items) {
    if (!items || !items.length) return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    return items.map(function (it) {
      return (
        '<a class="rn-ba-ditem" href="' + esc(it.href || "#") + '" target="_blank" rel="noopener">' +
        "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
        '<span class="rn-ba-ditem-go">→</span></a>'
      );
    }).join("");
  }

  function openDrill(kind) {
    if (!BOARD_CACHE) return;
    var items = ((BOARD_CACHE.kpi_items || {})[DRILL_FIELD[kind]]) || [];
    $("#evidenceDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    $("#evidenceDrillSub").textContent = items.length + " item";
    $("#evidenceDrillBody").innerHTML = drillItemsHtml(items);
    $("#evidenceDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#evidenceDrill").hidden = true; document.body.style.overflow = ""; }

  /* ---------- render ---------- */

  function renderKpi(t) {
    $("#kpiBaru").textContent = fmt(t.evidence_baru);
    $("#kpiPending").textContent = fmt(t.pending_verifikasi);
    $("#kpiRestricted").textContent = fmt(t.restricted);
    $("#kpiGeotagged").textContent = fmt(t.geotagged);
    $("#kpiSerahTerima").textContent = fmt(t.dokumen_serah_terima);
    $("#kpiVideo").textContent = fmt(t.video_evidence);
  }

  function renderModulChips(filterModul) {
    var el = $("#modulChips");
    el.innerHTML = filterModul.map(function (m) {
      var active = m.label === state.module ? " is-active" : "";
      return '<button type="button" class="rn-ev-chip' + active + '" data-modul="' + esc(m.label) + '">' +
        esc(m.label) + ' <span>' + fmt(m.count) + '</span></button>';
    }).join("");
    el.querySelectorAll(".rn-ev-chip").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.module = btn.getAttribute("data-modul");
        state.page = 0;
        applyFilter();
        renderModulChips(filterModul);
      });
    });
  }

  function hasGeo(r) { return !!(r.latitude && r.longitude && (Math.abs(r.latitude) > 0.0001 || Math.abs(r.longitude) > 0.0001)); }
  function matchVerif(r, v) {
    var l = String(r.status || "").toLowerCase();
    if (v === "verified") return statusPillClass(l) === "ok";
    if (v === "restricted") return r.visibility === "restricted" && l === "restricted";
    return l === v;
  }
  function fmtWhen(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(s || ""));
    if (!m) return ["-", ""];
    return [Number(m[3]) + " " + MONTHS[Number(m[2]) - 1] + " " + m[1], m[4] + ":" + m[5] + " WIB"];
  }
  var VERIF_LABEL = { verified: "Terverifikasi", official_verified: "Terverifikasi", community_verified: "Terverifikasi", pending: "Pending", rejected: "Ditolak", flagged: "Ditandai", restricted: "Restricted" };
  var VERIF_ICON = { ok: "check-circle", warning: "clock", danger: "alert-circle" };

  function applyFilter() {
    var q = state.query.toLowerCase();
    state.filtered = state.rows.filter(function (r) {
      if (state.module !== "Semua" && r.module !== state.module) return false;
      if (state.verif && !matchVerif(r, state.verif)) return false;
      if (state.vis && r.visibility !== state.vis) return false;
      if (state.mime && r.mime !== state.mime) return false;
      if (state.geo && !hasGeo(r)) return false;
      if (!q) return true;
      var hay = [r.title, r.location_text, r.posko, r.uploader].join(" ").toLowerCase();
      return hay.indexOf(q) !== -1;
    });
    renderTable();
  }

  function renderTable() {
    var total = state.filtered.length;
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    var slice = state.filtered.slice(state.page * PAGE_SIZE, state.page * PAGE_SIZE + PAGE_SIZE);

    var body = $("#evidenceBody");
    if (!slice.length) {
      body.innerHTML = '<tr><td colspan="9"><em class="rn-muted">Tidak ada evidence yang cocok.</em></td></tr>';
    } else {
      body.innerHTML = slice.map(function (r, i) {
        var url = r.evidence_url || "";
        var thumb = r.mime === "image"
          ? '<img src="' + esc(url) + '" alt="" loading="lazy">'
          : '<span class="rn-ev-thumb-icon">' + mimeIcon(r.mime) + "</span>";
        var geo = hasGeo(r)
          ? '<small class="rn-ev-geo"><span data-icon="map-pin"></span>' + r.latitude.toFixed(4) + ", " + r.longitude.toFixed(4) + "</small>"
          : "";
        var cap = String(r.evidence_caption || r.caption || r.title || "Evidence").replace(/^\s*\[[^\]]+\]\s*/, "");
        var meta = [r.location_text || r.posko, r.uploader].filter(Boolean).join(" · ");
        var lbAttr = r.mime === "image"
          ? ' data-caption="' + esc(cap) + '" data-meta="' + esc(meta) + '"'
          : ' data-no-lightbox';
        var when = fmtWhen(r.created_at);
        var vc = statusPillClass(r.status);
        var vlabel = VERIF_LABEL[String(r.status || "").toLowerCase()] || r.status || "-";
        var vtone = String(r.status).toLowerCase() === "restricted" ? "danger" : vc;
        var id = String(r.name || r.id || url || (state.page * PAGE_SIZE + i));
        var typeIcon = r.mime === "video" ? "camera" : r.mime === "document" ? "clipboard-check" : "camera";
        return (
          '<tr data-id="' + esc(id) + '">' +
          '<td class="rn-ev-c0"><input type="checkbox" class="rn-ev-sel" data-id="' + esc(id) + '"' + (state.sel[id] ? " checked" : "") + ' aria-label="Pilih"></td>' +
          '<td data-label="Evidence"><a class="rn-ev-cell" href="' + esc(url) + '" target="_blank" rel="noopener"' + lbAttr + ">" +
          '<span class="rn-ev-thumb">' + thumb + '<i class="rn-ev-type ' + esc(r.mime || "image") + '" data-icon="' + typeIcon + '"></i></span>' +
          "<span><b>" + esc(r.title || "Evidence") + "</b><small>" + esc(filename(url)) + "</small>" + geo + "</span>" +
          "</a></td>" +
          '<td data-label="Modul"><span class="chip rn-ev-mod" data-mod="' + esc(r.module) + '">' + esc(r.module) + "</span></td>" +
          '<td data-label="Lokasi" class="rn-ev-loc">' + esc(r.location_text || r.posko || "-") + "</td>" +
          '<td data-label="Waktu" class="rn-ev-when">' + esc(when[0]) + "<small>" + esc(when[1]) + "</small></td>" +
          '<td data-label="Uploader"><b>' + esc(r.uploader || "-") + "</b><small>" + esc(r.uploader_role || "-") + "</small></td>" +
          '<td data-label="Verifikasi"><span class="chip ' + vtone + '">' + (VERIF_ICON[vtone] ? '<span data-icon="' + VERIF_ICON[vtone] + '"></span>' : "") + esc(vlabel) + "</span></td>" +
          '<td data-label="Visibilitas"><span class="chip ' + (r.visibility === "public" ? "" : "danger") + '">' + (r.visibility === "public" ? "Publik" : "Terbatas") + "</span></td>" +
          '<td class="rn-ev-act"><details class="rn-ev-menu"><summary aria-label="Aksi">⋯</summary><div>' +
          (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">Buka file</a><a href="' + esc(url) + '" download>Unduh</a><button type="button" data-copy="' + esc(url) + '">Salin tautan</button>' : "<span>Tidak ada file</span>") +
          "</div></details></td>" +
          "</tr>"
        );
      }).join("");
      if (window.RNIconFill) window.RNIconFill(body);
    }

    $("#evidenceShown").textContent = total
      ? "Menampilkan " + (state.page * PAGE_SIZE + 1) + "-" + Math.min(total, (state.page + 1) * PAGE_SIZE) + " dari " + total + " evidence"
      : "0 evidence";

    var pager = $("#evidencePager");
    var btns = [], shown = [];
    for (var i = 0; i < pages; i++) {
      if (i === 0 || i === pages - 1 || Math.abs(i - state.page) <= 1) shown.push(i);
      else if (shown[shown.length - 1] !== "…") shown.push("…");
    }
    shown.forEach(function (i) {
      btns.push(i === "…" ? '<span class="rn-ev-gap">…</span>'
        : '<button type="button" class="rn-ev-page' + (i === state.page ? " is-active" : "") + '" data-page="' + i + '">' + (i + 1) + "</button>");
    });
    pager.innerHTML = btns.join("");
    pager.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.page = Number(btn.getAttribute("data-page"));
        renderTable();
      });
    });
    var all = $("#selAll");
    if (all) all.checked = slice.length > 0 && slice.every(function (r) { return state.sel[String(r.name || r.id || r.evidence_url)]; });
  }

  function setupFilters() {
    function bind(id, key, isCheck) {
      $(id).addEventListener("change", function (e) {
        state[key] = isCheck ? e.target.checked : e.target.value;
        state.page = 0;
        applyFilter();
      });
    }
    bind("#fVerif", "verif"); bind("#fVis", "vis"); bind("#fMime", "mime"); bind("#fGeo", "geo", true);
    $("#fReset").addEventListener("click", function () {
      ["#fVerif", "#fVis", "#fMime"].forEach(function (id) { $(id).value = ""; });
      $("#fGeo").checked = false;
      state.verif = state.vis = state.mime = ""; state.geo = false; state.page = 0;
      applyFilter();
    });
    $("#perPage").addEventListener("change", function (e) { PAGE_SIZE = Number(e.target.value) || 10; state.page = 0; renderTable(); });
    $("#selAll").addEventListener("change", function (e) {
      var from = state.page * PAGE_SIZE;
      state.filtered.slice(from, from + PAGE_SIZE).forEach(function (r) { state.sel[String(r.name || r.id || r.evidence_url)] = e.target.checked; });
      renderTable();
    });
    $("#evidenceBody").addEventListener("change", function (e) {
      if (e.target.classList.contains("rn-ev-sel")) { state.sel[e.target.dataset.id] = e.target.checked; renderTable(); }
    });
    $("#evidenceBody").addEventListener("click", function (e) {
      var c = e.target.closest("[data-copy]");
      if (!c) return;
      var url = new URL(c.dataset.copy, location.href).href;
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { c.textContent = "Tersalin"; }, function () { window.prompt("Salin tautan", url); });
    });
    document.addEventListener("click", function (e) {
      document.querySelectorAll(".rn-ev-menu[open], #moreFilter[open]").forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
    });
  }

  function setupSearch() {
    $("#evidenceSearch").addEventListener("input", function (e) {
      state.query = e.target.value.trim();
      state.page = 0;
      applyFilter();
    });
  }

  function csvEscape(v) {
    var s = String(v == null ? "" : v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function setupExport() {
    $("#exportBtn").addEventListener("click", function () {
      var header = ["Judul", "Modul", "Lokasi", "Waktu", "Uploader", "Role", "Verifikasi", "Visibilitas", "URL"];
      var lines = [header.map(csvEscape).join(",")];
      var picked = state.filtered.filter(function (r) { return state.sel[String(r.name || r.id || r.evidence_url)]; });
      (picked.length ? picked : state.filtered).forEach(function (r) {
        lines.push([
          r.title, r.module, r.location_text || r.posko || "-", r.created_at,
          r.uploader, r.uploader_role, r.status, r.visibility, r.evidence_url,
        ].map(csvEscape).join(","));
      });
      var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "evidence-" + getEventId() + ".csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  async function loadBoard() {
    statusMsg("Memuat evidence…");
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    BOARD_CACHE = data;
    state.rows = data.rows || [];

    $("#evidenceUpdated").textContent = "Evidence · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    renderKpi(data.totals || {});
    renderModulChips(data.filter_modul || [{ label: "Semua", count: state.rows.length }]);
    applyFilter();
    statusMsg("Dimuat " + state.rows.length + " evidence.");
  }

  /* ---------- legacy upload form (unchanged behaviour) ---------- */

  async function rnFileToBase64(file) {
    var buffer = await file.arrayBuffer();
    var bytes = new Uint8Array(buffer);
    var binary = "";
    var chunk = 0x8000;
    for (var i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + chunk, bytes.length)));
    }
    return btoa(binary);
  }

  function setupUploadForm() {
    var form = $("#evidenceForm");
    if (!form) return;
    var params = new URLSearchParams(window.location.search);
    form.disaster_event_id.value = getEventId();
    var objectType = params.get("object_type") || params.get("linked_object_type");
    var objectId = params.get("object_id") || params.get("linked_object_id");
    var nodeId = params.get("node") || params.get("node_id");
    if (nodeId) form.node_id.value = nodeId;
    if (objectType) form.linked_object_type.value = objectType;
    if (objectId) form.linked_object_id.value = objectId;

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var file = form.file.files[0];
      if (!file) return;
      statusMsg("Uploading evidence...");
      try {
        var contentBase64 = await rnFileToBase64(file);
        await window.RN_FRAPPE.call("rescue_net.api_frontend_bridge.upload_evidence", {
          filename: file.name,
          content_base64: contentBase64,
          disaster_event: form.disaster_event_id.value.trim(),
          node_id: form.node_id.value.trim() || null,
          linked_object_type: form.linked_object_type.value.trim() || null,
          linked_object_id: form.linked_object_id.value.trim() || null,
          evidence_type: form.evidence_type.value.trim() || "photo",
          uploaded_by: form.uploaded_by.value.trim() || null,
        }, { method: "POST" });
        form.reset();
        statusMsg("Evidence uploaded.");
        await loadBoard();
      } catch (err) {
        statusMsg("Gagal upload: " + (err && err.message || err));
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) {
      statusMsg("Frappe client tidak tersedia.");
      return;
    }
    document.querySelectorAll(".rn-ev-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#evidenceDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });

    setupSearch();
    setupFilters();
    setupExport();
    setupUploadForm();
    loadBoard().catch(function (err) { statusMsg("Gagal memuat: " + (err && err.message || err)); });
  });
})();
