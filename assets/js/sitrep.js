/* Laporan Situasi (SITREP) otomatis — rescue_net.api_sitrep.sitrep for ?event=<bencana>; printable.
   2026-11-12 (owner: "sesuai template international" + "API protokol" + "button api key"): urutan mengikuti
   OCHA Situation Report — nomor & periode, highlights, angka kunci, kebutuhan/respons/kesenjangan per sektor,
   perubahan periode, prioritas tindakan, logistik & layanan, kelompok rentan, pendanaan, koordinasi, peringatan,
   laporan berikutnya; plus API (JSON, EDXL-SitRep, HXL, CAP) dan tombol Buat API key. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var num = function (v) { return v === null || v === undefined || v === "" ? "—" : Number(v).toLocaleString("id-ID"); };
  var tile = function (label, value) { return "<div><b>" + esc(value) + "</b><span>" + esc(label) + "</span></div>"; };
  var API = "/rescue-net-frappe/api/method/rescue_net.api_export.";
  var RENTAN = { female_count: "Perempuan", male_count: "Laki-laki", children_count: "Anak", elderly_count: "Lansia",
    disability_count: "Penyandang disabilitas", pregnant_count: "Ibu hamil", infants_count: "Bayi" };
  var JENIS = { transport: "Distribusi/transport", logistics: "Logistik", medical: "Medis", shelter: "Shelter", kitchen: "Dapur umum",
    org_admin: "Admin organisasi", field_assessment: "Assessment", volunteer: "Relawan", collection_hub: "Gudang pengumpul",
    posko_operator: "Operator", sar: "SAR", lainnya: "Lainnya" };
  var LAST = null;
  function eventParam() {
    var q = new URLSearchParams(location.search).get("event");
    if (q) return q;
    try { return localStorage.getItem("rn_active_event") || "event-sim-001"; } catch (e) { return "event-sim-001"; }
  }

  async function load() {
    $("srMeta").textContent = "Memuat…";
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_sitrep.sitrep", { disaster_event: eventParam(), hours: $("srHours").value });
      LAST = r;
      $("srTitle").textContent = "SITREP No. " + (r.nomor || 1) + " — " + r.bencana.title;
      $("srMeta").textContent = "Periode " + r.periode.dari + " s/d " + r.periode.sampai + " WIB · dibuat " + r.dibuat +
        " · status bencana: " + (r.bencana.status || "-") + (r.laporan_berikutnya ? " · laporan berikutnya: " + r.laporan_berikutnya + " WIB" : "");
      $("srHigh").innerHTML = (r.highlights || []).map(function (h) { return "<li>" + esc(h) + "</li>"; }).join("") || "<li>Belum ada ringkasan.</li>";
      var s = r.situasi, jl = s.jiwa_per_layanan || {};
      $("srSituasi").innerHTML = tile("Jiwa terdampak", num(s.jiwa_terdampak)) + tile("Pengungsi di shelter", num(s.pengungsi_shelter)) +
        tile("Orang hilang", num(s.orang_hilang)) + tile("Posko aktif", num(s.posko_aktif)) + tile("Posko kritis", num(s.posko_kritis)) +
        tile("Kebutuhan terbuka", num(s.kebutuhan_terbuka)) + tile("Relawan", num(s.relawan)) +
        tile("Jiwa berisiko: logistik belum sampai", num(jl.logistik)) + tile("Jiwa berisiko: shelter penuh", num(jl.shelter));
      $("srSektor").innerHTML = (r.sektor || []).map(function (x) {
        return "<tr><td><b>" + esc(x.nama) + "</b></td><td>" + num(x.kebutuhan) + (x.kritis ? ' <span class="chip danger">' + num(x.kritis) + " kritis</span>" : "") +
          "</td><td>" + esc(x.respons || "—") + "</td><td>" + ((x.kesenjangan || []).map(esc).join("<br>") || "—") + "</td></tr>";
      }).join("") || '<tr><td colspan="4">Belum ada data sektor.</td></tr>';
      $("srPeriode").textContent = r.periode.jam + " jam terakhir";
      $("srChanges").innerHTML = (r.perubahan_periode || []).map(function (c) { return tile(c.label, num(c.value)); }).join("");
      $("srNeeds").innerHTML = (r.kebutuhan_mendesak || []).length ? r.kebutuhan_mendesak.map(function (n) {
        return "<li><b>" + esc(n.judul) + "</b> — " + esc(n.alasan) + (n.prioritas ? ' <span class="chip ' + (n.prioritas === "kritis" ? "danger" : "warning") + '">' + esc(n.prioritas) + "</span>" : "") + "</li>";
      }).join("") : "<li>Tidak ada kebutuhan mendesak tercatat.</li>";
      var L = r.logistik, sh = r.layanan.shelter, med = r.layanan.medis_per_status || {};
      $("srLayanan").innerHTML = tile("Kiriman total", num(L.kiriman_total)) + tile("Kiriman terhambat", num(L.kiriman_terhambat)) +
        tile("Tawaran bantuan", num(L.tawaran_bantuan)) + tile("Penghuni shelter / kapasitas", num(sh.penghuni) + " / " + num(sh.kapasitas)) +
        tile("Titik shelter", num(sh.titik)) + tile("Keluarga di shelter", num(sh.keluarga)) + tile("Porsi dapur umum", num(r.layanan.porsi_dapur)) +
        Object.keys(med).map(function (k) { return tile("Pasien: " + k, num(med[k])); }).join("");
      var kr = r.kelompok_rentan || {}, rt = [];
      [["Di shelter", kr.shelter], ["Dari laporan warga", kr.laporan_warga]].forEach(function (g) {
        var o = g[1] || {}, parts = Object.keys(o).filter(function (k) { return o[k]; }).map(function (k) { return (RENTAN[k] || k) + " " + num(o[k]); });
        if (parts.length) rt.push("<li><b>" + g[0] + ":</b> " + esc(parts.join(" · ")) + "</li>");
      });
      $("srRentan").innerHTML = rt.join("") || "<li>Belum ada data terpilah (jenis kelamin, usia, disabilitas).</li>";
      var d = r.pendanaan || {};
      $("srDana").innerHTML = d.program ? tile("Program khusus", num(d.program)) + tile("Target (Rp)", num(d.target_rp)) +
        tile("Terkumpul (Rp)", num(d.terkumpul_rp)) + tile("Capaian", d.persen == null ? "—" : d.persen + "%") : "<p>Belum ada program pendanaan untuk bencana ini.</p>";
      var k = r.koordinasi || {}, pj = k.posko_per_jenis || {};
      $("srKoord").innerHTML = "<p>" + num(k.organisasi) + " organisasi · " + num(k.posko) + " posko. " +
        Object.keys(pj).map(function (j) { return esc(JENIS[j] || j) + " " + num(pj[j]); }).join(" · ") + "</p>" +
        (k.pusat_kendali ? "<p>Pusat kendali: " + esc(k.pusat_kendali) + "</p>" : "");
      var al = (r.peringatan || []).map(function (a) { return "<li>" + esc(a) + "</li>"; });
      (r.gempa_bmkg || []).forEach(function (q) { al.push("<li>BMKG (nasional, belum tentu terkait bencana ini): " + esc(q.title) + " (" + esc(q.issued_at) + " UTC)</li>"); });
      $("srAlerts").innerHTML = al.join("") || "<li>Tidak ada peringatan.</li>";
      $("srNote").textContent = r.catatan || "";
      renderApi(r.bencana.id);
    } catch (e) {
      $("srMeta").textContent = "Gagal memuat: " + ((e && e.message) || e);
    }
  }

  function renderApi(ev) {
    var q = "?disaster_event=" + encodeURIComponent(ev) + "&hours=" + encodeURIComponent($("srHours").value);
    $("srApiList").innerHTML =
      "<li><b>JSON</b> (SITREP lengkap, perlu kunci): <code>" + esc(API + "sitrep_json" + q) + "</code></li>" +
      "<li><b>EDXL-SitRep 1.0</b> (OASIS, XML, perlu kunci): <code>" + esc(API + "sitrep_edxl" + q) + "</code></li>" +
      "<li><b>HXL</b> angka kunci (CSV, perlu kunci): <code>" + esc(API + "sitrep_hxl" + q) + "</code></li>" +
      '<li><b>HXL</b> kebutuhan per posko (publik): <a href="' + API + "hxl_needs?disaster_event=" + encodeURIComponent(ev) + '">hxl_needs</a></li>' +
      '<li><b>CAP 1.2</b> peringatan gempa (publik): <a href="' + API + 'cap_alerts">cap_alerts</a></li>';
    var logged = !!(window.RNSession && window.RNSession.getSession && window.RNSession.getSession());
    $("srKeyBtn").hidden = !logged;
    $("srKeyHint").textContent = logged ? "Kunci hanya bisa dibuat super admin atau admin organisasi." : "Login sebagai super admin / admin organisasi untuk membuat kunci API.";
  }

  async function makeKey() {
    var out = $("srKeyOut");
    if (!confirm("Buat kunci API SITREP baru? Kunci lama organisasi Anda akan tidak berlaku.")) return;
    out.hidden = false; out.textContent = "Membuat kunci…";
    try {
      var k = await window.RN_FRAPPE.call("rescue_net.api_export.buat_kunci_api_sitrep", {}, { method: "POST" });
      var ev = LAST ? LAST.bencana.id : eventParam();
      out.innerHTML = "<b>Kunci API dibuat — simpan sekarang, rahasia tidak bisa ditampilkan lagi.</b>" +
        "<pre>api_key    : " + esc(k.api_key) + "\napi_secret : " + esc(k.api_secret) + "\nheader     : " + esc(k.header) + "</pre>" +
        "<p>Contoh:</p><pre>curl -H \"" + esc(k.header) + "\" \\\n  \"https://rescue-net.online" + esc(API) + "sitrep_edxl?disaster_event=" + esc(ev) + "&amp;hours=24\"</pre>" +
        '<button type="button" class="btn ghost mini" id="srKeyCopy">Salin header</button>';
      $("srKeyCopy").addEventListener("click", function () {
        try { navigator.clipboard.writeText(k.header); $("srKeyCopy").textContent = "Tersalin"; } catch (e) { /* abaikan */ }
      });
    } catch (e) {
      out.textContent = "Gagal: " + ((e && e.message) || e);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("srFilter").addEventListener("submit", function (e) { e.preventDefault(); load(); });
    $("srHours").addEventListener("change", function () { load(); });
    $("srPrint").addEventListener("click", function () { window.print(); });
    $("srKeyBtn").addEventListener("click", makeKey);
    load();
  });
})();
