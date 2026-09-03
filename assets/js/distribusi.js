/* ============================================================
 * New dashboard (matches manajemen distribusi.png): calls
 * rescue_net.api_control_centre.distribusi_board (guest, event-wide)
 * + auto_match_distribution (login required, real write action).
 * Legacy per-posko panels below (Bantuan Perlu Pickup/Transport
 * Space/Distribution Flow + both forms) keep calling
 * api_logistics.dashboard / create_transport_space / create_flow.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_control_centre.distribusi_board";
  var BOARD_CACHE = null;
  var activeTransportTab = "darat";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }

  function statusPillClass(status) {
    var l = String(status || "").toLowerCase();
    if (l === "in_transit" || l === "dispatched" || l === "assigned_pickup") return "warning";
    if (l === "arrived" || l === "received" || l === "received_verified" || l === "stock_transferred") return "ok";
    if (l === "cancelled") return "danger";
    return "";
  }

  /* ---------- KPI drill ---------- */

  var DRILL_TITLES = {
    transport: "Transport Space — Utilisasi Keseluruhan",
    darat: "Kapasitas Darat", laut: "Kapasitas Laut", udara: "Kapasitas Udara",
    kebutuhan: "Kebutuhan Belum Match", terhambat: "Distribusi Terhambat",
  };

  function capInfoHtml(bucket, label) {
    return (
      '<div class="rn-dp-target rn-dp-target-modal">' +
      "<div><span>Tersedia</span><b>" + fmt(bucket.tersedia_m3) + "</b><small>m³</small></div>" +
      "<div><span>Terpakai</span><b>" + fmt(bucket.terpakai_m3) + "</b><small>m³</small></div>" +
      "<div><span>Total</span><b>" + fmt(bucket.total_m3) + "</b><small>m³ · " + bucket.pct + "%</small></div>" +
      "</div>"
    );
  }

  function drillItemsHtml(items) {
    if (!items || !items.length) return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    return items.map(function (it) {
      return (
        '<a class="rn-ba-ditem" href="' + esc(it.href || "#") + '">' +
        "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
        '<span class="rn-ba-ditem-go">→</span></a>'
      );
    }).join("");
  }

  function openDrill(kind) {
    if (!BOARD_CACHE) return;
    $("#distribusiDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    if (kind === "transport" || kind === "darat" || kind === "laut" || kind === "udara") {
      var bucket = kind === "transport" ? BOARD_CACHE.ruang_transportasi.overall : BOARD_CACHE.ruang_transportasi.by_type[kind];
      $("#distribusiDrillSub").textContent = "Basis volume (m³)";
      $("#distribusiDrillBody").innerHTML = capInfoHtml(bucket);
    } else {
      var field = kind === "kebutuhan" ? "kebutuhan_items" : "terhambat_items";
      var items = ((BOARD_CACHE.kpi_items || {})[field]) || [];
      $("#distribusiDrillSub").textContent = items.length + " item";
      $("#distribusiDrillBody").innerHTML = drillItemsHtml(items);
    }
    $("#distribusiDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#distribusiDrill").hidden = true; document.body.style.overflow = ""; }

  /* ---------- render ---------- */

  function renderKpi(t) {
    $("#kpiTransport").textContent = t.transport_space_pct + "%";
    $("#kpiDarat").textContent = t.kapasitas_darat_pct + "%";
    $("#kpiLaut").textContent = t.kapasitas_laut_pct + "%";
    $("#kpiUdara").textContent = t.kapasitas_udara_pct + "%";
    $("#kpiKebutuhan").textContent = fmt(t.kebutuhan_belum_match);
    $("#kpiTerhambat").textContent = fmt(t.distribusi_terhambat);
  }

  function boardItemHtml(it, extra) {
    return (
      '<div class="rn-md-board-item">' +
      "<b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small>" +
      (extra ? '<span class="chip ' + esc(extra.cls || "") + '">' + esc(extra.label) + "</span>" : "") +
      "</div>"
    );
  }

  function renderMatchingBoard(mb) {
    $("#boardKebutuhanCount").textContent = fmt(mb.kebutuhan.total);
    $("#boardKebutuhan").innerHTML = mb.kebutuhan.items.length
      ? mb.kebutuhan.items.map(function (it) {
          var urgent = ["critical", "urgent", "tinggi", "darurat"].indexOf(String(it.urgency).toLowerCase()) !== -1;
          return boardItemHtml(it, { label: it.urgency, cls: urgent ? "danger" : "" });
        }).join("")
      : '<p class="rn-muted">Semua kebutuhan sudah cocok.</p>';

    $("#boardBantuanCount").textContent = fmt(mb.bantuan.total);
    $("#boardBantuan").innerHTML = mb.bantuan.items.length
      ? mb.bantuan.items.map(function (it) { return boardItemHtml(it, { label: it.status }); }).join("")
      : '<p class="rn-muted">Tidak ada bantuan menunggu.</p>';

    $("#boardRelawanCount").textContent = fmt(mb.relawan_pickup.total);
    $("#boardRelawan").innerHTML = mb.relawan_pickup.items.length
      ? mb.relawan_pickup.items.map(function (it) { return boardItemHtml(it); }).join("")
      : '<p class="rn-muted">Belum ada relawan pickup bertugas.</p>';

    $("#boardTransportCount").textContent = fmt(mb.transportasi.total);
    $("#boardTransport").innerHTML = mb.transportasi.items.length
      ? mb.transportasi.items.map(function (it) { return boardItemHtml(it); }).join("")
      : '<p class="rn-muted">Tidak ada transport tersedia.</p>';
  }

  var DONUT_COLORS = { tersedia: "#3b82c4", terpakai: "#e8835d" };

  function renderTransportTab(byType) {
    var bucket = byType[activeTransportTab];
    var pct = bucket.pct || 0;
    $("#transportPct").textContent = pct + "%";
    $("#transportM3").textContent = fmt(bucket.terpakai_m3) + "/" + fmt(bucket.total_m3) + " m³";
    $("#transportDonut").style.background = "conic-gradient(#e8835d 0% " + pct + "%, #e5e0da " + pct + "% 100%)";
    $("#transportLegend").innerHTML =
      '<li><span class="rn-donut-dot" style="background:#3b82c4"></span><span>Tersedia</span><b>' + fmt(bucket.tersedia_m3) + ' m³</b></li>' +
      '<li><span class="rn-donut-dot" style="background:#e8835d"></span><span>Terpakai</span><b>' + fmt(bucket.terpakai_m3) + ' m³</b></li>';

    var body = $("#transportUnitBody");
    body.innerHTML = bucket.units.length
      ? bucket.units.map(function (u) {
          return (
            "<tr><td>" + esc(u.provider) + "</td><td>" + fmt(u.capacity_m3) + " m³</td><td>" + esc(u.route) + "</td>" +
            '<td><span class="chip ' + statusPillClass(u.status) + '">' + esc(u.status) + "</span></td></tr>"
          );
        }).join("")
      : '<tr><td colspan="4"><em class="rn-muted">Belum ada unit ' + activeTransportTab + '.</em></td></tr>';
  }

  function setupTransportTabs() {
    document.querySelectorAll("#transportTabs .rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll("#transportTabs .rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        activeTransportTab = tab.getAttribute("data-type");
        if (BOARD_CACHE) renderTransportTab(BOARD_CACHE.ruang_transportasi.by_type);
      });
    });
  }

  function renderAlur(rows) {
    var body = $("#alurBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="9"><em class="rn-muted">Belum ada distribution flow untuk event ini.</em></td></tr>';
      $("#alurShown").textContent = "0 distribusi";
      return;
    }
    body.innerHTML = rows.map(function (r) {
      return (
        '<tr class="rn-ba-row" data-href="' + esc(r.href) + '">' +
        "<td><b>" + esc(r.id) + "</b></td><td>" + esc(r.kebutuhan) + "</td><td>" + esc(r.bantuan) + "</td>" +
        "<td>" + esc(r.pickup_oleh) + "</td><td>" + esc(r.transportasi) + "</td><td>" + esc(r.rute) + "</td>" +
        "<td>" + esc(r.eta) + "</td>" +
        '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status_label) + "</span></td>" +
        "<td><code>" + esc(r.trace) + "</code></td></tr>"
      );
    }).join("");
    body.querySelectorAll("tr[data-href]").forEach(function (tr) {
      tr.addEventListener("click", function () { window.location.href = tr.getAttribute("data-href"); });
    });
    $("#alurShown").textContent = "Menampilkan " + rows.length + " distribusi";
  }

  var MODE_CHIP = { space_only: "", courier_pickup: "warning", both: "ok" };

  function capMeterHtml(r) {
    if (!r.kapasitas_total_kg && !r.kapasitas_total_m3) return esc(r.kapasitas);
    var pct = Math.min(100, Math.max(0, r.kapasitas_pct || 0));
    var cls = pct >= 90 ? "bad" : (pct >= 60 ? "warn" : "ok");
    return (
      '<div class="rn-md-cap">' +
      '<div class="rn-md-cap-bar"><i class="' + cls + '" style="width:' + pct + '%"></i></div>' +
      '<small>Tersedia ' + fmt(r.kapasitas_tersedia_kg) + " kg" +
      (r.kapasitas_total_m3 ? " · " + fmt(r.kapasitas_tersedia_m3) + " m³" : "") +
      " / total " + esc(r.kapasitas) + "</small></div>"
    );
  }

  function bookingsHtml(r) {
    if (!r.bookings || !r.bookings.length) return "";
    return '<div class="rn-md-bk-list">' + r.bookings.map(function (b) {
      var cls = b.status === "confirmed" ? "ok" : "warning";
      return (
        '<div class="rn-md-bk"><span><b>' + esc(b.cargo) + "</b> " + esc(b.qty || "") +
        '<small class="rn-muted"> · ' + esc(b.booker) + (b.dropoff ? " → " + esc(b.dropoff) : "") + "</small></span>" +
        '<span class="chip ' + cls + '">' + esc(b.status_label) + "</span>" +
        '<code class="rn-md-bk-id">' + esc(b.id) + "</code></div>"
      );
    }).join("") + "</div>";
  }

  function renderArmada(rows) {
    var body = $("#armadaBody");
    var shown = $("#armadaShown");
    if (!body) return;
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="9"><em class="rn-muted">Belum ada armada distribusi didaftarkan untuk event ini. Gunakan "Daftarkan Armada".</em></td></tr>';
      if (shown) shown.textContent = "0 armada";
      return;
    }
    var html = "";
    rows.forEach(function (r) {
      var kontak = r.kontak && r.kontak !== "-"
        ? '<a href="tel:' + esc(String(r.kontak).replace(/[^0-9+]/g, "")) + '">' + esc(r.kontak) + "</a>"
        : "";
      var relawan = r.pickup_volunteer_name
        ? esc(r.pickup_volunteer_name)
        : (r.service_mode === "space_only"
            ? '<span class="rn-muted">—</span>'
            : '<span class="chip warning">belum ada</span>');
      html +=
        "<tr>" +
        "<td><b>" + esc(r.provider) + "</b>" +
          (r.catatan ? '<small class="rn-muted">' + esc(r.catatan) + "</small>" : "") + "</td>" +
        "<td>" + esc(r.posko) + "</td>" +
        '<td><span class="chip ' + (MODE_CHIP[r.service_mode] || "") + '">' + esc(r.service_mode_label) + "</span>" +
          (r.booking_policy === "open" ? '<small class="rn-muted">booking terbuka</small>' : '<small class="rn-muted">PIN</small>') + "</td>" +
        "<td>" + capMeterHtml(r) + "</td>" +
        "<td>" + esc(r.berangkat) + '<small class="rn-muted">→ ' + esc(r.eta) + "</small></td>" +
        "<td>" + esc(r.lokasi_serah_terima) + '<small class="rn-muted">' + esc(r.narahubung) +
          (kontak ? " · " + kontak : "") + "</small></td>" +
        "<td>" + relawan + "</td>" +
        '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status_label) + "</span>" +
          (r.bookings_count ? '<small class="rn-muted">' + fmt(r.bookings_count) + " booking</small>" : "") + "</td>" +
        '<td><button type="button" class="btn mini rn-md-book-btn" data-space="' + esc(r.id) + '">Booking</button>' +
          '<a class="rn-md-armada-link" href="' + esc(r.href) + '">detail →</a></td>' +
        "</tr>";
      if (r.bookings && r.bookings.length) {
        html += '<tr class="rn-md-bk-row"><td colspan="9">' + bookingsHtml(r) + "</td></tr>";
      }
    });
    body.innerHTML = html;
    body.querySelectorAll(".rn-md-book-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openBookingForm(btn.getAttribute("data-space")); });
    });
    if (shown) shown.textContent = "Menampilkan " + rows.length + " armada";
  }

  function renderPickupMatches(rows) {
    var el = $("#pickupMatchList");
    if (!el) return;
    if (!rows || !rows.length) {
      el.innerHTML = '<p class="rn-muted">Semua armada kurir sudah punya relawan pickup, atau belum ada armada bermode kurir.</p>';
      return;
    }
    el.innerHTML = rows.map(function (m) {
      var cands = m.candidates && m.candidates.length
        ? m.candidates.map(function (c) { return '<span class="chip">' + esc(c.name) + "</span>"; }).join(" ")
        : '<span class="rn-muted">Belum ada relawan distribusi di posko ini</span>';
      return (
        '<div class="rn-md-pm"><div class="rn-md-pm-head"><b>' + esc(m.armada) + "</b>" +
        '<small class="rn-muted"> · ' + esc(m.posko) + " · " + fmt(m.open_need_count) + " kebutuhan terbuka</small></div>" +
        '<div class="rn-md-pm-cands">' + cands + "</div>" +
        '<a class="rn-md-armada-link" href="' + esc(m.href) + '">Kelola relawan →</a></div>'
      );
    }).join("");
  }

  function renderPeringatan(rows) {
    var el = $("#peringatanList");
    if (!rows.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Aman</h4><p>Tidak ada peringatan distribusi saat ini.</p></div></div></article>';
      return;
    }
    el.innerHTML = rows.map(function (r) {
      var inner =
        '<div class="event-main"><div><h4>⚠ ' + esc(r.title) + "</h4><p>" + esc(r.sub) + "</p></div>" +
        '<div class="chips"><span class="chip ' + (r.level === "critical" ? "danger" : "warning") + '">' + esc(r.level) + "</span></div></div>";
      return r.href
        ? '<a class="event-card rn-sh-alert" href="' + esc(r.href) + '">' + inner + "</a>"
        : '<article class="event-card">' + inner + "</article>";
    }).join("");
  }

  function renderConversions(rows) {
    var body = $("#conversionBody");
    body.innerHTML = rows.map(function (r) {
      return "<tr><td>" + esc(r.item) + "</td><td>" + esc(r.base_unit) + "</td><td>" + fmt(r.factor) + "</td><td>" + esc(r.target_unit) + "</td></tr>";
    }).join("");
  }

  function setupAutoMatch() {
    var btn = $("#autoMatchBtn");
    if (!btn) return;
    btn.addEventListener("click", async function () {
      var msg = $("#autoMatchMsg");
      msg.textContent = "Mencocokkan…";
      try {
        await window.RN_FRAPPE.call(
          "rescue_net.api_control_centre.auto_match_distribution",
          { disaster_event: getEventId(), limit: 5 },
          { method: "POST" }
        );
        msg.textContent = "Selesai — memuat ulang…";
        await loadBoard();
        msg.textContent = "";
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (
          /login|permission|akses/i.test(String(err && err.message)) ? " (perlu login sebagai operator)" : ""
        );
      }
    });
  }

  window.__distribusiReloadBoard = function () { return loadBoard(); };

  function openBookingForm(spaceId) {
    var det = $("#bookingForm");
    if (!det) return;
    var inp = det.querySelector('[name="transport_space"]');
    if (inp && spaceId) inp.value = spaceId;
    det.open = true;
    det.scrollIntoView({ behavior: "smooth", block: "center" });
    var cargo = det.querySelector('[name="cargo_desc"]');
    if (cargo) setTimeout(function () { cargo.focus(); }, 300);
  }

  function setupPostForm(sel, method, msgSel, opts) {
    opts = opts || {};
    var form = $(sel);
    if (!form) return;
    var msg = $(msgSel);
    async function submit(extra) {
      var payload = {};
      [].forEach.call(form.elements, function (el) {
        if (!el.name) return;
        var v = el.value == null ? "" : String(el.value).trim();
        if (v !== "") payload[el.name] = v;
      });
      Object.keys(extra || {}).forEach(function (k) { payload[k] = extra[k]; });
      if (msg) msg.textContent = "Memproses…";
      try {
        var res = await window.RN_FRAPPE.call(method(payload), payload, { method: "POST" });
        if (msg) msg.textContent = (opts.done ? opts.done(res) : "Berhasil.");
        if (!opts.keep) form.reset();
        await loadBoard();
      } catch (err) {
        var m = (err && err.message) || String(err);
        if (msg) msg.textContent = "Gagal: " + m + (/login|permission|akses|whitelist/i.test(m) ? " (perlu login)" : "");
      }
    }
    form.addEventListener("submit", function (e) { e.preventDefault(); submit(); });
    form.querySelectorAll("[data-act]").forEach(function (b) {
      if (b.type === "submit") return;
      b.addEventListener("click", function () { submit({ __act: b.getAttribute("data-act") }); });
    });
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    BOARD_CACHE = data;
    $("#distribusiUpdated").textContent = "Distribusi · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    $("#distribusiStatus").textContent = "Dimuat pukul " + String(data.generated_at || "").slice(11, 16);

    renderKpi(data.totals || {});
    renderMatchingBoard(data.matching_board || {});
    renderTransportTab(data.ruang_transportasi.by_type);
    renderArmada(data.armada_posko || []);
    renderPickupMatches(data.pickup_matches || []);
    renderAlur(data.alur_distribusi || []);
    renderPeringatan(data.peringatan || []);
    renderConversions(data.conversions || []);
    $("#matchedTodayLabel").textContent = fmt(data.matched_today) + " distribusi berhasil dicocokkan hari ini";
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    document.querySelectorAll(".rn-md-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#distribusiDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });
    setupTransportTabs();
    setupAutoMatch();

    function wireOpen(btnSel, detSel, focusSel) {
      var btn = $(btnSel), det = $(detSel);
      if (!btn || !det) return;
      btn.addEventListener("click", function () {
        det.open = true;
        det.scrollIntoView({ behavior: "smooth", block: "center" });
        var f = det.querySelector(focusSel);
        if (f) setTimeout(function () { f.focus(); }, 300);
      });
    }
    wireOpen("#armadaAddBtn", "#armadaForm", 'input[name="provider_name"]');
    wireOpen("#bookingConfirmBtn", "#bookingConfirmForm", 'input[name="booking"]');

    setupPostForm("[data-create-booking]", function () {
      return "rescue_net.api_logistics.book_transport_space";
    }, "[data-booking-message]", {
      done: function (res) {
        return res && res.verification_pin
          ? "Booking diajukan. PIN untuk koordinator: " + res.verification_pin
          : "Booking dibuat & terkonfirmasi.";
      },
    });

    setupPostForm("[data-confirm-booking]", function (p) {
      return p.__act === "reject"
        ? "rescue_net.api_logistics.reject_transport_booking"
        : "rescue_net.api_logistics.confirm_transport_booking";
    }, "[data-confirm-message]", {
      keep: true,
      done: function (res) { return "Status booking: " + (res && res.status || "-"); },
    });

    loadBoard().catch(function (err) { console.error("[distribusi board]", err); });
  });
})();

