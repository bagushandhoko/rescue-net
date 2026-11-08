/* ============================================================
 * back-office.js — Ekosistem Penanganan (owner 2026-10-19).
 * One disaster from the support side: who helps (Pemerintah /
 * Organisasi / Masyarakat Umum / Program Donasi), what they bring,
 * and the gap to posko needs. Backend:
 * rescue_net.api_control_centre.ecosystem_board (guest, counts only).
 * Opened from the Control Centre header ("Ekosistem Penanganan").
 * ============================================================ */
(function () {
  "use strict";

  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return window.RNUI.esc(s); };
  var fmt = function (n) { return window.RNUI.fmt(Math.round(Number(n || 0) * 100) / 100); };
  var rp = function (n) { return "Rp " + window.RNUI.fmt(Math.round(Number(n || 0))); };
  // short money for KPI cards / group cards (a full "Rp 262.000.000" overflows a phone card)
  var rpShort = function (n) {
    n = Number(n || 0);
    if (n >= 1e12) return "Rp " + fmt(n / 1e12) + " T";
    if (n >= 1e9) return "Rp " + fmt(Math.round(n / 1e7) / 100) + " M";
    if (n >= 1e6) return "Rp " + fmt(Math.round(n / 1e4) / 100) + " jt";
    return rp(n);
  };
  var GROUP_LABEL = { pemerintah: "Pemerintah", organisasi: "Organisasi Masyarakat & Lembaga",
                      masyarakat: "Masyarakat Umum", program: "Program Donasi" };
  var TYPE_LABEL = { government: "Pemerintah", community: "Komunitas", ngo: "LSM / NGO", academic: "Kampus",
                     media: "Media", private_sector: "Swasta" };
  var STATUS_LABEL = { planned: "Direncanakan", active: "Berjalan", completed: "Selesai", cancelled: "Batal" };
  var DATA = null;
  var FILTER = "semua";

  function eventId() {
    var q = new URLSearchParams(location.search).get("event");
    if (!q) { try { q = localStorage.getItem("rn_active_event"); } catch (e) {} }
    return String(q || "").replace(/^disaster_events:/, "");
  }

  // owner 2026-11-09: klik → pindah ke halaman (dengan tombol kembali), bukan isi berubah di bawah
  function orgHref(o) {
    var m = /[?&](?:org|id)=([^&]+)/.exec(o.href || ""); var id = (m && decodeURIComponent(m[1])) || o.id || o.name || "";
    return "profil-organisasi.html?id=" + encodeURIComponent(id) + (eventId() ? "&event=" + encodeURIComponent(eventId()) : "");
  }
  function orgId(o) { var m = /[?&](?:org|id)=([^&]+)/.exec(o.href || ""); return (m && decodeURIComponent(m[1])) || o.id || o.name || ""; }
  function progHref(p) {
    var m = /[?&](?:id|program)=([^&]+)/.exec(p.href || ""); var id = (m && decodeURIComponent(m[1])) || p.id || p.name || "";
    return "program-khusus.html?program=" + encodeURIComponent(id) + (eventId() ? "&event=" + encodeURIComponent(eventId()) : "");
  }
  function flash(el) {
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    el.classList.remove("rn-flash"); void el.offsetWidth; el.classList.add("rn-flash");
  }
  async function setupTopNav() {
    var back = $("#boBack");
    if (back) back.onclick = function () {
      if (document.referrer && document.referrer.indexOf(location.host) > -1 && history.length > 1) history.back();
      else location.href = "war-room.html" + (eventId() ? "?event=" + encodeURIComponent(eventId()) : "");
    };
    var sel = $("#boEventSel"); if (!sel) return;
    var evs = [];
    try { evs = await window.RN_FRAPPE.call("rescue_net.api_ai.public_active_disasters", {}); } catch (e) {}
    evs = Array.isArray(evs) ? evs : [];
    var cur = eventId();
    var known = function (id) { return evs.some(function (e) { return (e.id || e.name) === id; }); };
    if (evs.length && (!cur || !known(cur))) {
      cur = evs[0].id || evs[0].name;
      var u = new URL(location.href); u.searchParams.set("event", cur); history.replaceState(null, "", u.toString());
    }
    sel.innerHTML = evs.map(function (e) { var id = e.id || e.name; return '<option value="' + esc(id) + '"' + (id === cur ? " selected" : "") + ">" + esc(e.title || id) + "</option>"; }).join("") ||
      '<option value="">Tidak ada bencana aktif</option>';
    sel.onchange = function () {
      try { localStorage.setItem("rn_active_event", sel.value); } catch (e) {}
      var u = new URL(location.href); u.searchParams.set("event", sel.value); location.href = u.toString();
    };
  }

  var IC = { kirim: "🚚", terima: "📦", dapur: "🍲", medis: "🩺", shelter: "🏠", stok: "📋", bukti: "📷", relawan: "🙋", laporan: "📣", sar: "🔎", donasi: "💚", realisasi: "🧾" };
  async function renderPerf() {
    var box = $("#boPerf"); if (!box) return;
    var ev = eventId(), q = ev ? "&event=" + encodeURIComponent(ev) : "";
    var ops = $("#boOpsLink"); if (ops) ops.href = "war-room.html" + (ev ? "?event=" + encodeURIComponent(ev) : "");
    var d;
    try { d = await window.RN_FRAPPE.call("rescue_net.api_org_profile.ecosystem_performance", { disaster_event: ev }); }
    catch (e) { box.innerHTML = '<p class="rn-muted">Gagal memuat kinerja.</p>'; return; }
    var rows = d.pihak || [];
    var kk = $("#kKeg"); if (kk) kk.textContent = fmt(rows.reduce(function (s, r) { return s + (r.kegiatan || 0); }, 0));
    box.innerHTML = rows.length ? rows.map(function (r) {
      var prof = r.masyarakat ? "kegiatan-masyarakat.html?" + q.slice(1) : "profil-organisasi.html?id=" + encodeURIComponent(r.id) + q;
      var hist = "riwayat-kegiatan.html?scope=" + (r.masyarakat ? "masyarakat" : "organisasi&id=" + encodeURIComponent(r.id)) + q;
      var kir = (r.per_jenis || []).filter(function (x) { return x.jenis === "kirim" || x.jenis === "terima"; }).reduce(function (s, x) { return s + x.n; }, 0);
      var m = [[r.kegiatan, "kegiatan"], [r.posko, "posko"], [kir, "kiriman"]];
      if (r.porsi) m.push([fmt(r.porsi), "porsi"]); if (r.pasien) m.push([r.pasien, "pasien"]);
      if (r.dana) m.push([rpShort(r.dana), "donasi"]); if (r.realisasi) m.push([rpShort(r.realisasi), "realisasi"]);
      return '<article class="bo-pc"><h4><a href="' + esc(prof) + '">' + esc(r.title) + "</a></h4>" +
        '<div class="sub">' + (r.masyarakat ? "Warga, relawan & donatur perorangan" : (r.open ? "Organisasi terbuka" : "Organisasi tertutup — angka saja") + (r.verified ? " · ✔ terverifikasi" : "")) +
        ((r.anak || []).length ? "<br>termasuk " + r.anak.map(esc).join(", ") : "") + "</div>" +
        '<div class="bo-pm">' + m.map(function (x) { return "<div><b>" + (typeof x[0] === "number" ? fmt(x[0]) : esc(x[0])) + "</b><span>" + x[1] + "</span></div>"; }).join("") + "</div>" +
        '<div class="bo-pj">' + (r.per_jenis || []).slice(0, 6).map(function (x) { return "<span>" + (IC[x.jenis] || "") + " " + esc(x.label) + " " + fmt(x.n) + "</span>"; }).join("") + "</div>" +
        '<div class="sub">' + (r.terakhir ? "Terakhir aktif " + esc(r.terakhir.replace("T", " ")) : "Belum ada kegiatan tercatat") + "</div>" +
        '<div class="bo-pa"><a class="btn mini primary" href="' + esc(hist) + '">Riwayat & kinerja →</a><a class="btn mini" href="' + esc(prof) + '">' + (r.masyarakat ? "Ringkasan" : "Profil") + "</a></div></article>";
    }).join("") : '<p class="rn-muted">Belum ada pihak yang tercatat pada bencana ini.</p>';
  }

  function bar(pct) {
    if (pct === null || pct === undefined) return '<span class="rn-muted">—</span>';
    var p = Math.max(0, Math.min(100, Number(pct)));
    var tone = p < 40 ? " low" : p < 80 ? " mid" : "";
    return '<div class="rn-bo-bar' + tone + '"><span style="width:' + p + '%"></span></div><span class="rn-bo-pct">' + fmt(p) + "%</span>";
  }

  function renderKpi(t) {
    $("#kPihak").textContent = fmt(t.pihak);
    $("#kPosko").textContent = fmt(t.posko);
    $("#kPoskoSub").textContent = fmt(t.jiwa_dilayani) + " jiwa dilayani";
    $("#kRelawan").textContent = fmt(t.relawan);
    $("#kRelawanSub").textContent = fmt(t.relawan_siaga) + " siaga";
    $("#kGap").textContent = fmt(t.kebutuhan_gap);
    $("#kGapSub").textContent = "dari " + fmt(t.kebutuhan_terbuka) + " jenis barang dibutuhkan";
    $("#kAlat").textContent = fmt(t.peralatan);
    $("#kDana").textContent = rpShort(t.dana_terkumpul);
    $("#kDana").title = rp(t.dana_terkumpul);
    $("#kDanaSub").textContent = fmt(t.program) + " program donasi";
  }

  function renderGroups(groups) {
    var el = $("#boGroups");
    el.innerHTML = groups.map(function (g) {
      var rows = g.key === "program"
        ? [["Program", g.program], ["Dana terkumpul", rpShort(g.dana_terkumpul)]]
        : [[g.key === "masyarakat" ? "Perorangan" : "Organisasi", g.key === "masyarakat" ? "—" : g.orgs],
           ["Posko", g.posko], ["Relawan", g.relawan],
           ["Sumbangan barang", g.sumbangan + (g.sumbangan_diterima ? " (" + g.sumbangan_diterima + " diterima)" : "")],
           ["Peralatan", g.peralatan]];
      return '<button type="button" class="rn-bo-group" data-group="' + esc(g.key) + '"><h4>' + esc(g.label) + "</h4><dl>" +
        rows.map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + esc(typeof r[1] === "number" ? fmt(r[1]) : r[1]) + "</dd>"; }).join("") +
        "</dl></button>";
    }).join("");
    el.querySelectorAll("[data-group]").forEach(function (b) {
      b.addEventListener("click", function () {
        var g = b.getAttribute("data-group");
        if (g === "program") { flash($("#boProgPanel")); return; }
        if (g === "masyarakat") { location.href = "kegiatan-masyarakat.html?event=" + encodeURIComponent(eventId()); return; }
        setFilter(g);
        flash($("#boOrgPanel"));
      });
    });
  }

  function setFilter(g) {
    FILTER = g;
    document.querySelectorAll("#boOrgTabs button").forEach(function (b) {
      b.setAttribute("aria-selected", b.getAttribute("data-f") === g ? "true" : "false");
    });
    document.querySelectorAll(".rn-bo-group").forEach(function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-group") === g);
    });
    renderOrgs();
  }

  function renderTabs() {
    var tabs = [["semua", "Semua"], ["pemerintah", "Pemerintah"], ["organisasi", "Organisasi"], ["masyarakat", "Masyarakat Umum"]];
    $("#boOrgTabs").innerHTML = tabs.map(function (t) {
      return '<button type="button" role="tab" data-f="' + t[0] + '" aria-selected="' + (t[0] === FILTER) + '">' + t[1] + "</button>";
    }).join("");
    document.querySelectorAll("#boOrgTabs button").forEach(function (b) {
      b.addEventListener("click", function () { setFilter(b.getAttribute("data-f")); });
    });
  }

  function renderOrgs() {
    var body = $("#boOrgBody");
    var ev = encodeURIComponent(eventId());
    if (FILTER === "masyarakat") {
      var m = (DATA.groups || []).filter(function (g) { return g.key === "masyarakat"; })[0] || {};
      body.innerHTML = '<tr><td><a href="kegiatan-masyarakat.html?event=' + ev + '"><b>Masyarakat umum (perorangan)</b></a><span class="rn-bo-pct">tanpa organisasi — klik untuk melihat kegiatannya</span></td><td>Masyarakat Umum</td>' +
        '<td class="num">' + fmt(m.posko) + '</td><td class="num">' + fmt(m.relawan) + '</td><td class="num">' + fmt(m.sumbangan) +
        '</td><td class="num">' + fmt(m.peralatan) + '</td><td class="num">—</td><td class="num">—</td></tr>';
      return;
    }
    var rows = (DATA.orgs || []).filter(function (o) { return FILTER === "semua" || o.group === FILTER; });
    if (!rows.length) { body.innerHTML = '<tr><td colspan="8">Belum ada pihak di kelompok ini.</td></tr>'; return; }
    body.innerHTML = rows.map(function (o) {
      var type = TYPE_LABEL[o.organization_type] || "Lainnya";
      return "<tr>" +
        '<td><a href="' + esc(orgHref(o)) + '">' + esc(o.title) + "</a>" +
          (o.posko ? '<span class="rn-bo-pct">' + fmt(o.posko_aktif) + " posko aktif</span>" : "") +
          ((o.anak || []).length ? '<span class="rn-bo-pct">termasuk ' + o.anak.map(function (a) { return esc(a.title); }).join(", ") + "</span>" : "") +
          '<span class="rn-bo-pct"><a href="riwayat-kegiatan.html?scope=organisasi&id=' + encodeURIComponent(orgId(o)) + (eventId() ? "&event=" + encodeURIComponent(eventId()) : "") + '">Riwayat kegiatan →</a></span>' +
          "</td>" +
        "<td>" + esc(GROUP_LABEL[o.group] || o.group) + '<span class="rn-bo-pct">' + esc(type) + "</span></td>" +
        '<td class="num">' + fmt(o.posko) + '</td><td class="num">' + fmt(o.relawan) + '</td>' +
        '<td class="num">' + fmt(o.sumbangan) + '</td><td class="num">' + fmt(o.peralatan) + '</td>' +
        '<td class="num">' + fmt(o.program) + '</td><td class="num">' + (o.dana_terkumpul ? fmt(o.dana_terkumpul) : "—") + "</td>" +
        "</tr>";
    }).join("");
  }

  function renderNeeds(rows) {
    $("#boNeedCount").textContent = fmt(rows.filter(function (r) { return r.gap > 0; }).length) + " masih kurang";
    $("#boNeedBody").innerHTML = rows.length ? rows.map(function (r) {
      var u = r.unit ? " " + esc(r.unit) : "";
      return "<tr>" +
        "<td><b>" + esc(r.item) + "</b>" + (r.kritis ? ' <span class="chip danger">kritis</span>' : "") +
          '<span class="rn-bo-pct">' + fmt(r.posko) + " permintaan posko</span></td>" +
        '<td class="num">' + fmt(r.dibutuhkan) + u + '</td><td class="num">' + fmt(r.terpenuhi) + u +
        '</td><td class="num">' + fmt(r.menuju) + u + '</td>' +
        '<td class="num' + (r.gap > 0 ? " gap-pos" : "") + '">' + fmt(r.gap) + u + "</td>" +
        "<td>" + bar(r.percent) + "</td></tr>";
    }).join("") : '<tr><td colspan="6">Tidak ada kebutuhan terbuka di posko bencana ini.</td></tr>';
  }

  function renderTools(rows) {
    $("#boToolBody").innerHTML = rows.length ? rows.map(function (t) {
      return "<tr><td>" + esc(String(t.category).replace(/_/g, " ")) + '</td><td class="num">' + fmt(t.tersedia) +
        '</td><td class="num">' + fmt(t.diminta) + '</td><td class="num">' + fmt(t.dikerahkan) +
        '</td><td class="num' + (t.gap > 0 ? " gap-pos" : "") + '">' + fmt(t.gap) + "</td></tr>";
    }).join("") : '<tr><td colspan="5">Belum ada peralatan atau permintaan alat untuk bencana ini.</td></tr>';
  }

  function renderSkills(rows) {
    $("#boSkills").innerHTML = rows.length ? rows.map(function (s) {
      return '<span class="chip">' + esc(s.skill) + " · " + fmt(s.count) + "</span>";
    }).join("") : '<p class="rn-muted">Belum ada relawan terdaftar untuk bencana ini.</p>';
  }

  function renderPrograms(rows) {
    var ev = encodeURIComponent(eventId());
    $("#boProgBody").innerHTML = rows.length ? rows.map(function (p) {
      return '<tr><td><a href="' + esc(progHref(p)) + '">' + esc(p.title) + "</a></td>" +
        "<td>" + esc(p.owner) + "</td><td>" + esc(STATUS_LABEL[p.status] || p.status || "-") + "</td>" +
        '<td class="num">' + fmt(p.target) + '</td><td class="num">' + fmt(p.received) + "</td>" +
        '<td class="num' + (p.gap > 0 ? " gap-pos" : "") + '">' + fmt(p.gap) + "</td><td>" + bar(p.percent) + "</td></tr>";
    }).join("") : '<tr><td colspan="7">Belum ada program donasi untuk bencana ini.</td></tr>';
  }

  async function load() {
    var ev = eventId();
    document.querySelectorAll("[data-bo-event]").forEach(function (a) {
      var u = new URL(a.getAttribute("href"), location.href);
      u.searchParams.set("event", ev);
      a.setAttribute("href", u.pathname.split("/").pop() + u.search);
    });
    $("#boBackLink").setAttribute("href", "war-room.html?event=" + encodeURIComponent(ev));
    var rw = $("#boRiwayat"); if (rw) rw.setAttribute("href", "riwayat-kegiatan.html?scope=all&event=" + encodeURIComponent(ev));
    try {
      DATA = await window.RN_FRAPPE.call("rescue_net.api_control_centre.ecosystem_board", { disaster_event: ev });
    } catch (err) {
      $("#boStatus").textContent = "Gagal memuat: " + ((err && err.message) || err);
      return;
    }
    $("#boTitle").textContent = "Ekosistem Penanganan — " + (DATA.event_title || ev);
    $("#boStatus").textContent = "Diperbarui " + window.RNUI.fmtTime(DATA.generated_at);
    renderKpi(DATA.totals || {});
    renderGroups(DATA.groups || []);
    renderTabs();
    renderOrgs();
    renderNeeds(DATA.needs || []);
    renderTools(DATA.tools || []);
    renderSkills(DATA.relawan_keahlian || []);
    renderPrograms(DATA.programs || []);
    renderPerf();
  }

  // owner 2026-11-09: "tidak harus seluruhnya yang tampil" — pilih bagian yang ditampilkan (diingat di alamat & browser)
  function setupShow() {
    var box = $("#boShow"); if (!box) return;
    var q = new URLSearchParams(location.search).get("tampil");
    var cur = q || (function () { try { return localStorage.getItem("rn-bo-tampil") || "semua"; } catch (e) { return "semua"; } })();
    function apply(k) {
      box.querySelectorAll("button[data-s]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-s") === k); });
      document.querySelectorAll("[data-bo-sec]").forEach(function (el) { var s = el.getAttribute("data-bo-sec"); el.hidden = s === "operasional" || (k !== "semua" && s !== k); });
      var grid = document.querySelector("#boToolPanel") && document.querySelector("#boToolPanel").parentElement;
      if (grid) grid.hidden = k !== "semua" && k !== "relawan";
      try { localStorage.setItem("rn-bo-tampil", k); } catch (e) {}
      var u = new URL(location.href); if (k === "semua") u.searchParams.delete("tampil"); else u.searchParams.set("tampil", k); history.replaceState(null, "", u.toString());
    }
    box.querySelectorAll("button[data-s]").forEach(function (b) { b.addEventListener("click", function () { apply(b.getAttribute("data-s")); }); });
    apply(cur);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    setupShow();
    setupTopNav().then(load);
  });
})();
