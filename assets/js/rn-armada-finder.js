/* Cari Armada (owner 2026-11-02) — public on Manajemen Distribusi. API: rescue_net.api_armada.armada_finder.
 * Filters: jenis, berangkat dari/sampai, status, sort by distance from the viewer. Booking needs login. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var ME = null, LOGGED = false;
  var CHIP = { tersedia: "ok", penuh: "warning", dipakai: "danger" };
  function num(n, unit) { return n == null ? "" : (Math.round(n * 10) / 10).toLocaleString("id-ID") + " " + unit; }
  function eventId() { return (window.RNUI && window.RNUI.eventId()) || new URLSearchParams(location.search).get("event") || ""; }

  function row(a) {
    var cap = [a.left_kg != null ? "sisa " + num(a.left_kg, "kg") + (a.capacity_kg ? " dari " + num(a.capacity_kg, "kg") : "") : "",
               a.left_m3 != null ? "sisa " + num(a.left_m3, "m³") : "", a.seats ? a.seats + " kursi relawan" : ""].filter(Boolean).join(" · ");
    var when = a.departure ? (a.flexible ? "Jadwal: " + a.departure : "Berangkat " + a.departure.replace("T", " ")) : "Jadwal fleksibel";
    var action = a.status === "dipakai" ? '<span class="rn-muted">Sedang dipakai</span>'
      : LOGGED ? '<a class="btn primary mini" href="' + esc(a.href + "&armada=" + encodeURIComponent(a.name)) + '">Pesan</a>'
      : '<a class="btn mini" href="auth.html?next=' + encodeURIComponent(a.href + "&armada=" + encodeURIComponent(a.name)) + '">Login untuk pesan</a>';
    return '<details class="rn-af-item"><summary><span class="chip ' + (CHIP[a.status] || "") + '">' + esc(a.status_label) + "</span>" +
      "<b>" + esc(a.title) + "</b><small>" + esc(a.type_label) + " · " + esc(a.route) + "</small>" +
      (a.km != null ? '<span class="rn-af-km">' + esc(a.km) + " km</span>" : "") + "</summary>" +
      '<div class="rn-af-body"><div>' + esc(when) + (a.eta ? " · tiba " + esc(a.eta) : "") + "</div>" +
      (cap ? "<div>" + esc(cap) + "</div>" : "") +
      "<div>Posko: " + esc(a.posko_title || "-") + (a.city ? " (" + esc(a.city) + ")" : "") + (a.open_booking ? " · pesanan langsung dikonfirmasi" : " · pesanan dikonfirmasi posko (PIN)") + "</div>" +
      '<div class="form-actions">' + action + ' <a class="btn ghost mini" href="' + esc(a.href) + '">Lihat posko</a></div></div></details>';
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
        '</span> <span class="chip danger">Sedang dipakai ' + (c.dipakai || 0) + "</span>" + (ME ? ' <small class="rn-muted">urut dari lokasi Anda</small>' : "");
      $("afList").innerHTML = r.rows.length ? r.rows.map(row).join("") : '<p class="rn-muted">Tidak ada armada yang cocok dengan filter.</p>';
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
    load();
  });
})();
