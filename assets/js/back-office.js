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
    return String(q || "event-sim-001").replace(/^disaster_events:/, "");
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
        if (g === "program") { $("#boProgPanel").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
        setFilter(g);
        $("#boOrgPanel").scrollIntoView({ behavior: "smooth", block: "start" });
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
      body.innerHTML = '<tr><td><b>Masyarakat umum (perorangan)</b><span class="rn-bo-pct">tanpa organisasi</span></td><td>Masyarakat Umum</td>' +
        '<td class="num">' + fmt(m.posko) + '</td><td class="num">' + fmt(m.relawan) + '</td><td class="num">' + fmt(m.sumbangan) +
        '</td><td class="num">' + fmt(m.peralatan) + '</td><td class="num">—</td><td class="num">—</td></tr>';
      return;
    }
    var rows = (DATA.orgs || []).filter(function (o) { return FILTER === "semua" || o.group === FILTER; });
    if (!rows.length) { body.innerHTML = '<tr><td colspan="8">Belum ada pihak di kelompok ini.</td></tr>'; return; }
    body.innerHTML = rows.map(function (o) {
      var type = TYPE_LABEL[o.organization_type] || "Lainnya";
      return "<tr>" +
        '<td><a href="' + esc(o.href) + "&event=" + ev + '">' + esc(o.title) + "</a>" +
          (o.posko ? '<span class="rn-bo-pct">' + fmt(o.posko_aktif) + " posko aktif</span>" : "") + "</td>" +
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
      return '<tr><td><a href="' + esc(p.href) + "&event=" + ev + '">' + esc(p.title) + "</a></td>" +
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
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    load();
  });
})();