let DISTRIBUTION_CACHE = null;

function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  ) ? "n/a" : v;
}

function rowId(row) {
  return (
    row?.name ||
    row?.id ||
    row?.legacy_id ||
    ""
  );
}

function getDistributionPosko() {
  const params =
    new URLSearchParams(
      location.search
    );

  return (
    params.get("id") ||
    params.get("posko") ||
    "posko-sim-logistik"
  );
}

function chipClass(status) {
  if (
    status === "in_transit" ||
    status === "assigned_pickup"
  ) {
    return "warning";
  }

  if (
    status === "arrived_at_posko"
  ) {
    return "danger";
  }

  return "neutral";
}

async function dashboard() {
  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_logistics.dashboard",
      {
        posko:
          getDistributionPosko()
      }
    );

  DISTRIBUTION_CACHE = ctx;

  return ctx;
}

function renderOffer(a) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>
            ${safe(a.item_name)}
            · ${safe(a.quantity)}
            ${safe(a.unit)}
          </h4>
          <p>
            Donatur:
            ${safe(a.donor_name)}
          </p>
          <p>
            Tujuan:
            ${safe(a.target_posko)}
          </p>
        </div>
        <div class="chips">
          <span class="chip ${chipClass(a.offer_status)}">
            ${safe(a.offer_status)}
          </span>
        </div>
      </div>
    </article>
  `;
}

async function loadAidOffers() {
  const needPickup =
    document.querySelector(
      "[data-need-pickup]"
    );

  const selfDelivery =
    document.querySelector(
      "[data-self-delivery]"
    );

  if (
    !needPickup &&
    !selfDelivery
  ) {
    return;
  }

  try {
    const ctx =
      DISTRIBUTION_CACHE ||
      await dashboard();

    const offers =
      ctx.offers || [];

    const available =
      offers.filter(
        a =>
          [
            "available",
            "need_pickup"
          ].includes(
            a.offer_status
          )
      );

    if (needPickup) {
      needPickup.innerHTML =
        available.length
          ? available
              .map(renderOffer)
              .join("")
          : `
            <article class="event-card">
              <h4>Tidak ada bantuan perlu pickup</h4>
              <p>Tidak ada Aid Offer tersedia.</p>
            </article>
          `;
    }

    if (selfDelivery) {
      selfDelivery.innerHTML = `
        <article class="event-card">
          <h4>Frappe-native Aid Offer</h4>
          <p>
            Self-delivery legacy digantikan oleh lifecycle
            Aid Offer dan Distribution Flow.
          </p>
        </article>
      `;
    }

  } catch (err) {
    if (needPickup) {
      needPickup.innerHTML =
        `<article class="event-card">` +
        `<h4>Gagal load Aid Offer</h4>` +
        `<p>${safe(err.message)}</p>` +
        `</article>`;
    }
  }
}

async function loadTransportSpaces() {
  const target =
    document.querySelector(
      "[data-transport-spaces]"
    );

  if (!target) return;

  try {
    const ctx =
      DISTRIBUTION_CACHE ||
      await dashboard();

    const transports =
      ctx.transports || [];

    target.innerHTML =
      transports.length
        ? transports.map(t => `
          <article class="event-card">
            <div class="event-main">
              <div>
                <h4>${safe(t.provider_name)}</h4>
                <p>
                  ${safe(t.transport_type)}
                  · ${safe(t.route_origin)}
                  →
                  ${safe(t.route_destination)}
                </p>
                <p>
                  Kapasitas:
                  ${safe(t.capacity_weight_kg)} kg
                  · ${safe(t.capacity_volume_m3)} m³
                  · Berangkat: ${safe(t.departure_time)}
                  · ETA: ${safe(t.eta)}
                </p>
                <p>
                  Lokasi kini: ${safe(t.current_location)}
                  · Serah terima: ${safe(t.handover_location)}
                </p>
                <p>
                  Koordinasi: ${safe(t.handover_contact_person)}
                  ${t.handover_contact_phone ? "· ☎ " + safe(t.handover_contact_phone) : ""}
                </p>
              </div>
              <div class="chips">
                <span class="chip neutral">
                  ${safe(t.transport_status)}
                </span>
                <span class="chip neutral">
                  ${safe(rowId(t))}
                </span>
              </div>
            </div>
          </article>
        `).join("")
        : `
          <article class="event-card">
            <h4>Belum ada transport</h4>
          </article>
        `;

  } catch (err) {
    target.innerHTML =
      `<article class="event-card">` +
      `<h4>Gagal load transport</h4>` +
      `<p>${safe(err.message)}</p>` +
      `</article>`;
  }
}

async function loadDistributionFlows() {
  const target =
    document.querySelector(
      "[data-distribution-flows]"
    );

  if (!target) return;

  try {
    const ctx =
      DISTRIBUTION_CACHE ||
      await dashboard();

    const flows =
      ctx.flows || [];

    target.innerHTML =
      flows.length
        ? flows.map(f => `
          <article class="event-card">
            <div class="event-main">
              <div>
                <h4>${safe(rowId(f))}</h4>
                <p>
                  Item: ${safe(f.item_name)}
                  · Quantity:
                  ${safe(f.quantity)}
                  ${safe(f.unit)}
                </p>
                <p>
                  Source:
                  ${safe(f.source_posko)}
                  · Destination:
                  ${safe(f.destination_posko)}
                  · ETA:
                  ${safe(f.eta_final)}
                </p>
              </div>
              <div class="chips">
                <span class="chip ${chipClass(f.flow_status)}">
                  ${safe(f.flow_status)}
                </span>
              </div>
            </div>
          </article>
        `).join("")
        : `
          <article class="event-card">
            <h4>Belum ada flow</h4>
            <p>
              Belum ada Distribution Flow.
            </p>
          </article>
        `;

  } catch (err) {
    target.innerHTML =
      `<article class="event-card">` +
      `<h4>Gagal load flow</h4>` +
      `<p>${safe(err.message)}</p>` +
      `</article>`;
  }
}

function setupTransportForm() {
  const form =
    document.querySelector(
      "[data-create-transport]"
    );

  const msg =
    document.querySelector(
      "[data-transport-message]"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      try {
        if (msg) {
          msg.textContent =
            "Menyimpan transport...";
        }

        const field = (n) => (form[n] && form[n].value ? form[n].value.trim() : "");

        await RN_FRAPPE.call(
          "rescue_net.api_logistics.create_transport_space",
          {
            coordination_posko:
              field("coordination_posko") || getDistributionPosko(),

            disaster_event:
              field("disaster_event_id") || null,

            provider_name: field("provider_name"),
            transport_type: field("transport_type"),
            route_origin: field("route_origin"),
            route_destination: field("route_destination"),

            capacity_weight_kg:
              Number(form.capacity_weight_kg.value || 0),

            capacity_volume_m3:
              Number(form.capacity_volume_m3.value || 0),

            departure_at: field("departure_at").replace("T", " "),
            eta_at: field("eta_at").replace("T", " "),
            service_mode: field("service_mode"),
            booking_policy: field("booking_policy"),
            current_location: field("current_location"),
            handover_location: field("handover_location"),
            handover_contact_person: field("handover_contact_person"),
            handover_contact_phone: field("handover_contact_phone"),
            coordination_notes: field("coordination_notes")
          },
          {
            method: "POST"
          }
        );

        DISTRIBUTION_CACHE = null;

        if (msg) {
          msg.textContent =
            "Armada berhasil disimpan.";
        }
        form.reset();

        await loadTransportSpaces();
        if (typeof window.__distribusiReloadBoard === "function") {
          try { await window.__distribusiReloadBoard(); } catch (e) {}
        }

      } catch (err) {
        if (msg) {
          msg.textContent =
            err.message;
        }
      }
    }
  );
}

function findReference(
  list,
  id
) {
  return (
    list || []
  ).find(
    row =>
      rowId(row) === id ||
      row.legacy_id === id
  );
}

function setupFlowForm() {
  const form =
    document.querySelector(
      "[data-create-flow]"
    );

  const msg =
    document.querySelector(
      "[data-flow-message]"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      try {
        const ctx =
          DISTRIBUTION_CACHE ||
          await dashboard();

        const needId =
          form.need_id.value.trim();

        const aidId =
          form.aid_offer_id.value.trim();

        const transportId =
          form.transport_space_id.value.trim();

        const need =
          findReference(
            ctx.needs,
            needId
          );

        const aid =
          findReference(
            ctx.offers,
            aidId
          );

        const selected =
          need ||
          aid ||
          {};

        const destination =
          form.destination_node_id
            .value
            .trim() ||
          selected.posko ||
          selected.target_posko ||
          getDistributionPosko();

        const item =
          selected.item_name ||
          "Distribution";

        if (msg) {
          msg.textContent =
            "Menyimpan flow...";
        }

        await RN_FRAPPE.call(
          "rescue_net.api_logistics.create_flow",
          {
            destination_posko:
              destination,

            item_text:
              item,

            quantity:
              selected.quantity || null,

            unit:
              selected.unit || null,

            quantity_mode:
              selected.quantity_mode ||
              "unknown",

            logistic_need:
              needId || null,

            aid_offer:
              aidId || null,

            transport_space:
              transportId || null,

            eta_final:
              form.eta_final.value.trim()
          },
          {
            method: "POST"
          }
        );

        DISTRIBUTION_CACHE = null;

        if (msg) {
          msg.textContent =
            "Distribution Flow berhasil disimpan.";
        }

        await loadDistributionFlows();

      } catch (err) {
        if (msg) {
          msg.textContent =
            err.message;
        }
      }
    }
  );
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      console.error(
        "RN_FRAPPE unavailable"
      );
      return;
    }

    setupTransportForm();
    setupFlowForm();

    dashboard()
      .then(() =>
        Promise.all([
          loadAidOffers(),
          loadTransportSpaces(),
          loadDistributionFlows()
        ])
      )
      .catch(console.error);
  }
);
