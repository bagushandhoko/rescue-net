/* Dapur Umum dashboard — pages/dapur-umum.html
 * New dashboard: rescue_net.api_kitchen.kitchen_board (guest).
 * Legacy raw panels (Kitchen Stock riwayat, Meal Productions, Stock
 * Movements, Record Meal Production form) keep calling
 * rescue_net.api_kitchen.dashboard / create_production as before.
 */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_kitchen.kitchen_board";
  var LEGACY_METHOD = "rescue_net.api_kitchen.dashboard";

  var BOARD_CACHE = null;
  var LEGACY_CACHE = null;

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

  function getKitchenPoskoId() {
    var params = new URLSearchParams(window.location.search);
    var value = params.get("id") || "posko_nodes:posko-sim-dapur";
    value = String(value).trim();
    if (value && !value.includes(":") && value.startsWith("posko-")) {
      value = "posko_nodes:" + value;
    }
    return value;
  }

  function getEventId() {
    return new URLSearchParams(window.location.search).get("event") || "";
  }

  function statusMsg(msg) {
    var el = document.getElementById("kitchenStatus");
    if (el) el.textContent = msg;
  }

  function rowId(row) {
    if (!row) return "";
    return row.name || row.id || row.legacy_id || "";
  }

  function statusPillClass(status) {
    if (status === "kritis") return "danger";
    if (status === "waspada") return "warning";
    return "";
  }

  /* ---------- KPI drill-down modal (reuses .rn-ba-modal from Bencana Aktif) ---------- */

  var DRILL_TITLES = {
    jiwa: "Jiwa Dilayani",
    kapasitas: "Kapasitas Porsi / Hari",
    produksi: "Produksi Hari Ini",
    gap: "Gap Porsi",
    bahan: "Bahan Kritis",
    distribusi: "Distribusi Hari Ini",
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

    $("#kitchenDrillTitle").textContent = DRILL_TITLES[kind] || kind;

    if (kind === "kapasitas" || kind === "gap") {
      var t = data.target_layanan || {};
      $("#kitchenDrillSub").textContent = "Berbasis puncak produksi historis (data tipis = jujur, bukan target manual).";
      $("#kitchenDrillBody").innerHTML =
        '<div class="rn-dp-target rn-dp-target-modal">' +
        "<div><span>Total Target</span><b>" + fmt(t.total_target) + "</b><small>porsi / hari</small></div>" +
        "<div><span>Target Jiwa</span><b>" + fmt(t.target_jiwa) + "</b><small>jiwa</small></div>" +
        "<div><span>Rasio</span><b>" + esc(t.rasio_label || "-") + "</b></div>" +
        "</div>";
    } else {
      var fieldMap = {
        jiwa: "jiwa_dilayani_items",
        produksi: "produksi_hari_ini_items",
        bahan: "bahan_kritis_items",
        distribusi: "distribusi_hari_ini_items",
      };
      var items = (data.kpi_items || {})[fieldMap[kind]] || [];
      $("#kitchenDrillSub").textContent = items.length + " item";
      $("#kitchenDrillBody").innerHTML = drillItemsHtml(items);
    }

    var m = $("#kitchenDrill");
    m.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeDrill() {
    $("#kitchenDrill").hidden = true;
    document.body.style.overflow = "";
  }

  function setupDrill() {
    document.querySelectorAll(".rn-dp-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openDrill(btn.getAttribute("data-kpi"));
      });
    });
    document.querySelectorAll("#kitchenDrill [data-close]").forEach(function (el) {
      el.addEventListener("click", closeDrill);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrill();
    });
  }

  /* ---------- donut ---------- */

  var DONUT_COLORS = {
    distributed: "#3f8f65",
    dispatched: "#3b82c4",
    prepared: "#dd8a2f",
    remaining: "#d9d2c8",
  };

  function renderDonut(donut) {
    var segs = (donut && donut.segments) || [];
    var el = document.getElementById("produksiDonut");
    var legend = document.getElementById("produksiLegend");
    document.getElementById("donutTotal").textContent = fmt(donut && donut.total);

    var acc = 0;
    var stops = segs
      .map(function (s) {
        var start = acc;
        acc += s.pct;
        var color = DONUT_COLORS[s.key] || "#bbb";
        return color + " " + start + "% " + acc + "%";
      })
      .join(", ");
    if (el) {
      el.style.background = stops
        ? "conic-gradient(" + stops + ")"
        : "conic-gradient(#e5e0da 0% 100%)";
    }

    if (legend) {
      legend.innerHTML = segs
        .map(function (s) {
          return (
            '<li><span class="rn-donut-dot" style="background:' + (DONUT_COLORS[s.key] || "#bbb") + '"></span>' +
            "<span>" + esc(s.label) + "</span><b>" + fmt(s.value) + "</b><small>(" + s.pct + "%)</small></li>"
          );
        })
        .join("");
    }
  }

  /* ---------- render main board ---------- */

  function renderKpi(totals) {
    $("#kpiJiwa").textContent = fmt(totals.jiwa_dilayani);
    $("#kpiKapasitas").textContent = fmt(totals.kapasitas_porsi_hari);
    $("#kpiProduksi").textContent = fmt(totals.produksi_hari_ini);
    $("#kpiGap").textContent = fmt(totals.gap_porsi);
    $("#kpiBahan").textContent = fmt(totals.bahan_kritis);
    $("#kpiDistribusi").textContent = fmt(totals.distribusi_hari_ini);
    var pct = totals.kapasitas_porsi_hari
      ? Math.round((100 * totals.gap_porsi) / totals.kapasitas_porsi_hari)
      : 0;
    $("#kpiGapHint").textContent = pct + "% dari kapasitas";
  }

  function renderTarget(t) {
    $("#targetTotal").textContent = fmt(t.total_target);
    $("#targetJiwa").textContent = fmt(t.target_jiwa);
    $("#targetRasio").textContent = t.rasio_label || "-";
  }

  function renderStokBahan(rows) {
    var body = $("#stokBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4"><em class="rn-muted">Belum ada stok bahan tercatat.</em></td></tr>';
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        return (
          "<tr><td>" + esc(r.item_name) + "</td><td>" + fmt(r.stok) + "</td><td>" + esc(r.unit) + "</td>" +
          '<td><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status) + "</span></td></tr>"
        );
      })
      .join("");
  }

  function renderKebutuhanKritis(rows) {
    var el = $("#kebutuhanKritis");
    if (!rows.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Aman</h4><p>Tidak ada bahan berstatus waspada/kritis saat ini.</p></div></div></article>';
      return;
    }
    el.innerHTML = rows
      .map(function (r) {
        return (
          '<article class="event-card"><div class="event-main"><div><h4>' + esc(r.item_name) + "</h4>" +
          "<p>Stok tersisa: <b>" + fmt(r.stok) + "</b> " + esc(r.unit) + "</p></div>" +
          '<div class="chips"><span class="chip ' + statusPillClass(r.status) + '">' + esc(r.status) + "</span></div></div></article>"
        );
      })
      .join("");
  }

  function renderJadwal(rows) {
    var body = $("#jadwalBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4"><em class="rn-muted">Belum ada produksi hari ini.</em></td></tr>';
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        return (
          "<tr><td>" + esc(r.time) + "</td><td>" + esc(r.meal_name) + "</td><td>" + fmt(r.portions) + "</td>" +
          "<td>" + esc(r.status_label) + "</td></tr>"
        );
      })
      .join("");
  }

  function renderDistribusi(rows) {
    var body = $("#distribusiBody");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4"><em class="rn-muted">Belum ada distribusi hari ini.</em></td></tr>';
      return;
    }
    body.innerHTML = rows
      .map(function (r) {
        return (
          "<tr><td>" + esc(r.tujuan) + "</td><td>" + esc(r.waktu) + "</td><td>" + fmt(r.porsi) + "</td>" +
          "<td>" + esc(r.status_label) + "</td></tr>"
        );
      })
      .join("");
  }

  function renderRelawan(rd) {
    $("#relawanCount").textContent = rd.total + " Relawan";
    $("#relawanFoot").textContent =
      "Aktif " + rd.aktif + " · Istirahat " + rd.istirahat + " · Tidak Aktif " + rd.tidak_aktif;
    var el = $("#relawanList");
    if (!rd.list.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Belum ada relawan</h4><p>Belum ada relawan yang ditugaskan ke posko ini.</p></div></div></article>';
      return;
    }
    el.innerHTML = rd.list
      .map(function (v) {
        return (
          '<article class="event-card"><div class="event-main"><div><h4>' + esc(v.name) + "</h4><p>" + esc(v.role) + "</p></div>" +
          '<div class="chips"><span class="chip">' + esc(v.status_label) + "</span></div></div></article>"
        );
      })
      .join("");
  }

  function renderFuel(rows) {
    var el = $("#fuelGrid");
    if (!rows.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada data gas/BBM tercatat.</p>';
      return;
    }
    el.innerHTML = rows
      .map(function (r) {
        return (
          '<div class="rn-dp-fuel-card"><span>' + esc(r.item_name) + "</span><b>" + fmt(r.stok) + " " + esc(r.unit) + "</b>" +
          '<small class="chip ' + statusPillClass(r.status) + '">' + esc(r.status) + "</small></div>"
        );
      })
      .join("");
  }

  function renderBukti(rows) {
    var el = $("#buktiGrid");
    if (!rows.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada foto bukti dapur.</p>';
      return;
    }
    el.innerHTML = rows
      .map(function (r) {
        var url = r.evidence_url || r.file_url || "";
        return (
          '<a class="rn-bukti-thumb" href="' + esc(url) + '" target="_blank" rel="noopener">' +
          '<img src="' + esc(url) + '" alt="Bukti dapur" loading="lazy"></a>'
        );
      })
      .join("");
  }

  async function loadBoard() {
    statusMsg("Memuat dashboard dapur…");
    var poskoId = getKitchenPoskoId();
    var eventId = getEventId();
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, {
      posko: poskoId,
      disaster_event: eventId || undefined,
    });
    BOARD_CACHE = data;

    var posko = data.posko || {};
    $("#kitchenTitle").textContent = posko.title || posko.name || poskoId;
    $("#kitchenUpdated").textContent = "Kitchen · Diperbarui " + String(data.generated_at || "").slice(11, 16);

    renderKpi(data.totals || {});
    renderTarget(data.target_layanan || {});
    renderDonut(data.produksi_donut || {});
    renderStokBahan(data.stok_bahan || []);
    renderKebutuhanKritis(data.kebutuhan_kritis || []);
    renderJadwal(data.jadwal_masak || []);
    renderDistribusi(data.distribusi_hari_ini_list || []);
    renderRelawan(data.relawan_dapur || { total: 0, aktif: 0, istirahat: 0, tidak_aktif: 0, list: [] });
    renderFuel(data.gas_bbm || []);
    renderBukti(data.bukti || []);

    var seeAll = $("#evidenceSeeAll");
    if (seeAll) {
      seeAll.href =
        "evidence.html?event=" + encodeURIComponent(data.disaster_event || "") +
        "&object_type=posko&object_id=" + encodeURIComponent(posko.name || poskoId);
    }

    statusMsg("Dimuat pukul " + String(data.generated_at || "").slice(11, 16));
  }

  /* ---------- legacy raw panels (unchanged behaviour) ---------- */

  function evidenceLink(objectType, objectId, label) {
    label = label || "Add Evidence";
    if (!objectId) return "";
    var ctx = BOARD_CACHE || {};
    var eventId = ctx.disaster_event || getEventId() || "event-sim-001";
    return (
      '<br><a href="evidence.html?event=' + encodeURIComponent(eventId) +
      "&object_type=" + encodeURIComponent(objectType) +
      "&object_id=" + encodeURIComponent(objectId) +
      '&node_id=' + encodeURIComponent(getKitchenPoskoId()) + '">' + label + "</a>"
    );
  }

  function card(title, body, chip) {
    return (
      '<article class="event-card"><div class="event-main"><div><h4>' + esc(title) + "</h4><p>" + body + "</p></div>" +
      '<div class="chips">' + (chip ? '<span class="chip warning">' + esc(chip) + "</span>" : "") + "</div></div></article>"
    );
  }

  function renderLegacyStock(items) {
    var el = document.getElementById("kitchenStock");
    if (!el) return;
    document.getElementById("stockLegacyCount").textContent = items.length;
    el.innerHTML = items.length
      ? items
          .map(function (s) {
            var qty = s.current_quantity ?? s.quantity ?? s.effective_quantity ?? 0;
            return card(safe(s.item_name), "Current stock: <b>" + safe(qty) + "</b> " + safe(s.unit), safe(s.unit));
          })
          .join("")
      : card("Belum ada stok", "Transfer bahan dari Posko Logistik dulu.", "empty");
  }

  function renderLegacyMeals(items) {
    var el = document.getElementById("mealProductions");
    if (!el) return;
    el.innerHTML = items.length
      ? items
          .map(function (m) {
            var id = rowId(m);
            return card(
              safe(m.meal_name),
              "Portions: " + safe(m.portions) + "<br>Target: " + safe(m.target_distribution_location) +
                "<br>Time: " + safe(m.production_time) + "<br>" + safe(m.notes) + evidenceLink("meal_production", id),
              safe(m.status || m.production_status)
            );
          })
          .join("")
      : card("Belum ada produksi makanan", "Catat produksi makanan pertama.", "empty");
  }

  function renderLegacyMovements(items) {
    var el = document.getElementById("kitchenMovements");
    if (!el) return;
    el.innerHTML = items.length
      ? items
          .map(function (m) {
            var id = rowId(m);
            var created = m.created_at || m.creation || m.observed_at || "";
            return card(
              safe(m.item_name),
              safe(m.movement_type) + " · " + safe(m.movement_direction) + "<br>" + safe(m.quantity) + " " +
                safe(m.unit) + "<br>" + safe(m.notes) + evidenceLink("stock_movement", id),
              created ? String(created).slice(0, 16).replace("T", " ") : safe(id)
            );
          })
          .join("")
      : card("Belum ada movement", "Belum ada pergerakan stok dapur.", "empty");
  }

  async function loadLegacy() {
    var poskoId = getKitchenPoskoId();
    var raw = await window.RN_FRAPPE.call(LEGACY_METHOD, { posko: poskoId });
    var ctx = raw || {};
    LEGACY_CACHE = {
      posko: ctx.posko || { name: poskoId },
      stock_summary: ctx.stock_summary || [],
      stock_movements: ctx.ingredient_usages || ctx.stock_movements || [],
      meal_productions: ctx.productions || ctx.meal_productions || [],
    };

    renderLegacyStock(LEGACY_CACHE.stock_summary);
    renderLegacyMeals(LEGACY_CACHE.meal_productions);
    renderLegacyMovements(LEGACY_CACHE.stock_movements);

    var form = document.getElementById("mealForm");
    if (form && form.posko_id) form.posko_id.value = poskoId;
  }

  function setupMealForm() {
    var form = document.getElementById("mealForm");
    if (!form) return;

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (!LEGACY_CACHE) await loadLegacy();

      var eventId = (BOARD_CACHE && BOARD_CACHE.disaster_event) || null;

      var ingredients = [{
        item_name: form.ingredient_item_name.value.trim(),
        quantity: Number(form.ingredient_quantity.value || 0),
        unit: form.ingredient_unit.value.trim(),
      }];

      var payload = {
        posko: form.posko_id.value.trim(),
        meal_name: form.meal_name.value.trim(),
        portions: Number(form.portions.value || 0),
        ingredients: ingredients,
        disaster_event: eventId,
        production_time: form.production_time.value.trim(),
        target_distribution_location: form.target_distribution_location.value.trim(),
        notes: form.notes.value.trim(),
      };

      statusMsg("Saving meal production...");
      await window.RN_FRAPPE.call("rescue_net.api_kitchen.create_production", payload, { method: "POST" });
      statusMsg("Meal production saved.");
      form.reset();
      await refreshAll();
    });
  }

  async function refreshAll() {
    await Promise.all([
      loadBoard().catch(function (err) { statusMsg("Gagal memuat dashboard: " + err.message); }),
      loadLegacy().catch(function (err) { console.error("[dapur-umum legacy]", err); }),
    ]);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) {
      statusMsg("Frappe client tidak tersedia.");
      return;
    }

    setupDrill();
    setupMealForm();

    var btn = document.getElementById("refreshKitchen");
    if (btn) btn.addEventListener("click", function () { refreshAll(); });

    refreshAll();
  });
})();
