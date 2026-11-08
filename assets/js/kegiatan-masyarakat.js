/* Kegiatan Masyarakat Umum per bencana (owner 2026-11-09: profil = apa yang dilakukan dalam penanganan bencana).
   rescue_net.api_org_profile.community_activity (tamu) — hanya angka & kegiatan, tanpa nama/kontak. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  function esc(v) { return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function num(n) { return new Intl.NumberFormat("id-ID").format(Math.round(Number(n || 0) * 100) / 100); }
  function rp(n) { return "Rp " + num(n); }
  var JENIS = { kebutuhan: "Kebutuhan", kejadian: "Kejadian", kerusakan: "Kerusakan", pengungsi: "Pengungsi", korban: "Korban", akses: "Akses jalan", lainnya: "Lainnya" };
  function card(title, sub, inner) { return '<div class="po-card"><h2>' + esc(title) + "</h2>" + (sub ? '<p class="sub">' + esc(sub) + "</p>" : "") + inner + "</div>"; }
  function list(items, fn, empty) { return items && items.length ? '<ul class="po-list">' + items.map(fn).join("") + "</ul>" : '<p class="po-muted">' + esc(empty) + "</p>"; }
  function ev() {
    var q = new URLSearchParams(location.search).get("event");
    if (q) return q;
    try { return (localStorage.getItem("rn_active_event") || "").replace(/^disaster_events:/, ""); } catch (e) { return ""; }
  }
  async function setupNav() {
    $("kmBack").onclick = function () {
      if (document.referrer && document.referrer.indexOf(location.host) > -1 && history.length > 1) history.back();
      else location.href = "back-office.html" + (ev() ? "?event=" + encodeURIComponent(ev()) : "");
    };
    var evs = [];
    try { evs = await window.RN_FRAPPE.call("rescue_net.api_ai.public_active_disasters", {}); } catch (e) {}
    evs = Array.isArray(evs) ? evs : [];
    var cur = ev(), known = evs.some(function (e) { return (e.id || e.name) === cur; });
    if (evs.length && (!cur || !known)) { cur = evs[0].id || evs[0].name; var u = new URL(location.href); u.searchParams.set("event", cur); history.replaceState(null, "", u.toString()); }
    var sel = $("kmEvent");
    sel.innerHTML = evs.map(function (e) { var id = e.id || e.name; return '<option value="' + esc(id) + '"' + (id === cur ? " selected" : "") + ">" + esc(e.title || id) + "</option>"; }).join("") || '<option value="">Tidak ada bencana aktif</option>';
    sel.onchange = function () { try { localStorage.setItem("rn_active_event", sel.value); } catch (e) {} var u = new URL(location.href); u.searchParams.set("event", sel.value); location.href = u.toString(); };
    return cur;
  }
  async function load() {
    var cur = await setupNav();
    if (!cur) { $("kmBody").innerHTML = card("Belum ada bencana aktif", "", ""); return; }
    var d;
    try { d = await window.RN_FRAPPE.call("rescue_net.api_org_profile.community_activity", { disaster_event: cur }); }
    catch (e) { $("kmBody").innerHTML = card("Gagal memuat", String((e && e.message) || e), ""); return; }
    var L = d.laporan || {}, B = d.bantuan_barang || {}, D = d.donasi || {}, R = d.relawan || {}, A = d.alat || {}, S = d.sar || {};
    var kpi = [[L.total, "laporan warga"], [B.total, "tawaran bantuan barang"], [D.jumlah, "donasi perorangan"], [D.total, "dana didonasikan", true],
      [R.penugasan, "penugasan relawan"], [A.jumlah, "alat ditawarkan"], [S.hilang, "laporan orang hilang"], [S.ditemukan, "orang/barang ditemukan"]];
    var html = card("Ringkasan kegiatan", d.event_title || "", '<div class="po-kpis">' + kpi.map(function (k) {
      return '<div class="po-kpi"><b>' + (k[2] ? rp(k[0]) : num(k[0])) + "</b><span>" + esc(k[1]) + "</span></div>"; }).join("") + "</div>");
    html += '<div class="po-two">' +
      card("Laporan dari warga", num(L.ke_posko) + " laporan langsung diteruskan ke posko.", list(L.per_jenis, function (x) {
        return "<li><b>" + num(x.n) + "</b> " + esc(JENIS[x.jenis] || x.jenis) + "</li>"; }, "Belum ada laporan warga.")) +
      card("Bantuan barang dari perorangan", "Barang yang ditawarkan/dikirim lewat Kirim Bantuan.", list(B.barang, function (x) {
        return "<li>" + esc(x.item) + " — <b>" + num(x.jumlah) + " " + esc(x.satuan || "") + "</b></li>"; }, "Belum ada tawaran bantuan barang.")) +
      "</div>";
    html += '<div class="po-two">' +
      card("Donasi ke program", D.jumlah ? num(D.jumlah) + " donasi terkonfirmasi, total " + rp(D.total) + "." : "", list(D.program, function (x) {
        return '<li><a href="' + esc(x.href) + "&event=" + encodeURIComponent(cur) + '">' + esc(x.program) + "</a><br><span class=\"po-muted\">" + num(x.n) + " donasi · " + rp(x.total) + "</span></li>"; }, "Belum ada donasi terkonfirmasi.")) +
      card("Relawan bertugas", num(R.penugasan) + " penugasan di posko.", list(R.posko, function (x) {
        return '<li><a href="' + esc(x.href) + "&event=" + encodeURIComponent(cur) + '">' + esc(x.posko) + "</a> — " + num(x.n) + " penugasan</li>"; }, "Belum ada penugasan relawan.")) +
      "</div>";
    html += '<div class="po-two">' +
      card("Alat yang ditawarkan perorangan", "", list(A.kategori, function (x) { return "<li><b>" + num(x.n) + "</b> " + esc(x.kategori) + "</li>"; }, "Belum ada alat dari perorangan.")) +
      card("Posko yang dikelola perorangan", "Posko tanpa organisasi.", list(d.posko_perorangan, function (x) {
        return '<li><a href="' + esc(x.href) + "&event=" + encodeURIComponent(cur) + '">' + esc(x.title) + "</a> <span class=\"po-muted\">" + esc(x.jenis || "") + "</span></li>"; }, "Tidak ada posko perorangan.")) +
      "</div>";
    html += card("Ikut membantu", "", '<div class="po-cta"><a class="btn primary" href="kirim-bantuan.html?event=' + encodeURIComponent(cur) + '">Kirim Bantuan</a>' +
      '<a class="btn" href="program-khusus.html?event=' + encodeURIComponent(cur) + '">Donasi</a><a class="btn" href="laporan-masyarakat.html">Lapor Kondisi</a>' +
      '<a class="btn" href="relawan-saya.html">Jadi Relawan</a><a class="btn" href="riwayat-kegiatan.html?scope=masyarakat&event=' + encodeURIComponent(cur) + '">Riwayat kegiatan →</a></div>');
    $("kmBody").innerHTML = html;
  }
  document.addEventListener("DOMContentLoaded", function () { if (window.RN_FRAPPE) load(); });
})();
