/* ============================================================
 * Alat Komunikasi dashboard — matches assets/img/mockup/alat komunikasi.png
 * Board: rescue_net.api_comms.comms_board (guest, event-wide).
 * Writes: api_comms.create_comms_device / create_comms_operator /
 * create_comms_frequency (login required).
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_comms.comms_board";
  var CACHE = null;
  var invTab = "semua";

  var $ = function (s, r) { return (r || document).querySelector(s); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
  function shortTime(s) { return s ? String(s).slice(11, 16) : ""; }
  function tsLabel(s) {
    if (!s) return "-";
    var t = String(s);
    return t.length > 10 ? t.slice(0, 16).replace("T", " ") : t;
  }

  /* ---------- KPI drill ---------- */
  var DRILL_TITLES = {
    alat_aktif: "Alat Komunikasi Aktif",
    posko_tidak_terhubung: "Posko Tidak Terhubung",
    repeater_aktif: "Repeater Aktif",
    internet_darurat: "Internet Darurat Dibutuhkan",
    operator_dibutuhkan: "Operator Radio Dibutuhkan",
    baterai_kritis: "Baterai Kritis",
  };
  var DRILL_KEY = {
    alat_aktif: "alat_aktif_items",
    posko_tidak_terhubung: "posko_tidak_terhubung_items",
    repeater_aktif: "repeater_aktif_items",
    internet_darurat: "internet_darurat_items",
    operator_dibutuhkan: "operator_dibutuhkan_items",
    baterai_kritis: "baterai_kritis_items",
  };

  function drillItemsHtml(items) {
    if (!items || !items.length) return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    return items.map(function (it) {
      return (
        '<a class="rn-ba-ditem" href="' + esc(it.href || "#") + '">' +
        "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
        (it.href ? '<span class="rn-ba-ditem-go">→</span>' : "") + "</a>"
      );
    }).join("");
  }

  function openDrill(kind) {
    if (!CACHE) return;
    var items = ((CACHE.kpi_items || {})[DRILL_KEY[kind]]) || [];
    $("#komDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    $("#komDrillSub").textContent = items.length + " item";
    $("#komDrillBody").innerHTML = drillItemsHtml(items);
    $("#komDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#komDrill").hidden = true; document.body.style.overflow = ""; }

  /* ---------- render ---------- */
  function renderKpi(t) {
    $("#kpiAlatAktif").textContent = fmt(t.alat_aktif);
    $("#kpiPoskoOffline").textContent = fmt(t.posko_tidak_terhubung);
    $("#kpiRepeater").textContent = fmt(t.repeater_aktif);
    $("#kpiInternet").textContent = fmt(t.internet_darurat_posko);
    $("#kpiOperatorNeed").textContent = fmt(t.operator_dibutuhkan);
    $("#kpiBateraiKritis").textContent = fmt(t.baterai_kritis);
  }

  function renderInventory() {
    if (!CACHE) return;
    var rows = CACHE.inventory || [];
    if (invTab === "perhatian") rows = rows.filter(function (r) { return r.perlu_perhatian > 0 || r.tidak_aktif > 0; });
    var body = $("#invBody");
    body.innerHTML = rows.length
      ? rows.map(function (r) {
          return (
            "<tr><td><b>" + esc(r.label) + "</b></td><td>" + fmt(r.total) + "</td>" +
            "<td>" + fmt(r.aktif) + "</td><td>" + fmt(r.cadangan) + "</td><td>" + fmt(r.tidak_aktif) + "</td>" +
            '<td>' + (r.perlu_perhatian > 0 ? '<span class="chip danger">' + fmt(r.perlu_perhatian) + "</span>" : "0") + "</td></tr>"
          );
        }).join("")
      : '<tr><td colspan="6"><em class="rn-muted">Belum ada alat komunikasi terdata untuk kategori ini.</em></td></tr>';

    var tot = CACHE.inventory_total || {};
    $("#invFoot").innerHTML = rows.length
      ? ("<tr><td><b>Total</b></td><td><b>" + fmt(tot.total) + "</b></td><td>" + fmt(tot.aktif) + "</td><td>" +
         fmt(tot.cadangan) + "</td><td>" + fmt(tot.tidak_aktif) + "</td><td>" + fmt(tot.perlu_perhatian) + "</td></tr>")
      : "";
  }

  function renderOperators(ops) {
    var el = $("#operatorList");
    if (!ops || !ops.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada operator radio terdata. Gunakan "+ Tambah Operator".</p>';
      return;
    }
    var chip = { online: "ok", siaga: "warning", istirahat: "", offline: "danger" };
    el.innerHTML = ops.map(function (o) {
      return (
        '<div class="rn-kom-op-row">' +
        "<span class=\"rn-kom-op-id\"><b>" + esc(o.name) + "</b><small>" + esc(o.role_label) +
        (o.posko && o.posko !== "-" ? " · " + esc(o.posko) : "") + "</small></span>" +
        '<span class="rn-kom-op-ch">' + esc(o.channel) + "</span>" +
        '<span class="chip ' + (chip[o.status] || "") + '">' + esc(o.status_label) + "</span>" +
        "</div>"
      );
    }).join("");
  }

  function renderConnectivity(k) {
    k = k || {};
    $("#connLegend").innerHTML =
      '<span class="rn-kom-conn-pill ok"><b>' + fmt(k.terhubung) + "</b> Terhubung</span>" +
      '<span class="rn-kom-conn-pill warn"><b>' + fmt(k.lemah) + "</b> Koneksi Lemah</span>" +
      '<span class="rn-kom-conn-pill bad"><b>' + fmt(k.tidak_terhubung) + "</b> Tidak Terhubung</span>" +
      (k.belum_terdata ? '<span class="rn-kom-conn-pill"><b>' + fmt(k.belum_terdata) + "</b> Belum Terdata</span>" : "");

    var body = $("#connBody");
    var rows = k.poskos || [];
    var chip = { connected: "ok", weak: "warning", disconnected: "danger", unknown: "" };
    body.innerHTML = rows.length
      ? rows.map(function (p) {
          return (
            '<tr class="rn-ba-row" data-href="' + esc(p.href) + '">' +
            "<td><b>" + esc(p.title) + "</b></td>" +
            '<td><span class="chip ' + (chip[p.status] || "") + '">' + esc(p.status_label) + "</span></td>" +
            "<td>" + esc(tsLabel(p.last_contact)) + "</td></tr>"
          );
        }).join("")
      : '<tr><td colspan="3"><em class="rn-muted">Belum ada posko untuk event ini.</em></td></tr>';
    body.querySelectorAll("tr[data-href]").forEach(function (tr) {
      tr.addEventListener("click", function () { window.location.href = tr.getAttribute("data-href"); });
    });
  }

  function renderBattery(rows) {
    var el = $("#battList");
    if (!rows || !rows.length) {
      el.innerHTML = '<p class="rn-muted">Tidak ada data baterai alat komunikasi.</p>';
      return;
    }
    var cls = { kritis: "bad", waspada: "warn", aman: "ok" };
    el.innerHTML = rows.slice(0, 10).map(function (b) {
      return (
        '<div class="rn-kom-batt-row">' +
        "<span class=\"rn-kom-batt-id\"><b>" + esc(b.label) + "</b><small>" + esc(b.category_label) + " · " + esc(b.posko) + "</small></span>" +
        '<span class="rn-kom-batt-bar"><i class="' + (cls[b.state] || "") + '" style="width:' + Math.max(4, b.battery_pct) + '%"></i></span>' +
        '<span class="rn-kom-batt-pct ' + (cls[b.state] || "") + '">' + fmt(b.battery_pct) + "%</span>" +
        "</div>"
      );
    }).join("");
  }

  function renderFrequency(rows) {
    var body = $("#freqBody");
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="3"><em class="rn-muted">Belum ada kanal frekuensi terdata.</em></td></tr>';
      return;
    }
    var chip = { baik: "ok", sibuk: "warning", lemah: "warning", down: "danger" };
    body.innerHTML = rows.map(function (f) {
      var right = f.status_label + (f.load_pct != null ? " " + f.load_pct + "%" : "");
      var meta = [f.frequency_value, f.provider].filter(Boolean).join(" · ") || f.network_label;
      return (
        "<tr><td><b>" + esc(f.band_label) + "</b><br><small class=\"rn-muted\">" + esc(f.network_label) + "</small></td>" +
        "<td>" + esc(meta) + "</td>" +
        '<td><span class="chip ' + (chip[f.status] || "") + '">' + esc(right) + "</span></td></tr>"
      );
    }).join("");
  }

  function renderAlerts(rows) {
    var el = $("#alertList");
    if (!rows || !rows.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Aman</h4><p>Tidak ada peringatan konektivitas saat ini.</p></div></div></article>';
      return;
    }
    el.innerHTML = rows.slice(0, 12).map(function (r) {
      var inner =
        '<div class="event-main"><div><h4>' + (r.level === "critical" ? "⚠ " : "") + esc(r.title) + "</h4>" +
        "<p>" + esc(r.sub) + (r.time ? ' · <span class="rn-muted">' + esc(tsLabel(r.time)) + "</span>" : "") + "</p></div>" +
        '<div class="chips"><span class="chip ' + (r.level === "critical" ? "danger" : "warning") + '">' + esc(r.tag) + "</span></div></div>";
      return r.href
        ? '<a class="event-card rn-sh-alert" href="' + esc(r.href) + '">' + inner + "</a>"
        : '<article class="event-card">' + inner + "</article>";
    }).join("");
  }

  /* ---------- forms ---------- */
  function wireDetailsButton(btnSel, detailsSel, focusName) {
    var btn = $(btnSel), det = $(detailsSel);
    if (!btn || !det) return;
    btn.addEventListener("click", function () {
      det.open = true;
      det.scrollIntoView({ behavior: "smooth", block: "center" });
      var f = det.querySelector('[name="' + focusName + '"]');
      if (f) setTimeout(function () { f.focus(); }, 300);
    });
  }

  function setupForm(sel, method, msgSel) {
    var form = $(sel);
    if (!form) return;
    var msg = $(msgSel);
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var payload = {};
      [].forEach.call(form.elements, function (el) {
        if (!el.name) return;
        var v = el.value == null ? "" : String(el.value).trim();
        if (v !== "") payload[el.name] = v;
      });
      if (!payload.disaster_event) payload.disaster_event = getEventId();
      if (msg) msg.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call(method, payload, { method: "POST" });
        if (msg) msg.textContent = "Tersimpan.";
        form.reset();
        await load();
      } catch (err) {
        var m = (err && err.message) || String(err);
        if (msg) msg.textContent = "Gagal: " + m + (/login|permission|akses|whitelist/i.test(m) ? " (perlu login)" : "");
      }
    });
  }

  /* ---------- load ---------- */
  async function load() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    CACHE = data;
    var t = shortTime(data.generated_at);
    $("#komUpdated").textContent = "Alat Komunikasi · Diperbarui " + (t || "-");
    $("#komStatus").textContent = "Dimuat pukul " + (t || "-");

    renderKpi(data.totals || {});
    renderInventory();
    renderOperators(data.operators || []);
    renderConnectivity(data.konektivitas || {});
    renderBattery(data.daya_baterai || []);
    renderFrequency(data.frekuensi || []);
    renderAlerts(data.peringatan || []);

    var ev = getEventId();
    var ml = $("#mapLink"); if (ml) ml.href = "map.html?event=" + encodeURIComponent(ev);
    $("#komFootnote").textContent = data.posko_field_backed
      ? "Konektivitas posko dari field status komunikasi posko."
      : "Konektivitas posko diturunkan dari status alat komunikasi tiap posko (field status khusus belum aktif).";
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) { console.error("RN_FRAPPE unavailable"); return; }

    document.querySelectorAll(".rn-kom-kpi .rn-kpi-btn").forEach(function (b) {
      b.addEventListener("click", function () { openDrill(b.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#komDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });

    document.querySelectorAll("#invTabs .rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll("#invTabs .rn-tab").forEach(function (x) { x.classList.remove("is-active"); });
        tab.classList.add("is-active");
        invTab = tab.getAttribute("data-inv");
        renderInventory();
      });
    });

    wireDetailsButton("#opAddBtn", "#operatorForm", "operator_name");

    setupForm("[data-create-device]", "rescue_net.api_comms.create_comms_device", "[data-device-message]");
    setupForm("[data-create-operator]", "rescue_net.api_comms.create_comms_operator", "[data-operator-message]");
    setupForm("[data-create-freq]", "rescue_net.api_comms.create_comms_frequency", "[data-freq-message]");

    load().catch(function (err) { console.error("[comms board]", err); $("#komStatus").textContent = "Gagal memuat: " + (err && err.message || err); });
  });
})();
