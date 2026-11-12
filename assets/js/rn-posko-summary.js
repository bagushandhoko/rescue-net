/* ============================================================
 * rn-posko-summary.js — "Semua posko" lebih dulu, baru satu posko (owner 2026-11-09 malam).
 *
 * Halaman posko (logistik, distribusi, medis, shelter, dapur) dibuka TANPA ?id= -> tampil ringkasan
 * semua posko jenis itu di bencana terpilih, satu baris per posko. Klik baris -> halaman yang sama
 * dengan ?id=<posko> (tampilan satu posko seperti sebelumnya) + tombol "← Semua posko".
 *
 * Pemakaian: <body data-rn-posko-kind="logistik"> dan muat skrip ini SEBELUM rn-posko-scope.js
 * (supaya anggota organisasi tidak langsung dialihkan ke poskonya sendiri).
 * Data: rescue_net.api_control_centre.posko_summary(disaster_event, kind).
 * ============================================================ */
(function () {
  "use strict";

  var kind = document.body && document.body.getAttribute("data-rn-posko-kind");
  if (!kind) return;
  var qs = new URLSearchParams(location.search);
  var poskoId = qs.get("id") || qs.get("posko") || "";
  var summaryMode = !poskoId;
  window.RN_POSKO_SUMMARY_MODE = summaryMode;
  // Skrip halaman lama memilih posko pertama dan menulis ?id= ke alamat; di mode ringkasan itu diabaikan
  // supaya muat ulang tetap menampilkan daftar semua posko.
  if (summaryMode && window.history && history.replaceState) {
    var origReplace = history.replaceState;
    history.replaceState = function (st, t, url) {
      try { var u = new URL(url, location.href); if (u.searchParams.get("id") || u.searchParams.get("posko")) return; } catch (e) {}
      return origReplace.apply(history, arguments);
    };
  }

  var LABEL = {
    logistik: "Posko Logistik", distribusi: "Posko Distribusi", medis: "Posko Medis",
    shelter: "Posko Shelter", dapur: "Posko Dapur Umum"
  };

  function currentEvent() {
    var ev = qs.get("event") || qs.get("disaster_event_id");
    if (!ev) { try { ev = localStorage.getItem("rn_active_event"); } catch (e) {} }
    return String(ev || "event-sim-001").replace(/^disaster_events:/, "");
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) {
    if (n == null || n === "") return "–";
    var x = Number(n);
    return isFinite(x) ? x.toLocaleString("id-ID", { maximumFractionDigits: 1 }) : esc(n);
  }
  function listUrl() {
    var u = new URL(location.href);
    u.searchParams.delete("id"); u.searchParams.delete("posko");
    u.searchParams.set("event", currentEvent());
    return u.pathname + u.search;
  }
  function detailUrl(id) {
    var u = new URL(location.href);
    u.searchParams.delete("posko");
    u.searchParams.set("id", id);
    u.searchParams.set("event", currentEvent());
    return u.pathname + u.search;
  }
  function ago(ts) {
    if (!ts) return "–";
    var d = new Date(String(ts).replace(" ", "T"));
    if (isNaN(d)) return "–";
    var m = Math.round((Date.now() - d.getTime()) / 60000);
    if (m < 1) return "baru saja";
    if (m < 60) return m + " mnt lalu";
    var h = Math.round(m / 60);
    if (h < 24) return h + " jam lalu";
    var dd = Math.round(h / 24);
    return dd + " hari lalu";
  }
  function situ(s) {
    if (s === "critical") return '<span class="rn-ps-chip is-crit">Kritis</span>';
    if (s === "warning") return '<span class="rn-ps-chip is-warn">Waspada</span>';
    return '<span class="rn-ps-chip is-ok">Aman</span>';
  }
  // owner 2026-11-12: alasan Kritis/Waspada tampil di bawah status (mis. "Status diisi petugas posko: Kritis").
  function why(list) {
    if (!list || !list.length) return "";
    return '<small class="rn-ps-why" style="display:block;margin-top:4px;color:#6b5a4c;font-size:12px;line-height:1.35;max-width:220px">' +
      list.map(function (x) { return String(x).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }).join("<br>") + "</small>";
  }
  function bar(pct) {
    if (pct == null) return "–";
    var p = Math.max(0, Math.min(100, Number(pct)));
    var cls = p >= 90 ? "is-crit" : (p >= 70 ? "is-warn" : "is-ok");
    return '<span class="rn-ps-bar ' + cls + '"><i style="width:' + p + '%"></i></span> ' + fmt(pct) + "%";
  }
  function warnNum(n) {
    return n ? '<b class="rn-ps-red">' + fmt(n) + "</b>" : fmt(n);
  }

  /* kolom angka per jenis posko: [judul, fungsi(metrics) -> html] */
  var COLS = {
    logistik: [
      ["Peran", function (m) { return esc(m.peran || "–"); }],
      ["Jenis stok", function (m) { return fmt(m.stok_item); }],
      ["Stok menipis", function (m) { return warnNum(m.stok_menipis); }],
      ["Kebutuhan terbuka", function (m) { return fmt(m.kebutuhan_terbuka) + (m.kebutuhan_kritis ? ' <small class="rn-ps-red">(' + fmt(m.kebutuhan_kritis) + " kritis)</small>" : ""); }],
      ["Bantuan menuju", function (m) { return fmt(m.bantuan_menuju); }],
      ["Jiwa dilayani", function (m) { return fmt(m.jiwa_dilayani); }]
    ],
    distribusi: [
      ["Armada aktif", function (m) { return fmt(m.armada_aktif) + ' <small class="rn-muted">/ ' + fmt(m.armada) + "</small>"; }],
      ["Kapasitas", function (m) { return m.kapasitas_kg ? fmt(m.kapasitas_kg) + " kg" : "–"; }],
      ["Sisa ruang", function (m) { return m.kapasitas_kg ? fmt(m.tersedia_kg) + " kg" : "–"; }],
      ["Terpakai", function (m) { return bar(m.terpakai_pct); }],
      ["Booking", function (m) { return fmt(m.booking_menunggu) + ' antre · ' + fmt(m.booking_terkonfirmasi) + " ok"; }]
    ],
    medis: [
      ["Pasien ditangani", function (m) { return m.pasien_aktif == null ? '<small class="rn-muted">khusus petugas</small>' : fmt(m.pasien_aktif); }],
      ["Triase merah", function (m) { return m.pasien_merah == null ? "–" : warnNum(m.pasien_merah); }],
      ["Kebutuhan terbuka", function (m) { return fmt(m.kebutuhan_terbuka); }],
      ["Jenis stok", function (m) { return fmt(m.stok_item); }]
    ],
    shelter: [
      ["Penghuni", function (m) { return fmt(m.penghuni) + ' <small class="rn-muted">/ ' + fmt(m.kapasitas) + "</small>"; }],
      ["Okupansi", function (m) { return bar(m.okupansi_pct); }],
      ["Kelompok rentan", function (m) { return fmt(m.kelompok_rentan); }],
      ["Kebutuhan kritis", function (m) { return warnNum(m.kebutuhan_kritis); }]
    ],
    dapur: [
      ["Jiwa dilayani", function (m) { return fmt(m.jiwa_dilayani); }],
      ["Porsi hari ini", function (m) { return fmt(m.produksi_hari_ini) + ' <small class="rn-muted">/ ' + fmt(m.kapasitas_porsi_hari) + "</small>"; }],
      ["Dibagikan hari ini", function (m) { return fmt(m.distribusi_hari_ini); }],
      ["Kurang porsi", function (m) { return warnNum(m.gap_porsi); }],
      ["Bahan kritis", function (m) { return warnNum(m.bahan_kritis); }]
    ]
  };

  function rowHtml(r, cols) {
    var m = r.metrics || {};
    var tags = (r.mine ? '<span class="rn-ps-chip is-mine">Posko saya</span>' : "") +
      (r.public_participation ? '<span class="rn-ps-chip is-open">Terbuka</span>' : "") +
      (r.detail_allowed ? "" : '<span class="rn-ps-chip is-sum" title="Organisasi menutup detail; angka ringkasan saja">Ringkasan</span>');
    return '<tr data-href="' + esc(detailUrl(r.posko)) + '" tabindex="0">' +
      '<td class="rn-ps-name"><a href="' + esc(detailUrl(r.posko)) + '">' + esc(String(r.title || r.posko).replace(/^\[SIMULASI\]\s*/i, "")) + "</a>" +
      '<small>' + esc(r.organization || "") + (r.lokasi ? " · " + esc(r.lokasi) : "") + "</small>" +
      (tags ? '<span class="rn-ps-tags">' + tags + "</span>" : "") + "</td>" +
      '<td data-l="Kondisi">' + situ(r.situation) + why(r.situation_reasons) + "</td>" +
      cols.map(function (c) { return '<td data-l="' + esc(c[0]) + '">' + c[1](m) + "</td>"; }).join("") +
      '<td data-l="Update" class="rn-ps-time">' + esc(ago(r.last_update)) + "</td></tr>";
  }

  function render(panel, data) {
    var cols = COLS[kind] || [];
    var rows = data.rows || [];
    var crit = rows.filter(function (r) { return r.situation === "critical"; }).length;
    var mine = rows.filter(function (r) { return r.mine; }).length;
    var body = panel.querySelector(".rn-ps-body");
    panel.querySelector(".rn-ps-count").innerHTML =
      "<b>" + rows.length + "</b> posko" + (crit ? ' · <b class="rn-ps-red">' + crit + "</b> kritis" : "") +
      (mine ? " · <b>" + mine + "</b> posko saya" : "");
    if (!rows.length) {
      body.innerHTML = '<p class="rn-muted rn-ps-empty">Belum ada ' + esc(LABEL[kind] || "posko") +
        " di bencana ini. Pilih bencana lain di menu samping, atau daftarkan posko lewat Registrasi Posko.</p>";
      return;
    }
    body.innerHTML = '<div class="rn-ps-scroll"><table class="rn-ps-table"><thead><tr><th>Posko</th><th>Kondisi</th>' +
      cols.map(function (c) { return "<th>" + esc(c[0]) + "</th>"; }).join("") + "<th>Update</th></tr></thead><tbody>" +
      rows.map(function (r) { return rowHtml(r, cols); }).join("") + "</tbody></table></div>";
    var input = panel.querySelector(".rn-ps-search");
    input.hidden = rows.length < 6;
    input.oninput = function () {
      var q = input.value.trim().toLowerCase();
      body.querySelectorAll("tbody tr").forEach(function (tr) {
        tr.hidden = q && tr.textContent.toLowerCase().indexOf(q) < 0;
      });
    };
    body.querySelectorAll("tbody tr").forEach(function (tr) {
      function go(e) { if (e.target.closest("a")) return; location.href = tr.getAttribute("data-href"); }
      tr.addEventListener("click", go);
      tr.addEventListener("keydown", function (e) { if (e.key === "Enter") go(e); });
    });
  }

  function load(panel) {
    var body = panel.querySelector(".rn-ps-body");
    body.innerHTML = '<p class="rn-muted rn-ps-empty">Memuat daftar posko…</p>';
    var url = "/rescue-net-frappe/api/method/rescue_net.api_control_centre.posko_summary?disaster_event=" +
      encodeURIComponent(currentEvent()) + "&kind=" + encodeURIComponent(kind);
    fetch(url, { credentials: "include" })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error((j && j._server_messages) || r.status); return j; }); })
      .then(function (j) { render(panel, j.message || {}); })
      .catch(function () { body.innerHTML = '<p class="rn-muted rn-ps-empty">Gagal memuat daftar posko. <a href="' + esc(listUrl()) + '">Coba lagi</a></p>'; });
  }

  function mountSummary() {
    var main = document.querySelector("main.main, .main, main");
    if (!main) return;
    main.classList.add("rn-ps-mode");
    var panel = document.createElement("section");
    panel.className = "rn-ps-panel";
    panel.innerHTML =
      '<div class="rn-ps-head"><div><p class="rn-ps-eyebrow">Semua posko di bencana ini</p>' +
      "<h1>" + esc(LABEL[kind] || "Posko") + "</h1>" +
      '<p class="rn-ps-count rn-muted">…</p></div>' +
      '<input class="rn-ps-search" type="search" placeholder="Cari posko / lokasi / organisasi" hidden></div>' +
      '<p class="rn-muted rn-ps-hint">Klik nama posko untuk melihat rinciannya, mengirim bantuan, atau melapor. Pengelola posko mencatat data di halaman poskonya sendiri.</p>' +
      '<div class="rn-ps-body"></div>';
    main.insertBefore(panel, main.firstChild);
    // sembunyikan isi satu-posko (juga di HP, di mana aturan topbar memakai !important)
    Array.prototype.forEach.call(main.children, function (el) {
      if (el !== panel) el.style.setProperty("display", "none", "important");
    });
    load(panel);
  }

  function mountBack() {
    var main = document.querySelector("main.main, .main, main");
    if (!main || main.querySelector(".rn-ps-back")) return;
    var a = document.createElement("a");
    a.className = "rn-ps-back";
    a.href = listUrl();
    a.textContent = "← Semua " + (LABEL[kind] || "posko");
    main.insertBefore(a, main.firstChild);
  }

  function start() { if (summaryMode) mountSummary(); else mountBack(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
