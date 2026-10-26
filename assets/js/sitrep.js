/* Laporan Situasi (SITREP) otomatis (2026-10-26): rescue_net.api_sitrep.sitrep
   for ?event=<bencana>; printable (sidebar & form hidden in print). */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var num = function (v) { return v === null || v === undefined || v === "" ? "—" : Number(v).toLocaleString("id-ID"); };
  var tile = function (label, value) { return "<div><b>" + esc(value) + "</b><span>" + esc(label) + "</span></div>"; };
  function eventParam() {
    var q = new URLSearchParams(location.search).get("event");
    if (q) return q;
    try { return localStorage.getItem("rn_active_event") || "event-sim-001"; } catch (e) { return "event-sim-001"; }
  }

  async function load() {
    $("srMeta").textContent = "Memuat…";
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_sitrep.sitrep", { disaster_event: eventParam(), hours: $("srHours").value });
      $("srTitle").textContent = "SITREP — " + r.bencana.title;
      $("srMeta").textContent = "Periode " + r.periode.dari + " s/d " + r.periode.sampai + " · dibuat " + r.dibuat + " · status bencana: " + (r.bencana.status || "-");
      var s = r.situasi, jl = s.jiwa_per_layanan || {};
      $("srSituasi").innerHTML = tile("Jiwa terdampak", num(s.jiwa_terdampak)) + tile("Orang hilang", num(s.orang_hilang)) +
        tile("Posko aktif", num(s.posko_aktif)) + tile("Posko kritis", num(s.posko_kritis)) + tile("Kebutuhan terbuka", num(s.kebutuhan_terbuka)) +
        tile("Relawan", num(s.relawan)) + tile("Jiwa dilayani logistik", num(jl.logistik)) + tile("Jiwa di shelter", num(jl.shelter));
      $("srPeriode").textContent = r.periode.jam + " jam terakhir";
      $("srChanges").innerHTML = (r.perubahan_periode || []).map(function (c) { return tile(c.label, num(c.value)); }).join("");
      $("srNeeds").innerHTML = (r.kebutuhan_mendesak || []).length ? r.kebutuhan_mendesak.map(function (n) {
        return "<li><b>" + esc(n.judul) + "</b> — " + esc(n.alasan) + (n.prioritas ? ' <span class="chip ' + (n.prioritas === "critical" ? "danger" : "warning") + '">' + esc(n.prioritas) + "</span>" : "") + "</li>";
      }).join("") : "<li>Tidak ada kebutuhan mendesak tercatat.</li>";
      var L = r.logistik, sh = r.layanan.shelter, med = r.layanan.medis_per_status || {};
      $("srLayanan").innerHTML = tile("Kiriman total", num(L.kiriman_total)) + tile("Kiriman terhambat", num(L.kiriman_terhambat)) +
        tile("Tawaran bantuan", num(L.tawaran_bantuan)) + tile("Penghuni shelter / kapasitas", num(sh.penghuni) + " / " + num(sh.kapasitas)) +
        tile("Titik shelter", num(sh.titik)) + tile("Porsi dapur umum", num(r.layanan.porsi_dapur)) +
        Object.keys(med).map(function (k) { return tile("Pasien: " + k, num(med[k])); }).join("");
      var al = (r.peringatan || []).map(function (a) { return "<li>" + esc(a) + "</li>"; });
      (r.gempa_bmkg || []).forEach(function (q) { al.push("<li>BMKG: " + esc(q.title) + " (" + esc(q.issued_at) + " UTC)</li>"); });
      $("srAlerts").innerHTML = al.join("") || "<li>Tidak ada peringatan.</li>";
      var api = "/rescue-net-frappe/api/method/rescue_net.api_export.";
      $("srNote").innerHTML = esc(r.catatan) + "<br>Data standar untuk sistem lain: " +
        '<a href="' + api + "hxl_needs?disaster_event=" + encodeURIComponent(r.bencana.id) + '">kebutuhan (HXL/CSV)</a> · ' +
        '<a href="' + api + 'cap_alerts">peringatan gempa (CAP)</a>';
    } catch (e) {
      $("srMeta").textContent = "Gagal memuat: " + ((e && e.message) || e);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("srFilter").addEventListener("submit", function (e) { e.preventDefault(); load(); });
    $("srPrint").addEventListener("click", function () { window.print(); });
    load();
  });
})();
