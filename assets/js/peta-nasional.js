/* Peta Nasional — api_gis.national_situation */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function n(x) { return Number(x || 0).toLocaleString("id-ID"); }
  var SEV_COLOR = { critical: "#c0392b", urgent: "#d8862f", high: "#d8862f", normal: "#3b82c4", low: "#7aa7cf" };
  function sevChip(s) {
    var c = SEV_COLOR[s] || "#8a7d74";
    return '<span class="chip" style="color:' + c + ';border-color:' + c + '">' + esc(s || "normal") + "</span>";
  }

  var MAP = null, LAYER = null, DATA = null;

  function initMap() {
    if (MAP || !window.L) return;
    MAP = L.map("pnMap", { zoomControl: true }).setView([-2.2, 117.0], 4);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(MAP);
    LAYER = L.layerGroup().addTo(MAP);
  }

  function drawPoints(filterProv) {
    if (!MAP || !DATA) return;
    LAYER.clearLayers();
    var pts = (DATA.points || []).filter(function (p) {
      return !filterProv || p.province === filterProv;
    });
    var bounds = [];
    pts.forEach(function (p) {
      var lat = Number(p.lat), lng = Number(p.lng);
      if (!isFinite(lat) || !isFinite(lng)) return;
      var col = SEV_COLOR[p.severity] || "#3b82c4";
      var badge = window.RNVerifBadge
        ? window.RNVerifBadge.html(p.verification_status, p.trusted_verifier_count) : esc(p.verification_status);
      L.circleMarker([lat, lng], {
        radius: 7, color: col, weight: 2, fillColor: col, fillOpacity: 0.55,
      }).bindPopup(
        "<b>" + esc(p.title) + "</b><br>" +
        esc(p.posko_type || "") + " · " + esc(p.city || p.province || "") + "<br>" +
        (p.event ? "Bencana: " + esc(p.event) + " (" + esc(p.severity) + ")<br>" : "") +
        badge
      ).addTo(LAYER);
      bounds.push([lat, lng]);
    });
    if (bounds.length) {
      try { MAP.fitBounds(bounds, { padding: [30, 30], maxZoom: 11 }); } catch (e) {}
    }
  }

  async function load() {
    var d;
    try {
      d = await window.RN_FRAPPE.call("rescue_net.api_gis.national_situation", { active_only: 1 });
    } catch (e) { $("#pnStatus").textContent = "Gagal memuat: " + (e && e.message || e); return; }
    DATA = d;
    var t = d.totals || {};
    $("#kpiProv").textContent = n(t.provinces_affected);
    $("#kpiPosko").textContent = n(t.posko_total);
    $("#kpiVerif").textContent = n(t.verified_total) + " (" + n(t.official_verified_total) + " resmi)";
    $("#kpiBencana").textContent = n(t.active_disasters);
    $("#kpiJiwa").textContent = n(t.people_served_total);
    $("#pnStatus").textContent = t.provinces_affected + " provinsi · " + t.posko_total + " posko · " +
      t.active_disasters + " bencana aktif · " + n(t.open_needs_total) + " kebutuhan terbuka.";

    var sel = $("#pnProvFilter");
    sel.innerHTML = '<option value="">Semua provinsi</option>' +
      (d.provinces || []).map(function (p) {
        return '<option value="' + esc(p.province) + '">' + esc(p.province) + " (" + p.posko_count + ")</option>";
      }).join("");
    sel.onchange = function () { drawPoints(sel.value); };

    $("#pnBody").innerHTML = (d.provinces || []).map(function (p) {
      return "<tr>" +
        "<td><b>" + esc(p.province) + "</b><small class=\"rn-muted\">" + esc((p.events || []).join(", ")) + "</small></td>" +
        "<td>" + sevChip(p.severity) + "</td>" +
        "<td>" + p.event_count + "</td>" +
        "<td>" + p.posko_count + "</td>" +
        "<td>" + p.verified + " <small class=\"rn-muted\">(" + p.official_verified + " resmi)</small></td>" +
        "<td>" + n(p.open_needs) + "</td>" +
        "<td>" + n(p.people_served) + "</td>" +
        "</tr>";
    }).join("") || '<tr><td colspan="7"><em class="rn-muted">Belum ada data.</em></td></tr>';

    initMap();
    setTimeout(function () { if (MAP) MAP.invalidateSize(); drawPoints(""); }, 200);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", load);
  else load();
})();
