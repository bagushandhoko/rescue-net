/* ============================================================
 * New dashboard (matches manajemen alat kerja.png): calls
 * rescue_net.api_resource_tools.tools_board (guest, event-wide).
 * Legacy form + list panel below (kept inside <details>) still
 * calls api_resource_tools.dashboard / create_work_tool_request.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_resource_tools.tools_board";
  var BOARD_CACHE = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("id-ID"); }
  function getEventId() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
  function shortTime(s) { return s ? String(s).slice(11, 16) : "-"; }
  function shortDate(s) { return s ? String(s).slice(0, 10) : "-"; }

  var DRILL_TITLES = {
    alat_tersedia: "Alat Tersedia", kebutuhan_alat: "Kebutuhan Alat",
    operator_aktif: "Operator Aktif", dispatch_berjalan: "Dispatch Berjalan",
    bbm_kritis: "BBM Kritis", alat_rusak: "Alat Rusak",
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
    if (!BOARD_CACHE) return;
    $("#alatKerjaDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    var items = ((BOARD_CACHE.kpi_items || {})[kind + "_items"]) || [];
    $("#alatKerjaDrillSub").textContent = items.length + " item";
    $("#alatKerjaDrillBody").innerHTML = drillItemsHtml(items);
    $("#alatKerjaDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#alatKerjaDrill").hidden = true; document.body.style.overflow = ""; }

  function renderKpi(t) {
    $("#kpiAlatTersedia").textContent = fmt(t.alat_tersedia);
    $("#kpiKebutuhanAlat").textContent = fmt(t.kebutuhan_alat);
    $("#kpiOperatorAktif").textContent = fmt(t.operator_aktif);
    $("#kpiDispatchBerjalan").textContent = fmt(t.dispatch_berjalan);
    $("#kpiBbmKritis").textContent = fmt(t.bbm_kritis);
    $("#kpiAlatRusak").textContent = fmt(t.alat_rusak);
  }

  function renderCategories(cats) {
    var el = $("#categoryGrid");
    if (!cats || !cats.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada Resource Profile alat kerja untuk event ini.</p>';
      return;
    }
    el.innerHTML = cats.map(function (c) {
      return (
        '<div class="rn-ak-cat-tile">' +
        '<div class="rn-ak-cat-tile-head"><b>' + esc(c.label) + "</b><strong>" + fmt(c.total) + "</strong></div>" +
        '<div class="rn-ak-cat-legend">' +
        '<span><i class="rn-ak-dot-ready"></i>Ready ' + fmt(c.ready) + "</span>" +
        '<span><i class="rn-ak-dot-assigned"></i>Assigned ' + fmt(c.assigned) + "</span>" +
        '<span><i class="rn-ak-dot-maintenance"></i>Maintenance ' + fmt(c.maintenance) + "</span>" +
        '<span><i class="rn-ak-dot-critical"></i>Critical ' + fmt(c.critical) + "</span>" +
        "</div></div>"
      );
    }).join("");
  }

  function renderOperators(ops) {
    var el = $("#operatorList");
    if (!ops || !ops.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada operator dengan dispatch aktif.</p>';
      return;
    }
    el.innerHTML = ops.map(function (o) {
      return (
        '<div class="rn-ak-op-row"><span><b>' + esc(o.name) + "</b><small>" + esc(o.skill) + " · " + esc(o.location) + "</small></span>" +
        '<span class="chip">' + esc(o.status_label) + "</span></div>"
      );
    }).join("");
  }

  function renderMatches(matches) {
    var el = $("#matchList");
    if (!matches || !matches.length) {
      el.innerHTML = '<p class="rn-muted">Semua kebutuhan alat sudah tercocokkan atau tidak ada yang terbuka.</p>';
      return;
    }
    el.innerHTML = matches.map(function (m) {
      var candText = m.candidate_count > 0
        ? "✓ " + fmt(m.candidate_count) + " kandidat tersedia (" + esc(m.candidate_resource) + " · " + esc(m.candidate_location) + ")"
        : "✗ Belum ada alat available yang cocok";
      return (
        '<div class="rn-ak-match-row"><div class="rn-ak-match-head"><b>' + esc(m.tool_name) + " · " + fmt(m.quantity) + " unit</b>" +
        '<span class="chip ' + (m.priority === "critical" ? "danger" : m.priority === "urgent" ? "warning" : "") + '">' + esc(m.priority_label) + "</span></div>" +
        '<small class="rn-muted">' + esc(m.location) + " · " + esc(m.needed_for || "") + "</small>" +
        '<div class="rn-ak-match-cand' + (m.candidate_count > 0 ? " ok" : "") + '">' + candText + "</div></div>"
      );
    }).join("");
  }

  function renderDispatch(rows) {
    var body = $("#dispatchBody");
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="6"><em class="rn-muted">Belum ada dispatch alat untuk event ini.</em></td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (r) {
      var cls = r.status === "completed" ? "ok" : (r.status === "cancelled" ? "danger" : (r.status === "in_use" || r.status === "deployed" ? "warning" : ""));
      return (
        "<tr><td><b>" + esc(r.tool_name) + "</b></td><td>" + esc(r.operator) + "</td><td>" + esc(r.destination) + "</td>" +
        '<td><span class="chip ' + cls + '">' + esc(r.status_label) + "</span></td>" +
        "<td>" + shortDate(r.deployed_at) + " " + shortTime(r.deployed_at) + "</td>" +
        "<td>" + (r.completed_at ? shortDate(r.completed_at) + " " + shortTime(r.completed_at) : "-") + "</td></tr>"
      );
    }).join("");
  }

  function renderSites(sites) {
    var el = $("#siteList");
    if (!sites || !sites.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada dispatch dengan lokasi tujuan tercatat.</p>';
      return;
    }
    el.innerHTML = sites.map(function (s) {
      return (
        '<div class="rn-ak-op-row" style="flex-direction:column;align-items:stretch;gap:4px;">' +
        '<span><b>' + esc(s.location) + "</b><small>" + fmt(s.completed) + "/" + fmt(s.total) + " dispatch selesai</small></span>" +
        '<div style="height:6px;background:var(--line);border-radius:4px;overflow:hidden;">' +
        '<div style="height:100%;width:' + s.progress_pct + '%;background:var(--coral,#e8835d);"></div></div></div>'
      );
    }).join("");
  }

  function renderFuel(fuel) {
    var body = $("#fuelBody");
    if (!fuel || !fuel.length) {
      body.innerHTML = '<tr><td colspan="3"><em class="rn-muted">Belum ada Stock Observation BBM/oli untuk event ini.</em></td></tr>';
      return;
    }
    body.innerHTML = fuel.map(function (f) {
      var cls = f.status === "kritis" ? "danger" : (f.status === "waspada" ? "warning" : "ok");
      return (
        "<tr><td>" + esc(f.item_name) + "</td><td>" + fmt(f.stok) + " " + esc(f.unit) + "</td>" +
        '<td><span class="chip ' + cls + '">' + esc(f.status) + "</span></td></tr>"
      );
    }).join("");
  }

  function renderAssets(rows) {
    var body = $("#assetBody");
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="3"><em class="rn-muted">Belum ada Resource Profile.</em></td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (r) {
      return "<tr><td><code>" + esc(r.code) + "</code></td><td>" + esc(r.resource_name) + " · " + esc(r.category) + "</td><td>" + esc(r.status) + "</td></tr>";
    }).join("");
  }

  function renderBlockers(rows) {
    var el = $("#blockerList");
    if (!rows || !rows.length) {
      el.innerHTML = '<article class="event-card"><div class="event-main"><div><h4>Aman</h4><p>Tidak ada hambatan alat kerja saat ini.</p></div></div></article>';
      return;
    }
    el.innerHTML = rows.map(function (r) {
      return (
        '<article class="event-card"><div class="event-main"><div><h4>⚠ ' + esc(r.label) + "</h4><p>" + esc(r.detail) + "</p></div>" +
        '<div class="chips"><span class="chip ' + (r.severity === "critical" ? "danger" : "warning") + '">' + esc(r.severity) + "</span></div></div></article>"
      );
    }).join("");
  }

  function renderSummary(s) {
    var el = $("#summaryGrid");
    el.innerHTML =
      '<div class="rn-ak-summary-tile"><span>Penggunaan</span><b>' + s.penggunaan_pct + '%</b></div>' +
      '<div class="rn-ak-summary-tile"><span>Jam Operasional</span><b>' + s.jam_operasional + ' jam</b></div>' +
      '<div class="rn-ak-summary-tile"><span>Dispatch Selesai</span><b>' + fmt(s.dispatch_selesai) + '</b></div>' +
      '<div class="rn-ak-summary-tile"><span>Kerusakan Baru</span><b>' + fmt(s.kerusakan_baru) + '</b></div>';
  }

  var OBJECT_TYPE_METHOD = "rescue_net.api_resource_tools.work_objects_board";
  var CREATE_OBJECT_METHOD = "rescue_net.api_resource_tools.create_work_object";

  function renderGroups(groups) {
    var el = $("#groupList");
    if (!groups || !groups.length) {
      el.innerHTML = '<p class="rn-muted" style="padding:8px 10px;">Belum ada Resource Profile untuk dikelompokkan.</p>';
      return;
    }
    el.innerHTML = groups.map(function (g) {
      var bb = g.base_breakdown || [];
      var totalCol = bb.length
        ? bb.map(function (b) {
            var q = (b.measurable || 0) + (b.estimated || 0);
            var approx = b.estimated && !b.measurable;
            return '<span class="rn-ak-unit-chip"' + (approx ? ' title="perkiraan"' : "") + ">" +
              (approx ? "±" : "") + fmt(q) + " " + esc(b.base_unit || "") + "</span>";
          }).join("")
        : (g.same_unit
            ? fmt(g.total_qty) + " " + esc((g.unit_breakdown[0] || {}).unit || "")
            : g.unit_breakdown.map(function (u) { return '<span class="rn-ak-unit-chip">' + fmt(u.qty) + " " + esc(u.unit) + "</span>"; }).join(""));
      if (g.unmeasurable_count)
        totalCol += ' <span class="chip warning">' + fmt(g.unmeasurable_count) + " belum terukur</span>";
      var sourceLabel = g.source === "manual" ? "Manual" : g.source === "ai" ? "AI" : g.source === "rule" ? "Aturan" : "-";
      return (
        '<div class="rn-ak-group-row"><b>' + esc(g.group) + "</b>" +
        "<span>" + fmt(g.item_count) + " item</span>" +
        "<span>" + totalCol + "</span>" +
        "<span>" + fmt(g.posko_spread) + " lokasi</span>" +
        '<span><span class="chip">' + esc(sourceLabel) + (g.avg_confidence ? " " + g.avg_confidence + "%" : "") + "</span></span></div>"
      );
    }).join("");
  }

  var STATUS_CHIP = { open: "warning", in_progress: "", resolved: "ok" };
  var STATUS_LABEL = { open: "Terbuka", in_progress: "Dikerjakan", resolved: "Selesai" };

  var CONDITIONS = [];
  var TO_REQUEST_METHOD = "rescue_net.api_resource_tools.create_requests_from_work_object";

  function predRow(p) {
    var days = p.work_days ? " · " + fmt(p.work_days) + " hari kerja" : "";
    var stock = p.gap > 0
      ? '<span class="chip danger">Kurang ' + fmt(p.gap) + " (siap " + fmt(p.ready_available) + ")</span>"
      : '<span class="chip ok">Siap ' + fmt(p.ready_available) + "</span>";
    var asked = p.requested > 0
      ? '<span class="chip">Diminta ' + fmt(p.requested) + "</span>"
      : '<span class="chip warning">Belum diminta</span>';
    return (
      '<div class="rn-ak-pred-row"><span><b>' + esc(p.label) + " × " + fmt(p.predicted_qty) + " " + esc(p.unit || "") + days +
      "</b><small>" + esc(p.basis) + "</small></span><span>" + stock + " " + asked + "</span></div>"
    );
  }

  function renderObjects(objects) {
    var el = $("#objectList");
    if (!objects || !objects.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada kondisi lapangan dicatat. Mulai dari form di samping: ukuran fisik kondisi, bukan daftar alat.</p>';
      return;
    }
    el.innerHTML = objects.map(function (o) {
      var preds = (o.predictions || []).map(predRow).join("") ||
        '<p class="rn-muted" style="font-size:11px;">Belum ada aturan perkiraan alat untuk jenis kondisi ini — minta alat langsung di bagian bawah.</p>';
      var days = o.work_days_target ? " · target " + fmt(o.work_days_target) + " hari kerja" : "";
      var action = (o.status === "resolved" || !NEEDS_FIRST_BACKEND) ? "" : (o.to_request > 0
        ? '<button class="btn primary mini" type="button" data-to-request="' + esc(o.name) + '">Jadikan Kebutuhan Alat</button>'
        : (o.predictions || []).length ? "<small>Semua alat dari perkiraan ini sudah diminta — kelola di Kebutuhan Alat &amp; Manajemen.</small>" : "");
      return (
        '<div class="rn-ak-object-card"><div class="rn-ak-object-head"><b>' + esc(o.title) + "</b>" +
        '<span class="chip ' + (STATUS_CHIP[o.status] || "") + '">' + (STATUS_LABEL[o.status] || o.status) + "</span></div>" +
        '<div class="rn-ak-object-meta">' + esc(o.object_type_label) + " · " + fmt(o.size_value) + " " + esc(o.size_unit || "") + days +
        " · " + esc(o.location || "-") + "</div>" +
        '<div class="rn-ak-object-preds">' + preds + "</div>" +
        '<div class="rn-ak-object-actions">' + action + '<span class="rn-pr-add-msg" data-to-request-msg="' + esc(o.name) + '"></span></div></div>'
      );
    }).join("");
  }

  function fillConditionSelect(conditions) {
    var sel = document.getElementById("objectTypeSelect");
    if (!sel || !conditions.length) return;
    CONDITIONS = conditions;
    var cur = sel.value;
    sel.innerHTML = conditions.map(function (c) {
      return '<option value="' + esc(c.object_type) + '">' + esc(c.label) + "</option>";
    }).join("");
    if (cur) sel.value = cur;
    applyCondition();
  }

  function applyCondition() {
    var form = document.getElementById("objectForm");
    var c = CONDITIONS.find(function (x) { return x.object_type === form.object_type.value; });
    if (!c) return;
    $("#sizeLabel").textContent = "Ukuran fisik: " + c.measure;
    form.size_unit.value = c.unit || "";
    $("#daysField").hidden = !c.time_based;
    if (c.time_based && !form.work_days_target.value) form.work_days_target.value = c.default_days || "";
  }

  async function loadObjectPoskos() {
    var sel = document.getElementById("objectPoskoSelect");
    if (!sel) return;
    var res = await window.RN_FRAPPE.call("rescue_net.api_control_centre.event_poskos", { disaster_event: getEventId() });
    var points = Array.isArray(res) ? res : (res.points || []);
    var manages = (res.viewer && res.viewer.manages) || [];
    var mine = points.filter(function (pt) { return manages.indexOf(pt.posko_id || pt.id || pt.name) !== -1; });
    sel.innerHTML = '<option value="">— Control Centre —</option>' + mine.map(function (pt) {
      var id = pt.posko_id || pt.id || pt.name;
      return '<option value="' + esc(id) + '">' + esc(pt.name || id) + "</option>";
    }).join("");
    if (mine.length === 1) sel.value = mine[0].posko_id || mine[0].id || mine[0].name;
  }

  // backend before the needs-first release: no condition catalogue, no
  // create_requests_from_work_object — show the old condition types, no button
  var LEGACY_CONDITIONS = [
    { object_type: "longsoran", label: "Longsoran", unit: "m3", measure: "volume material", default_days: null, time_based: false },
    { object_type: "jembatan_putus", label: "Jembatan putus", unit: "m", measure: "panjang bentang", default_days: null, time_based: false },
    { object_type: "puing_berat", label: "Puing berat", unit: "m2", measure: "luas puing", default_days: null, time_based: false },
    { object_type: "pohon_tumbang", label: "Pohon tumbang", unit: "pohon", measure: "jumlah pohon", default_days: null, time_based: false },
    { object_type: "akses_terendam", label: "Akses terendam", unit: "m2", measure: "luas genangan akses", default_days: null, time_based: false },
    { object_type: "lainnya", label: "Lainnya", unit: "", measure: "ukuran", default_days: null, time_based: false }
  ];
  var NEEDS_FIRST_BACKEND = true;

  async function loadObjects() {
    var data = await window.RN_FRAPPE.call(OBJECT_TYPE_METHOD, { disaster_event: getEventId() });
    NEEDS_FIRST_BACKEND = Array.isArray(data.conditions);
    fillConditionSelect(NEEDS_FIRST_BACKEND ? data.conditions : LEGACY_CONDITIONS);
    var open = (data.objects || []).filter(function (o) { return o.status !== "resolved"; }).length;
    var kpi = document.getElementById("kpiKondisiLapangan");
    if (kpi) kpi.textContent = fmt(open);
    renderObjects(data.objects || []);
  }

  function setupObjectForm() {
    var form = document.getElementById("objectForm");
    if (!form) return;
    fillConditionSelect(LEGACY_CONDITIONS);  // until the board answers
    form.object_type.addEventListener("change", function () {
      form.work_days_target.value = "";
      applyCondition();
    });
    loadObjectPoskos().catch(function () {});
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#objectFormMsg");
      msg.textContent = "Menyimpan & menghitung alat…";
      try {
        await window.RN_FRAPPE.call(CREATE_OBJECT_METHOD, {
          title: form.title.value.trim(),
          object_type: form.object_type.value,
          size_value: Number(form.size_value.value),
          size_unit: form.size_unit.value.trim(),
          work_days_target: $("#daysField").hidden ? null : (Number(form.work_days_target.value) || null),
          posko: form.posko.value || null,
          location: form.location.value.trim(),
          notes: form.notes.value.trim(),
          disaster_event: getEventId(),
        }, { method: "POST" });
        var keepType = form.object_type.value;
        form.reset();
        form.object_type.value = keepType;
        applyCondition();
        msg.textContent = "Tersimpan — lihat perkiraan alat di daftar.";
        await loadObjects();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
    document.addEventListener("click", async function (e) {
      var btn = e.target.closest("[data-to-request]");
      if (!btn) return;
      var id = btn.getAttribute("data-to-request");
      var out = document.querySelector('[data-to-request-msg="' + id + '"]');
      btn.disabled = true;
      try {
        var r = await window.RN_FRAPPE.call(TO_REQUEST_METHOD, { work_object: id }, { method: "POST" });
        if (out) out.textContent = r.message || "";
        await loadObjects();
        await loadBoard();
      } catch (err) {
        btn.disabled = false;
        if (out) out.textContent = "Gagal: " + (err && err.message || err);
      }
    });
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    BOARD_CACHE = data;
    $("#workToolUpdated").textContent = "Alat Kerja · Diperbarui " + shortTime(data.generated_at);

    renderKpi(data.totals || {});
    renderCategories(data.categories || []);
    renderOperators(data.operators || []);
    renderMatches(data.matches || []);
    renderDispatch(data.dispatch || []);
    renderSites(data.sites || []);
    renderFuel(data.fuel || []);
    renderAssets(data.asset_registry || []);
    renderBlockers(data.blockers || []);
    renderSummary(data.summary || {});
    renderGroups(data.groups || []);
    $("#groupsNote").textContent = data.groups_note || "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    document.querySelectorAll(".rn-ak-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#alatKerjaDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });
    setupObjectForm();
    loadObjects().catch(function (err) { console.error("[work objects board]", err); });
    loadBoard().catch(function (err) { console.error("[alat kerja board]", err); });
  });
})();

const DISASTER_ID =
  new URLSearchParams(
    location.search
  ).get("event") ||
  "event-sim-001";


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function statusMsg(msg) {
  const el =
    document.getElementById(
      "workToolStatus"
    );

  if (el) {
    el.textContent = msg;
  }
}


function card(
  title,
  body,
  chip = ""
) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(title)}</h4>
          <p>${body}</p>
        </div>

        <div class="chips">
          ${
            chip
              ? `<span class="chip warning">${safe(chip)}</span>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}


function renderSummary(ctx) {
  const el =
    document.getElementById(
      "workToolSummary"
    );

  if (!el) return;

  const requests =
    ctx.requests || [];

  const resources =
    ctx.resources || [];

  const deployments =
    ctx.deployments || [];

  el.innerHTML = `
    <div>
      <span>Requests</span>
      <b>${requests.length}</b>
    </div>

    <div>
      <span>Resources</span>
      <b>${resources.length}</b>
    </div>

    <div>
      <span>Deployments</span>
      <b>${deployments.length}</b>
    </div>
  `;
}


function renderRequests(items) {
  const el =
    document.getElementById(
      "workToolRequests"
    );

  if (!el) return;

  el.innerHTML =
    items.length
      ? items.map(r => card(
          r.tool_name,
          `${safe(r.quantity)} ${safe(r.unit)}<br>` +
          `Location: ${safe(r.location)}<br>` +
          `Needed for: ${safe(r.needed_for)}<br>` +
          `Requested by: ${safe(r.requested_by_type)} / ` +
          `${safe(r.requested_by_id)}`,
          r.request_status ||
          r.priority
        )).join("")
      : card(
          "Belum ada Work Tool Request",
          "Belum ada permintaan alat kerja.",
          "empty"
        );
}


async function loadWorkTools() {
  statusMsg(
    "Loading Resource Tools..."
  );

  const ctx =
    await RN_FRAPPE.call(
      "rescue_net.api_resource_tools.dashboard",
      {
        disaster_event:
          DISASTER_ID
      }
    );

  renderSummary(ctx);
  renderRequests(
    ctx.requests || []
  );

  statusMsg(
    "Loaded from Frappe"
  );
}


function setupForm() {
  const form =
    document.getElementById(
      "workToolForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_resource_tools." +
        "create_work_tool_request",
        {
          disaster_event:
            DISASTER_ID,

          requested_by_type:
            form.requested_by_type.value ||
            "posko",

          requested_by_id:
            form.requested_by_id.value
              .trim(),

          tool_name:
            form.tool_name.value.trim(),

          tool_type:
            form.tool_type.value.trim(),

          quantity:
            Number(
              form.quantity.value || 1
            ),

          unit:
            form.unit.value.trim() ||
            "unit",

          location:
            form.location.value.trim(),

          needed_for:
            form.needed_for.value.trim(),

          priority:
            form.priority.value ||
            "normal",

          required_operator_skill:
            form.required_operator_skill
              .value
              .trim(),

          notes:
            form.notes.value.trim()
        },
        {
          method: "POST"
        }
      );

      statusMsg(
        "Work Tool Request saved."
      );

      form.reset();

      await loadWorkTools();
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      statusMsg(
        "Frappe client tidak tersedia."
      );
      return;
    }

    setupForm();

    const btn =
      document.getElementById(
        "refreshWorkTools"
      );

    if (btn) {
      btn.addEventListener(
        "click",
        () =>
          loadWorkTools().catch(
            err =>
              statusMsg(err.message)
          )
      );
    }

    loadWorkTools().catch(
      err =>
        statusMsg(err.message)
    );
  }
);
