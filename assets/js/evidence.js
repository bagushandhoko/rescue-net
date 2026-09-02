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

  var state = { rows: [], filtered: [], module: "Semua", query: "", page: 0 };
  var BOARD_CACHE = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }

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

  function applyFilter() {
    var q = state.query.toLowerCase();
    state.filtered = state.rows.filter(function (r) {
      if (state.module !== "Semua" && r.module !== state.module) return false;
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
      body.innerHTML = '<tr><td colspan="7"><em class="rn-muted">Tidak ada evidence yang cocok.</em></td></tr>';
    } else {
      body.innerHTML = slice.map(function (r) {
        var url = r.evidence_url || "";
        var thumb = r.mime === "image"
          ? '<img src="' + esc(url) + '" alt="" loading="lazy">'
          : '<span class="rn-ev-thumb-icon">' + mimeIcon(r.mime) + "</span>";
        var geo = (r.latitude && r.longitude && (Math.abs(r.latitude) > 0.0001 || Math.abs(r.longitude) > 0.0001))
          ? '<small class="rn-ev-geo">📍 ' + r.latitude.toFixed(4) + ", " + r.longitude.toFixed(4) + "</small>"
          : "";
        return (
          "<tr>" +
          '<td><a class="rn-ev-cell" href="' + esc(url) + '" target="_blank" rel="noopener">' +
          '<span class="rn-ev-thumb">' + thumb + "</span>" +
          "<span><b>" + esc(r.title || "Evidence") + "</b><small>" + esc(filename(url)) + "</small>" + geo + "</span>" +
          "</a></td>" +
          '<td><span class="chip">' + esc(r.module) + "</span></td>" +
          "<td>" + esc(r.location_text || r.posko || "-") + "</td>" +
          "<td>" + esc(String(r.created_at || "").slice(0, 16).replace("T", " ")) + "</td>" +
          "<td><b>" + esc(r.uploader || "-") + "</b><small>" + esc(r.uploader_role || "-") + "</small></td>" +
          '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status || "-") + "</span></td>" +
          '<td><span class="chip ' + (r.visibility === "public" ? "ok" : "") + '">' + (r.visibility === "public" ? "Publik" : "Terbatas") + "</span></td>" +
          "</tr>"
        );
      }).join("");
    }

    $("#evidenceShown").textContent = total
      ? "Menampilkan " + (state.page * PAGE_SIZE + 1) + "-" + Math.min(total, (state.page + 1) * PAGE_SIZE) + " dari " + total + " evidence"
      : "0 evidence";

    var pager = $("#evidencePager");
    var btns = [];
    for (var i = 0; i < pages; i++) {
      btns.push('<button type="button" class="rn-ev-page' + (i === state.page ? " is-active" : "") + '" data-page="' + i + '">' + (i + 1) + "</button>");
    }
    pager.innerHTML = btns.join("");
    pager.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.page = Number(btn.getAttribute("data-page"));
        renderTable();
      });
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
      state.filtered.forEach(function (r) {
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
    setupExport();
    setupUploadForm();
    loadBoard().catch(function (err) { statusMsg("Gagal memuat: " + (err && err.message || err)); });
  });
})();
