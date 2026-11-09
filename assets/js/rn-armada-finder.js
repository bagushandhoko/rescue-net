/* Cari Armada (owner 2026-11-02) — public on Manajemen Distribusi. API: rescue_net.api_armada.armada_finder.
 * Filters: jenis, berangkat dari/sampai, status, sort by distance from the viewer. Booking needs login. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var ME = null, LOGGED = false, MAP = null, LAYER = null, TRAIL = null, ROWS = [];
  var COLOR = { tersedia: "#2f9a5c", penuh: "#e08a1e", dipakai: "#d23c3c", lewat: "#a89a91", selesai: "#7d8a99" };

  function drawMap(rows) {
    var host = $("afMap");
    if (!host || typeof L === "undefined") { if (host) host.hidden = true; return; }
    if (!MAP) {
      MAP = L.map(host, { scrollWheelZoom: false }).setView([-2.5, 118], 4);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(MAP);
      LAYER = L.layerGroup().addTo(MAP);
    }
    LAYER.clearLayers();
    var pts = [];
    rows.forEach(function (a) {
      if (!a.pos) return;
      pts.push(a.pos);
      var m = L.circleMarker(a.pos, { radius: a.pos_live ? 9 : 7, weight: 2, color: "#fff", dashArray: a.pos_live ? null : "3",
        fillColor: COLOR[a.status] || "#888", fillOpacity: a.pos_live ? 0.95 : 0.55 }).addTo(LAYER);
      m.bindPopup("<b>" + esc(a.title) + "</b><br>" + esc(a.status_label) + " · " + esc(a.type_label) +
        (a.left_kg != null ? "<br>sisa " + num(a.left_kg, "kg") : "") +
        "<br>" + (a.pos_live ? "GPS " + esc(a.pos_at) : "lokasi posko " + esc(a.posko_title)) +
        '<br><a href="#" data-trail="' + esc(a.name) + '">Lihat jejak</a>');
    });
    if (ME) pts.push(ME);
    if (pts.length) MAP.fitBounds(pts, { padding: [24, 24], maxZoom: 12 });
    setTimeout(function () { MAP.invalidateSize(); }, 60);
  }

  async function showTrail(id) {
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_armada.armada_trail", { transport_space: id });
      if (TRAIL) { MAP.removeLayer(TRAIL); TRAIL = null; }
      var pts = (r.points || []).map(function (p) { return [p[0], p[1]]; });
      if (!pts.length) { alert("Belum ada jejak GPS untuk armada ini."); return; }
      TRAIL = L.layerGroup([L.polyline(pts, { color: "#c4442f", weight: 4, opacity: 0.8 })].concat(
        (r.points || []).map(function (p, i) {
          return L.circleMarker([p[0], p[1]], { radius: i === pts.length - 1 ? 6 : 3, color: "#c4442f", fillOpacity: 1 }).bindTooltip(p[2]);
        }))).addTo(MAP);
      MAP.fitBounds(pts, { padding: [30, 30], maxZoom: 14 });
      $("afMap").scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (e) { alert((e && e.message) || e); }
  }
  var CHIP = { tersedia: "ok", penuh: "warning", dipakai: "danger", lewat: "", selesai: "" };
  function num(n, unit) { return n == null ? "" : (Math.round(n * 10) / 10).toLocaleString("id-ID") + " " + unit; }
  function eventId() { return (window.RNUI && window.RNUI.eventId()) || new URLSearchParams(location.search).get("event") || ""; }

  function row(a) {
    var cap = [a.left_kg != null ? "sisa " + num(a.left_kg, "kg") + (a.capacity_kg ? " dari " + num(a.capacity_kg, "kg") : "") : "",
               a.left_m3 != null ? "sisa " + num(a.left_m3, "m³") : "", a.seats ? a.seats + " kursi relawan" : ""].filter(Boolean).join(" · ");
    var when = a.departure ? (a.flexible ? "Jadwal: " + a.departure : "Berangkat " + a.departure.replace("T", " ")) : "Jadwal fleksibel";
    var action = a.status === "selesai" ? '<span class="rn-muted">Perjalanan sudah selesai</span>'
      : a.status === "lewat" ? '<span class="rn-muted">Jadwal sudah lewat — hubungi posko untuk jadwal baru</span>'
      : a.status === "dipakai" ? '<span class="rn-muted">Sedang dipakai</span>'
      : LOGGED ? '<a class="btn primary mini" href="' + esc(a.href + "&armada=" + encodeURIComponent(a.name)) + '">Pesan</a>'
      : '<a class="btn mini" href="auth.html?next=' + encodeURIComponent(a.href + "&armada=" + encodeURIComponent(a.name)) + '">Login untuk pesan</a>';
    return '<details class="rn-af-item"><summary><span class="chip ' + (CHIP[a.status] || "") + '">' + esc(a.status_label) + "</span>" +
      "<b>" + esc(a.title) + "</b><small>" + esc(a.type_label) + " · " + esc(a.route) + "</small>" +
      (a.km != null ? '<span class="rn-af-km">' + esc(a.km) + " km</span>" : "") + "</summary>" +
      '<div class="rn-af-body"><div>' + esc(when) + (a.eta ? " · tiba " + esc(a.eta) : "") + "</div>" +
      (cap ? "<div>" + esc(cap) + "</div>" : "") +
      "<div>Posko: " + esc(a.posko_title || "-") + (a.city ? " (" + esc(a.city) + ")" : "") + (a.open_booking ? " · pesanan langsung dikonfirmasi" : " · pesanan dikonfirmasi posko (PIN)") + "</div>" +
      (a.pos_live ? "<div>📍 Posisi GPS diperbarui " + esc(a.pos_at) + "</div>" : "") +
      '<div class="form-actions">' + action + ' <a class="btn ghost mini" href="' + esc(a.href) + '">Lihat posko</a>' +
      (a.pos ? ' <button type="button" class="btn ghost mini" data-trail="' + esc(a.name) + '">Lihat jejak</button>' : "") + "</div></div></details>";
  }

  async function load() {
    var args = { disaster_event: eventId() || null, transport_type: $("afType").value || null, date_from: $("afFrom").value || null,
                 date_to: $("afTo").value || null, status: $("afStatus").value || null };
    if (ME) { args.lat = ME[0]; args.lng = ME[1]; }
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_armada.armada_finder", args);
      LOGGED = !!r.logged_in;
      var c = r.counts || {};
      $("afCounts").innerHTML = '<span class="chip ok">Tersedia ' + (c.tersedia || 0) + '</span> <span class="chip warning">Penuh ' + (c.penuh || 0) +
        '</span> <span class="chip danger">Sedang dipakai ' + (c.dipakai || 0) + '</span> <span class="chip">Jadwal lewat ' + (c.lewat || 0) + '</span> <span class="chip" data-af-done>Selesai ' + (c.selesai || 0) + "</span>" + (ME ? ' <small class="rn-muted">urut dari lokasi Anda</small>' : "");
      ROWS = r.rows;
      $("afList").innerHTML = r.rows.length ? r.rows.map(row).join("") : '<p class="rn-muted">Tidak ada armada yang cocok dengan filter.' +
        (c.selesai && $("afStatus").value !== "selesai" ? ' ' + c.selesai + ' armada sudah selesai perjalanan — <a href="#" data-af-showdone>tampilkan</a>.' : "") + "</p>";
      drawMap(r.rows);
    } catch (e) { $("afList").innerHTML = '<p class="rn-muted">' + esc((e && e.message) || e) + "</p>"; }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!$("armadaFinder") || !window.RN_FRAPPE) return;
    ["afType", "afFrom", "afTo", "afStatus"].forEach(function (id) { $(id).addEventListener("change", load); });
    $("afNear").addEventListener("click", function () {
      if (!navigator.geolocation) return alert("Peramban tidak mendukung lokasi.");
      $("afNear").textContent = "Mencari lokasi…";
      navigator.geolocation.getCurrentPosition(function (p) {
        ME = [p.coords.latitude, p.coords.longitude]; $("afNear").textContent = "📍 Diurutkan dari lokasi Anda"; load();
      }, function () { $("afNear").textContent = "📍 Urutkan dari lokasi saya"; alert("Izin lokasi ditolak."); });
    });
    document.addEventListener("click", function (e) {
      if (e.target.closest("[data-af-showdone]")) { e.preventDefault(); $("afStatus").value = "selesai"; load(); return; }
      var t = e.target.closest("[data-trail]");
      if (!t) return;
      e.preventDefault(); showTrail(t.getAttribute("data-trail"));
    });
    load();
    setInterval(function () { if (!document.hidden) load(); }, 60000);   // live: refresh positions every minute
  });
})();
