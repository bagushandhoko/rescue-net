/* Shelter & Akomodasi dashboard — pages/shelter-detail.html
 * New overview dashboard: rescue_net.api_shelter.shelter_board (guest,
 * cross-shelter for the whole disaster event).
 * Legacy per-posko panels (Shelter Occupancy riwayat, Shelter Needs, Shelter
 * Stock, Distribution Flows, the 3 input forms) keep calling
 * api_shelter.dashboard / api_logistics.dashboard for the posko in `?id=`.
 */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_shelter.shelter_board";

  var BOARD_CACHE = null;
  var SHELTER_CONTEXT_CACHE = null;

  var $ = function (sel, root) {
    return (root || document).querySelector(sel);
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fmt(n) {
    return Number(n || 0).toLocaleString("id-ID");
  }

  function safe(v) {
    return v === null || v === undefined || v === "" ? "n/a" : v;
  }

  function getShelterPoskoId() {
    var params = new URLSearchParams(window.location.search);
    var value = params.get("id") || "posko-sim-shelter";
    value = String(value).trim();
    if (value && !value.includes(":") && value.startsWith("posko-")) {
      value = "posko_nodes:" + value;
    }
    return value;
  }

  function getEventId() {
    return new URLSearchParams(window.location.search).get("event") || "event-sim-001";
  }

  function statusMsg(msg) {
    var el = document.getElementById("shelterStatus");
    if (el) el.textContent = msg;
  }

  function rowId(row) {
    return (row && (row.name || row.id || row.legacy_id)) || "";
  }

  function statusPillClass(status) {
    if (status === "kritis" || status === "overcapacity") return "danger";
    if (status === "waspada" || status === "perlu") return "warning";
    if (status === "aman" || status === "cukup") return "ok";
    return "";
  }

  function statusLabel(status) {
    var map = { overcapacity: "Overcapacity", aman: "Aman", kritis: "Kritis", perlu: "Perlu", cukup: "Cukup" };
    return map[status] || status;
  }

  /* ---------- KPI drill-down modal (reuses .rn-ba-modal) ---------- */

  var DRILL_TITLES = {
    shelter: "Daftar Shelter",
    overcapacity: "Shelter Overcapacity",
    air_bersih: "Air Bersih Kritis",
    sanitasi: "Sanitasi Kritis",
  };
  var DRILL_FIELD = {
    shelter: "shelter_items",
    overcapacity: "overcapacity_items",
    air_bersih: "air_bersih_items",
    sanitasi: "sanitasi_items",
  };

  function drillItemsHtml(items) {
    if (!items || !items.length) {
      return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    }
    return items
      .map(function (it) {
        return (
          '<a class="rn-ba-ditem" href="' + esc(it.href || "#") + '">' +
          "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
          '<span class="rn-ba-ditem-go">→</span></a>'
        );
      })
      .join("");
  }

  function openDrill(kind) {
    var data = BOARD_CACHE;
    if (!data) return;
    var items = ((data.kpi_items || {})[DRILL_FIELD[kind]]) || [];
    $("#shelterDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    $("#shelterDrillSub").textContent = items.length + " item";
    $("#shelterDrillBody").innerHTML = drillItemsHtml(items);
    var m = $("#shelterDrill");
    m.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeDrill() {
    $("#shelterDrill").hidden = true;
    document.body.style.overflow = "";
  }

  function setupDrill() {
    document.querySelectorAll(".rn-sh-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#shelterDrill [data-close]").forEach(function (el) {
      el.addEventListener("click", closeDrill);
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });
  }

  /* ---------- donut ---------- */

  function renderOkupansiDonut(ko) {
    var pct = ko.pct || 0;
    var el = document.getElementById("okupansiDonut");
    $("#okupansiPct").textContent = pct + "%";
    el.style.background =
      "conic-gradient(#e8835d 0% " + pct + "%, #e5e0da " + pct + "% 100%)";

    var legend = document.getElementById("okupansiLegend");
    legend.innerHTML = [
      { color: "#e8835d", label: "Terisi", value: ko.terisi },
      { color: "#3b82c4", label: "Tersedia", value: ko.tersedia },
      { color: "#d9d2c8", label: "Kapasitas Max", value: ko.kapasitas_max },
    ].map(function (s) {
      return (
        '<li><span class="rn-donut-dot" style="background:' + s.color + '"></span>' +
        "<span>" + s.label + "</span><b>" + fmt(s.value) + "</b></li>"
      );
    }).join("");
  }

  /* ---------- render main board ---------- */

  function renderKpi(t) {
    $("#kpiPenghuni").textContent = fmt(t.total_penghuni);
    $("#kpiKapasitas").textContent = fmt(t.kapasitas_maksimal);
    $("#kpiOvercapacity").textContent = fmt(t.overcapacity);
    $("#kpiRentan").textContent = fmt(t.kelompok_rentan);
    $("#kpiAirKritis").textContent = fmt(t.air_bersih_kritis) + " Lokasi";
    $("#kpiSanitasiKritis").textContent = fmt(t.sanitasi_kritis) + " Lokasi";
  }

  function renderDaftarShelter(rows) {
    var body = $("#daftarShelterBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6"><em class="rn-muted">Belum ada shelter tercatat untuk event ini.</em></td></tr>';
      $("#daftarShelterShown").textContent = "0 shelter";
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        return (
          '<tr class="rn-ba-row" data-href="' + esc(r.href) + '">' +
          "<td><b>" + esc(r.title) + "</b></td><td>" + esc(r.lokasi) + "</td>" +
          "<td>" + fmt(r.penghuni) + "</td><td>" + fmt(r.kapasitas) + "</td>" +
          "<td>" + (r.okupansi_pct == null ? "-" : r.okupansi_pct + "%") + "</td>" +
          '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(statusLabel(r.status)) + "</span></td></tr>"
        );
      })
      .join("");
    body.querySelectorAll("tr[data-href]").forEach(function (tr) {
      tr.addEventListener("click", function () { window.location.href = tr.getAttribute("data-href"); });
    });
    $("#daftarShelterShown").textContent = "Menampilkan " + rows.length + " dari " + rows.length + " shelter";
  }

  function renderKebutuhanDasar(rows) {
    var el = $("#kebutuhanDasar");
    el.innerHTML = rows
      .map(function (r) {
        return (
          '<article class="event-card"><div class="event-main"><div><h4>' + esc(r.label) + "</h4>" +
          (r.open_count ? "<p>" + r.open_count + " kebutuhan terbuka</p>" : "<p>Tidak ada kebutuhan terbuka</p>") + "</div>" +
          '<div class="chips"><span class="chip ' + statusPillClass(r.status) + '">' + esc(statusLabel(r.status)) + "</span></div></div></article>"
        );
      })
      .join("");
  }

  function renderAkomodasiRelawan(rows) {
    var body = $("#akomodasiRelawanBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5"><em class="rn-muted">Belum ada akomodasi relawan/petugas tercatat.</em></td></tr>';
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        return (
          "<tr><td><b>" + esc(r.lokasi) + "</b></td><td>" + fmt(r.terisi) + " / " + fmt(r.kapasitas) + "</td>" +
          "<td>" + fmt(r.kapasitas) + "</td><td>" + fmt(r.tersedia) + "</td><td>" + r.pct + "%</td></tr>"
        );
      })
      .join("");
  }

  function renderSanitasiAir(t) {
    var el = $("#sanitasiAir");
    el.innerHTML =
      '<div class="rn-sh-sanitasi-row"><span>Kebutuhan Air Bersih terbuka (kritis/urgent)</span><b>' + fmt(t.air_bersih_kritis) + ' lokasi</b></div>' +
      '<div class="rn-sh-sanitasi-row"><span>Kebutuhan Sanitasi terbuka (kritis/urgent)</span><b>' + fmt(t.sanitasi_kritis) + ' lokasi</b></div>' +
      '<p class="rn-muted rn-sh-gap-note">Jumlah toilet/MCK &amp; titik air fisik belum tercatat sebagai data terstruktur (belum ada field-nya) — dihitung dari kebutuhan sanitasi/air yang masih terbuka.</p>';
  }

  function renderCheckinOut(c) {
    var el = $("#checkinOut");
    el.innerHTML =
      '<div class="rn-sh-checkinout-row"><span>Check-in</span><b class="rn-in">+' + fmt(c.checkin_people) + '</b><small>' + c.checkin_households + ' keluarga</small></div>' +
      '<div class="rn-sh-checkinout-row"><span>Check-out</span><b class="rn-out">-' + fmt(c.checkout_people) + '</b><small>' + c.checkout_households + ' keluarga</small></div>' +
      '<div class="rn-sh-checkinout-row"><span>Perpindahan Shelter</span><b>' + fmt(c.moved_people) + '</b><small>' + c.moved_households + ' keluarga</small></div>';
  }

  function renderKelompokRentan(rows) {
    var body = $("#kelompokRentanBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4"><em class="rn-muted">Belum ada data kelompok rentan.</em></td></tr>';
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        return (
          "<tr><td>" + esc(r.label) + "</td><td>" + fmt(r.jumlah) + "</td><td>" + r.pct + "%</td><td>" + esc(r.lokasi_terbanyak) + "</td></tr>"
        );
      })
      .join("");
  }

  function renderPeringatan(rows) {
    var el = $("#peringatanList");
    if (!rows.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Aman</h4><p>Tidak ada peringatan keselamatan saat ini.</p></div></div></article>';
      return;
    }
    el.innerHTML = rows
      .map(function (r) {
        return (
          '<a class="event-card rn-sh-alert" href="' + esc(r.href) + '"><div class="event-main"><div><h4>⚠ ' + esc(r.title) + "</h4><p>" + esc(r.sub) + "</p></div>" +
          '<div class="chips"><span class="chip danger">' + esc(r.level) + "</span></div></div></a>"
        );
      })
      .join("");
  }

  var PLACEHOLDER_ICONS = ["🏕️", "🧺", "💧"];

  function renderBukti(rows, uploadHref) {
    var el = $("#buktiGrid");
    var real = rows
      .map(function (r) {
        var url = r.evidence_url || r.file_url || "";
        var cap = String(r.evidence_caption || r.caption || r.title || "Bukti shelter")
          .replace(/^\s*\[[^\]]+\]\s*/, "");
        var meta = [r.location_text, r.reporter_name || r.uploader].filter(Boolean).join(" · ");
        return (
          '<a class="rn-bukti-thumb" href="' + esc(url) + '" target="_blank" rel="noopener"' +
          ' data-caption="' + esc(cap) + '" data-meta="' + esc(meta) + '">' +
          '<img src="' + esc(url) + '" alt="' + esc(cap) + '" loading="lazy"></a>'
        );
      })
      .join("");

    var placeholders = "";
    if (!rows.length) {
      placeholders = PLACEHOLDER_ICONS.map(function (icon) {
        return (
          '<div class="rn-dp-photo-placeholder" title="Simulasi — belum ada foto asli">' +
          "<span>" + icon + "</span><small>Simulasi</small></div>"
        );
      }).join("");
    }

    var upload = '<a class="rn-dp-upload-tile" href="' + esc(uploadHref || "#") + '"><span>＋</span>Unggah Foto</a>';
    el.innerHTML = real + placeholders + upload;
  }

  async function loadBoard() {
    statusMsg("Memuat dashboard shelter…");
    var eventId = getEventId();
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: eventId });
    BOARD_CACHE = data;

    $("#shelterUpdated").textContent = "Shelter · Diperbarui " + String(data.generated_at || "").slice(11, 16);

    renderKpi(data.totals || {});
    renderDaftarShelter(data.daftar_shelter || []);
    renderOkupansiDonut(data.kapasitas_okupansi || { terisi: 0, tersedia: 0, kapasitas_max: 0, pct: 0 });
    renderKebutuhanDasar(data.kebutuhan_dasar || []);
    renderSanitasiAir(data.totals || {});
    renderCheckinOut(data.checkin_checkout || { checkin_people: 0, checkin_households: 0, checkout_people: 0, checkout_households: 0, moved_people: 0, moved_households: 0 });
    renderKelompokRentan(data.kelompok_rentan || []);
    renderPeringatan(data.peringatan || []);
    renderAkomodasiRelawan(data.akomodasi_relawan || []);

    var evidenceHref =
      "evidence.html?event=" + encodeURIComponent(data.disaster_event || "") + "&object_type=shelter";
    renderBukti(data.bukti || [], evidenceHref);
    var seeAll = $("#evidenceSeeAll");
    if (seeAll) seeAll.href = evidenceHref;

    statusMsg("Dimuat pukul " + String(data.generated_at || "").slice(11, 16));
  }

  /* ---------- legacy per-posko panels (unchanged behaviour) ---------- */

  function card(title, body, chip) {
    return (
      '<article class="event-card"><div class="event-main"><div><h4>' + esc(safe(title)) + "</h4><p>" + body + "</p></div>" +
      '<div class="chips">' + (chip ? '<span class="chip warning">' + esc(safe(chip)) + "</span>" : "") + "</div></div></article>"
    );
  }

  function latestOccupancy(items) { return items && items.length ? items[0] : null; }

  function renderLegacyOccupancies(items) {
    var el = document.getElementById("shelterOccupancies");
    if (!el) return;
    document.getElementById("occLegacyCount").textContent = items.length;
    el.innerHTML = items.length
      ? items.map(function (o) {
          return card(
            o.shelter_name,
            "Occupancy: " + safe(o.current_occupancy) + "/" + safe(o.capacity_total) + "<br>" +
              "Families: " + safe(o.families_count) + "<br>" +
              "Children: " + safe(o.children_count) + " · Elderly: " + safe(o.elderly_count) + " · Disabled: " + safe(o.disability_count),
            o.verification_status
          );
        }).join("")
      : card("Belum ada occupancy", "Catat data hunian shelter.", "empty");
  }

  function renderLegacyNeeds(items) {
    var el = document.getElementById("shelterNeeds");
    if (!el) return;
    el.innerHTML = items.length
      ? items.map(function (n) {
          return card(
            n.item_name,
            "Need: " + safe(n.quantity_needed) + " " + safe(n.unit) + "<br>Priority: " + safe(n.priority) + "<br>Before: " + safe(n.needed_before),
            n.need_status
          );
        }).join("")
      : card("Belum ada kebutuhan shelter", "Tambahkan kebutuhan shelter.", "empty");
  }

  function renderLegacyStock(items) {
    var el = document.getElementById("shelterStock");
    if (!el) return;
    el.innerHTML = items.length
      ? items.map(function (s) { return card(s.item_name, "Current stock: <b>" + safe(s.quantity) + "</b> " + safe(s.unit), s.stock_state); }).join("")
      : card("Belum ada stok shelter", "Belum ada Stock Observation.", "empty");
  }

  function renderLegacyFlows(items) {
    var el = document.getElementById("shelterFlows");
    if (!el) return;
    el.innerHTML = items.length
      ? items.map(function (f) { return card(rowId(f), "Item: " + safe(f.item_name) + "<br>Source: " + safe(f.source_posko) + "<br>ETA: " + safe(f.eta_final), f.flow_status); }).join("")
      : card("Belum ada distribution flow", "Belum ada distribusi menuju shelter.", "empty");
  }

  async function loadLegacy() {
    var poskoId = getShelterPoskoId();
    var results = await Promise.all([
      window.RN_FRAPPE.call("rescue_net.api_shelter.dashboard", { posko: poskoId }),
      window.RN_FRAPPE.call("rescue_net.api_logistics.dashboard", { posko: poskoId }),
    ]);
    var shelter = results[0] || {};
    var logistics = results[1] || {};
    var posko = (shelter.poskos && shelter.poskos[0]) || (logistics.poskos && logistics.poskos[0]) || { name: poskoId };

    SHELTER_CONTEXT_CACHE = {
      posko: posko,
      occupancies: shelter.occupancies || [],
      households: shelter.households || [],
      needs: shelter.needs || [],
      stocks: logistics.stocks || [],
      flows: logistics.flows || [],
    };

    renderLegacyOccupancies(SHELTER_CONTEXT_CACHE.occupancies);
    renderLegacyNeeds(SHELTER_CONTEXT_CACHE.needs);
    renderLegacyStock(SHELTER_CONTEXT_CACHE.stocks);
    renderLegacyFlows(SHELTER_CONTEXT_CACHE.flows);

    var form = document.getElementById("occupancyForm");
    if (form && form.posko_id) form.posko_id.value = poskoId;
  }

  function setupOccupancyForm() {
    var form = document.getElementById("occupancyForm");
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      await window.RN_FRAPPE.call("rescue_net.api_shelter.create_occupancy", {
        posko: form.posko_id.value.trim(),
        shelter_name: form.shelter_name.value.trim(),
        capacity_total: Number(form.capacity_total.value || 0),
        current_occupancy: Number(form.current_occupancy.value || 0),
        families_count: Number(form.families_count.value || 0),
        children_count: Number(form.children_count.value || 0),
        elderly_count: Number(form.elderly_count.value || 0),
        disability_count: Number(form.disabled_count.value || 0),
      }, { method: "POST" });
      statusMsg("Shelter occupancy saved.");
      await refreshAll();
    });
  }

  function setupNeedForm() {
    var form = document.getElementById("needForm");
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      await window.RN_FRAPPE.call("rescue_net.api_shelter.create_need", {
        posko: getShelterPoskoId(),
        item_name: form.item_name.value.trim(),
        quantity_mode: "known",
        quantity_needed: Number(form.quantity_needed.value || 0),
        unit: form.unit.value.trim(),
        priority: form.priority.value,
        needed_before: form.needed_before.value.trim(),
        notes: form.notes.value.trim(),
      }, { method: "POST" });
      statusMsg("Shelter need saved.");
      await refreshAll();
    });
  }

  async function refreshAll() {
    await Promise.all([
      loadBoard().catch(function (err) { statusMsg("Gagal memuat dashboard: " + err.message); }),
      loadLegacy().catch(function (err) { console.error("[shelter-detail legacy]", err); }),
    ]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) {
      statusMsg("Frappe client tidak tersedia.");
      return;
    }

    setupDrill();
    setupOccupancyForm();
    setupNeedForm();

    var btn = document.getElementById("refreshShelter");
    if (btn) btn.addEventListener("click", function () { refreshAll(); });

    refreshAll();
  });
})();
