/* Riwayat Kegiatan (owner 2026-11-09): telusuri apa yang dilakukan organisasi (satu kesatuan, termasuk anaknya),
   posko, atau masyarakat umum pada satu bencana — kinerja + daftar kegiatan berurutan waktu.
   ?scope=all|organisasi|posko|masyarakat &id= &event= &jenis= */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  function esc(v) { return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function num(n) { return new Intl.NumberFormat("id-ID").format(Math.round(Number(n || 0))); }
  var IC = { kirim: "🚚", terima: "📦", dapur: "🍲", medis: "🩺", shelter: "🏠", stok: "📋", bukti: "📷", relawan: "🙋", laporan: "📣", sar: "🔎", donasi: "💚", realisasi: "🧾" };
  var Q = new URLSearchParams(location.search);
  var SCOPE = Q.get("scope") || "all", ID = Q.get("id") || "", KIND = Q.get("jenis") || "";
  function ev() {
    var q = Q.get("event"); if (q) return q;
    try { return (localStorage.getItem("rn_active_event") || "").replace(/^disaster_events:/, ""); } catch (e) { return ""; }
  }
  function card(t, sub, inner) { return '<div class="po-card"><h2>' + esc(t) + "</h2>" + (sub ? '<p class="sub">' + esc(sub) + "</p>" : "") + inner + "</div>"; }
  function url(over) {
    var u = new URL(location.href);
    Object.keys(over).forEach(function (k) { if (over[k] === null || over[k] === "") u.searchParams.delete(k); else u.searchParams.set(k, over[k]); });
    return u.pathname.split("/").pop() + u.search;
  }
  async function nav() {
    $("rkBack").onclick = function () {
      if (document.referrer && document.referrer.indexOf(location.host) > -1 && history.length > 1) history.back();
      else location.href = "back-office.html" + (ev() ? "?event=" + encodeURIComponent(ev()) : "");
    };
    var evs = [];
    try { evs = await window.RN_FRAPPE.call("rescue_net.api_ai.public_active_disasters", {}); } catch (e) {}
    evs = Array.isArray(evs) ? evs : [];
    var cur = ev(), known = evs.some(function (e) { return (e.id || e.name) === cur; });
    if (evs.length && (!cur || !known)) { cur = evs[0].id || evs[0].name; history.replaceState(null, "", url({ event: cur })); }
    var sel = $("rkEvent");
    sel.innerHTML = evs.map(function (e) { var id = e.id || e.name; return '<option value="' + esc(id) + '"' + (id === cur ? " selected" : "") + ">" + esc(e.title || id) + "</option>"; }).join("") || '<option value="">Tidak ada bencana aktif</option>';
    sel.onchange = function () { try { localStorage.setItem("rn_active_event", sel.value); } catch (e) {} location.href = url({ event: sel.value }); };
    return cur;
  }
  async function load() {
    var cur = await nav();
    if (!cur) { $("rkBody").innerHTML = card("Belum ada bencana aktif", "", ""); return; }
    var d;
    try { d = await window.RN_FRAPPE.call("rescue_net.api_org_profile.activity_history", { disaster_event: cur, scope: SCOPE, scope_id: ID || null, kind: KIND || null, limit: 300 }); }
    catch (e) { $("rkTitle").textContent = "Riwayat tidak bisa dimuat"; $("rkBody").innerHTML = card("Gagal memuat", String((e && e.message) || e), ""); return; }
    document.title = "Rescue-Net | Riwayat — " + d.title;
    $("rkTitle").textContent = d.title;
    $("rkSub").textContent = (d.subtitle ? d.subtitle + " · " : "") + (d.event_title || "");
    $("rkLinks").innerHTML = (d.href ? '<a class="btn" href="' + esc(d.href) + (d.href.indexOf("?") > -1 ? "&" : "?") + "event=" + encodeURIComponent(cur) + '">' +
      (SCOPE === "organisasi" ? "Profil organisasi" : SCOPE === "posko" ? "Halaman posko" : "Ringkasan masyarakat") + " →</a>" : "") +
      (SCOPE !== "all" ? '<a class="btn" href="' + esc(url({ scope: "all", id: "", jenis: "" })) + '">Semua pihak</a>' : "");
    var S = d.sums || {};
    var kpi = '<div class="po-kpis"><div class="po-kpi"><b>' + num(d.total) + "</b><span>kegiatan tercatat</span></div>" +
      (d.poskos && d.poskos.length ? '<div class="po-kpi"><b>' + num(d.poskos.length) + "</b><span>posko terlibat</span></div>" : "") +
      (S.porsi ? '<div class="po-kpi"><b>' + num(S.porsi) + "</b><span>porsi makanan</span></div>" : "") +
      (S.pasien ? '<div class="po-kpi"><b>' + num(S.pasien) + "</b><span>pasien dilayani</span></div>" : "") +
      (S.dana ? '<div class="po-kpi"><b>Rp ' + num(S.dana) + "</b><span>donasi terkonfirmasi</span></div>" : "") +
      (S.realisasi ? '<div class="po-kpi"><b>Rp ' + num(S.realisasi) + "</b><span>dana direalisasikan</span></div>" : "") + "</div>";
    var max = Math.max.apply(null, (d.per_hari || []).map(function (x) { return x.n; }).concat([1]));
    var days = '<div class="rk-days">' + (d.per_hari || []).map(function (x) {
      return '<div title="' + esc(x.tanggal) + ": " + x.n + ' kegiatan"><span>' + x.n + '</span><i style="height:' + Math.round(x.n / max * 80) + 'px"></i><span>' + esc(x.tanggal.slice(8)) + "</span></div>"; }).join("") + "</div>";
    var chips = '<div class="rk-chips"><button type="button" data-k=""' + (KIND ? "" : ' class="on"') + ">Semua (" + num(d.total) + ")</button>" +
      (d.counts || []).map(function (c) { return '<button type="button" data-k="' + esc(c.jenis) + '"' + (KIND === c.jenis ? ' class="on"' : "") + ">" + (IC[c.jenis] || "") + " " + esc(c.label) + " (" + num(c.n) + ")</button>"; }).join("") + "</div>";
    var html = card("Kinerja & kontribusi", "Jumlah kegiatan per jenis dan 7 hari terakhir.", kpi + days) + card("Saring jenis kegiatan", "", chips);
    if (SCOPE !== "posko" && d.poskos && d.poskos.length) {
      html += card("Posko terlibat (" + d.poskos.length + ")", "Klik untuk melihat riwayat satu posko.", '<div class="po-orgs">' + d.poskos.map(function (p) {
        return '<a class="po-badge" href="' + esc(url({ scope: "posko", id: p.id, jenis: "" })) + '">' + esc(p.title) + "</a>"; }).join("") + "</div>");
    }
    var items = d.items || [];
    html += card("Riwayat kegiatan", d.detail_hidden ? d.detail_hidden + " kegiatan organisasi tertutup hanya dihitung (rincian untuk anggotanya)." : "",
      items.length ? '<ul class="rk-tl">' + items.map(function (i) {
        var who = [i.posko_title, i.organisasi].filter(Boolean).join(" · ");
        return '<li><span class="rk-ic">' + (IC[i.jenis] || "•") + "</span><div><b>" + (i.href ? '<a href="' + esc(i.href) + (i.href.indexOf("?") > -1 ? "&" : "?") + "event=" + encodeURIComponent(cur) + '">' + esc(i.teks) + "</a>" : esc(i.teks)) +
          "</b><small>" + esc(i.waktu.replace("T", " ")) + (who ? " · " + esc(who) : "") + " · " + esc(i.label) + "</small></div></li>"; }).join("") + "</ul>"
        : '<p class="po-muted">Belum ada kegiatan tercatat' + (KIND ? " untuk jenis ini" : "") + ".</p>");
    $("rkBody").innerHTML = html;
    $("rkBody").querySelectorAll(".rk-chips [data-k]").forEach(function (b) { b.onclick = function () { location.href = url({ jenis: b.getAttribute("data-k") }); }; });
  }
  document.addEventListener("DOMContentLoaded", function () { if (window.RN_FRAPPE) load(); });
})();
