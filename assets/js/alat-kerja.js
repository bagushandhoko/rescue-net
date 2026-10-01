/* ============================================================
 * Kebutuhan & Manajemen Alat Kerja (layout of manajemen alat kerja.png):
 *   row 1  Inventaris per Kategori | Operator | Matching Kebutuhan Alat
 *   row 2  Jadwal Dispatch | Lokasi Kerja | BBM + QR / Asset Tracking
 *   row 3  Hambatan Alat Kerja | Ringkasan Hari Ini
 * Matching Kebutuhan = needs-first: field conditions (RN Work Object,
 * work_objects_board — tools derived from the physical size, rule per
 * number in the drill) followed by open tool requests (tools_board).
 * Legacy direct-request form + list below (inside <details>) still
 * calls api_resource_tools.dashboard / create_work_tool_request.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_resource_tools.tools_board";
  var BOARD_CACHE = null;
  var OBJECTS = [];

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function getEventId() { return window.RNUI.eventId(); }
  function shortTime(s) { return s ? String(s).slice(11, 16) : "-"; }
  function dayMonth(s) { var d = String(s || "").slice(0, 10).split("-"); return d.length === 3 ? d[2] + "/" + d[1] : ""; }
  function icon(name) { return window.RNIcon ? window.RNIcon(name) : ""; }
  function initials(name) {
    return esc(String(name || "?").replace(/^(Sertu|Serka|Kopda|Pratu|Praka|Lettu|Letda|Kapten|Mayor|Bripka|Briptu|Aiptu|Ipda)\s+/i, "")
      .split(/\s+/).map(function (w) { return w.charAt(0); }).join("").slice(0, 2).toUpperCase());
  }

  // category / tool name → line icon
  var TOOL_ICON = [
    [/ekskavator|excavator|buldoser|bulldozer|backhoe/i, "excavator"], [/genset|generator/i, "generator"],
    [/pompa|pump/i, "pump"], [/forklift/i, "forklift"], [/chainsaw|gergaji/i, "chainsaw"],
    [/perahu|boat|rubber/i, "boat"], [/truk|truck|pickup|kendaraan|motor/i, "truck"],
    [/solar|bensin|pertalite|bbm/i, "bbm"], [/oli/i, "droplet"], [/fasilitas|rumah/i, "building"],
    [/barang|bantuan|selimut/i, "box"],
  ];
  function toolIcon(text) {
    for (var i = 0; i < TOOL_ICON.length; i++) if (TOOL_ICON[i][0].test(text || "")) return TOOL_ICON[i][1];
    return "wrench";
  }

  /* mock-up panels show the first rows; the header "Lihat semua" link expands the rest */
  function limitRows(el, shown) {
    var rows = el.children;
    for (var i = 0; i < rows.length; i++) rows[i].classList.toggle("rn-ak-extra", i >= shown);
    el.classList.remove("is-all");
    var link = document.querySelector('[data-ak-more="' + el.id + '"]');
    if (link) {
      link.hidden = rows.length <= shown;
      link.setAttribute("data-label", link.getAttribute("data-label") || link.textContent);
      link.textContent = link.getAttribute("data-label");
    }
  }

  var DRILL_TITLES = {
    alat_tersedia: "Alat Tersedia", kebutuhan_alat: "Kebutuhan Alat",
    operator_aktif: "Operator Aktif", dispatch_berjalan: "Dispatch Berjalan",
    bbm_kritis: "BBM Kritis", alat_rusak: "Alat Rusak",
  };

  /* PIC of the posko (BBM kritis): name/role/phone only when the backend sends it
     (posko_contacts_visible — same rule as Posko Detail), else a login hint */
  function loginLink(text) {
    return '<a href="auth.html?next=' + encodeURIComponent(location.pathname + location.search) + '">' + text + "</a>";
  }

  function personHtml(c) {
    return '<div class="rn-ak-contact"><span><small>' + esc(c.source || "Kontak") + "</small><b>" + esc(c.name || "-") + "</b>" +
      (c.role ? " · " + esc(c.role) : "") + "</span>" +
      (c.phone ? '<a href="tel:' + esc(c.phone) + '">' + esc(c.phone) + "</a>" : "") +
      (c.whatsapp_url ? '<a href="' + esc(c.whatsapp_url) + '" target="_blank" rel="noopener">WhatsApp</a>' : "") +
      (c.email ? '<a href="mailto:' + esc(c.email) + '">' + esc(c.email) + "</a>" : "") +
      (c.note ? "<small>" + esc(c.note) + "</small>" : "") + "</div>";
  }

  function contactHtml(it) {
    var list = it.contacts || (it.contact ? [it.contact] : null);
    if (list && list.length) return list.map(personHtml).join("");
    if (it.contact_locked) {
      return '<div class="rn-ak-contact is-locked">Kontak hanya untuk petugas posko / organisasi terkait — ' + loginLink("login") + "</div>";
    }
    if (list) {
      var logged = window.RN_SESSION && window.RN_SESSION.getUser && window.RN_SESSION.getUser();
      return '<div class="rn-ak-contact is-locked">Posko ini belum mencatat PIC.' +
        (logged ? "" : " " + loginLink("Login") + " untuk melihat petugas / pengurus organisasinya.") + "</div>";
    }
    return "";
  }

  function drillItemsHtml(items) {
    if (!items || !items.length) return '<p class="rn-muted">Tidak ada data untuk ditampilkan.</p>';
    return items.map(function (it) {
      var row =
        '<a class="rn-ba-ditem" href="' + esc(it.href || "#") + '">' +
        "<span><b>" + esc(it.title) + "</b><small>" + esc(it.sub || "") + "</small></span>" +
        (it.href ? '<span class="rn-ba-ditem-go">→</span>' : "") + "</a>";
      var contact = contactHtml(it);
      return contact ? '<div class="rn-ak-ditem">' + row + contact + "</div>" : row;
    }).join("");
  }

  function fuelItem(f) {
    return { title: f.item_name, sub: (f.posko_name ? f.posko_name + " · " : "") + "Stok " + fmt(f.stok) + " " + (f.unit || "") + " tersisa",
      href: f.href || "", contact: f.contact, contacts: f.contacts, contact_locked: f.contact_locked };
  }

  function showDrill(title, sub, html) {
    $("#alatKerjaDrillTitle").textContent = title;
    $("#alatKerjaDrillSub").textContent = sub;
    $("#alatKerjaDrillBody").innerHTML = html;
    $("#alatKerjaDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }

  function openDrill(kind) {
    if (!BOARD_CACHE) return;
    var items = ((BOARD_CACHE.kpi_items || {})[kind + "_items"]) || [];
    showDrill(DRILL_TITLES[kind] || kind, items.length + " item", drillItemsHtml(items));
  }
  function closeDrill() { $("#alatKerjaDrill").hidden = true; document.body.style.overflow = ""; }

  function openAssets() {
    var rows = (BOARD_CACHE && BOARD_CACHE.asset_registry) || [];
    showDrill("QR / Asset Tracking", rows.length + " aset · Kode Aset dari Resource Profile",
      drillItemsHtml(rows.map(function (r) {
        return { title: r.resource_name, sub: r.code + " · " + r.category + " · " + r.status + (r.location ? " · " + r.location : "") };
      })));
  }

  function renderKpi(t) {
    $("#kpiAlatTersedia").textContent = fmt(t.alat_tersedia);
    $("#kpiKebutuhanAlat").textContent = fmt(t.kebutuhan_alat);
    $("#kpiOperatorAktif").textContent = fmt(t.operator_aktif);
    $("#kpiDispatchBerjalan").textContent = fmt(t.dispatch_berjalan);
    $("#kpiBbmKritis").textContent = fmt(t.bbm_kritis);
    $("#kpiAlatRusak").textContent = fmt(t.alat_rusak);
  }

  /* tile: name · large tool icon · "N Unit" + "x Tersedia"; status split in the title */
  function renderCategories(cats) {
    var el = $("#categoryGrid");
    if (!cats || !cats.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada Resource Profile alat kerja untuk event ini.</p>';
      return;
    }
    el.innerHTML = cats.map(function (c) {
      var split = "Ready " + c.ready + " · Assigned " + c.assigned + " · Maintenance " + c.maintenance + " · Critical " + c.critical;
      var seg = function (cls, n) { return n ? '<i class="' + cls + '" style="flex:' + n + '"></i>' : ""; };
      return (
        '<div class="rn-ak-cat-tile" title="' + esc(split) + '">' +
        "<b>" + esc(c.label) + "</b>" +
        '<span class="rn-ak-cat-art">' + icon(toolIcon(c.category + " " + c.label)) + "</span>" +
        '<span class="rn-ak-cat-bar">' + seg("rn-ak-dot-ready", c.ready) + seg("rn-ak-dot-assigned", c.assigned) +
        seg("rn-ak-dot-maintenance", c.maintenance) + seg("rn-ak-dot-critical", c.critical) + "</span>" +
        '<span class="rn-ak-cat-foot"><span><b>' + fmt(c.total) + "</b> Unit</span><em>" + fmt(c.ready) + " Tersedia</em></span>" +
        "</div>"
      );
    }).join("");
    limitRows(el, 6);
  }

  var OP_CLS = { deployed: "ok", in_use: "ok", reserved: "info", completed: "", cancelled: "danger" };

  function renderOperators(ops) {
    var el = $("#operatorList");
    if (!ops || !ops.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada operator dengan dispatch aktif.</p>';
      return;
    }
    el.innerHTML = ops.map(function (o) {
      return (
        '<div class="rn-ak-op-row"><span class="rn-kom-op-av">' + initials(o.name) + "</span>" +
        '<span class="rn-ak-op-id"><b>' + esc(o.name) + "</b><small>" + esc(o.skill) + "</small></span>" +
        '<span class="chip ' + (OP_CLS[o.status] || "") + '">' + esc(o.status_label) + "</span>" +
        '<span class="rn-ak-op-job"><small>Penugasan</small>' + esc(o.location || "-") + "</span></div>"
      );
    }).join("");
    limitRows(el, 5);
  }

  /* ---------- Matching Kebutuhan Alat: field conditions first, then open requests ---------- */
  var STATUS_CHIP = { open: "warning", in_progress: "info", resolved: "ok" };
  var STATUS_LABEL = { open: "Terbuka", in_progress: "Dikerjakan", resolved: "Selesai" };
  var PRIO_CHIP = { critical: "danger", urgent: "warning" };

  function needButton(ok, text, title) {
    return '<span class="rn-ak-need-st ' + (ok ? "ok" : "bad") + '" title="' + esc(title || "") + '">' +
      (ok ? "✓ " : "") + esc(text) + "</span>";
  }

  function objectRow(o, i) {
    var preds = o.predictions || [];
    var butuh = preds.length
      ? preds.map(function (p) { return esc(p.label) + " (" + fmt(p.predicted_qty) + ")"; }).join(", ")
      : "belum ada aturan perkiraan alat";
    var gap = preds.reduce(function (a, p) { return a + (p.gap > 0 ? p.gap : 0); }, 0);
    var st = !preds.length ? "" : (gap > 0
      ? needButton(false, "Kurang " + fmt(gap), "alat siap pakai belum cukup")
      : needButton(true, "Cocok", "alat siap pakai mencukupi"));
    var action = (o.status !== "resolved" && NEEDS_FIRST_BACKEND && o.to_request > 0)
      ? '<button class="rn-ak-mini" type="button" data-requires-role-action="create_work_tool" data-to-request="' + esc(o.name) + '">Jadikan Kebutuhan Alat</button>' : "";
    return (
      '<div class="rn-ak-need-row" data-object="' + esc(o.name) + '" role="button" tabindex="0">' +
      '<span class="rn-ak-need-no">' + (i + 1) + "</span>" +
      '<span class="rn-ak-need-body"><span class="rn-ak-need-head"><b>' + esc(o.title) + "</b>" +
      '<span class="chip ' + (STATUS_CHIP[o.status] || "") + '">' + (STATUS_LABEL[o.status] || esc(o.status)) + "</span></span>" +
      "<small>" + esc(o.object_type_label) + " " + fmt(o.size_value) + " " + esc(o.size_unit || "") +
      (o.work_days_target ? " · " + fmt(o.work_days_target) + " hari kerja" : "") + " → Butuh: " + butuh + "</small>" +
      (action ? '<span class="rn-ak-need-act">' + action + '<span class="rn-pr-add-msg" data-to-request-msg="' + esc(o.name) + '"></span></span>' : "") +
      "</span>" + st + "</div>"
    );
  }

  function requestRow(m, i) {
    var ok = m.candidate_count > 0;
    return (
      '<div class="rn-ak-need-row">' +
      '<span class="rn-ak-need-no">' + (i + 1) + "</span>" +
      '<span class="rn-ak-need-body"><span class="rn-ak-need-head"><b>' + esc(m.location || "-") + "</b>" +
      '<span class="chip ' + (PRIO_CHIP[m.priority] || "") + '">' + esc(m.priority_label) + "</span></span>" +
      "<small>Butuh: " + esc(m.tool_name) + " (" + fmt(m.quantity) + ")" + (m.needed_for ? " · " + esc(m.needed_for) : "") + "</small></span>" +
      needButton(ok, ok ? "Cocok" : "Belum ada",
        ok ? fmt(m.candidate_count) + " kandidat: " + m.candidate_resource + " · " + m.candidate_location : "belum ada alat available yang cocok") +
      "</div>"
    );
  }

  function renderNeeds() {
    var el = $("#needList");
    var open = OBJECTS.filter(function (o) { return o.status !== "resolved"; });
    var matches = (BOARD_CACHE && BOARD_CACHE.matches) || [];
    $("#needsNote").textContent = fmt(open.length) + " kondisi lapangan · " + fmt(matches.length) + " permintaan alat terbuka";
    if (!open.length && !matches.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada kondisi lapangan atau permintaan alat terbuka. Mulai dari “Catat Kondisi Lapangan”: ukuran fisik kondisi, bukan daftar alat.</p>';
      return;
    }
    el.innerHTML = open.map(objectRow).join("") + matches.map(function (m, i) { return requestRow(m, open.length + i); }).join("");
    limitRows(el, 4);
    var S = window.RN_SESSION, user = S && S.getUser && S.getUser();
    el.querySelectorAll("[data-requires-role-action]").forEach(function (b) {
      if (S && S.roleAllows && !S.roleAllows(user ? user.role : "viewer", b.getAttribute("data-requires-role-action"))) b.style.display = "none";
    });
  }

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

  /* the drill keeps the rule behind every number (needs-first requirement) */
  function openObject(id) {
    var o = OBJECTS.find(function (x) { return x.name === id; });
    if (!o) return;
    var preds = (o.predictions || []).map(predRow).join("") ||
      '<p class="rn-muted">Belum ada aturan perkiraan alat untuk jenis kondisi ini — minta alat langsung lewat form di bawah halaman.</p>';
    showDrill(o.title,
      o.object_type_label + " · " + fmt(o.size_value) + " " + (o.size_unit || "") +
      (o.work_days_target ? " · target " + fmt(o.work_days_target) + " hari kerja" : "") + " · " + (o.location || "-"),
      '<div class="rn-ak-object-preds">' + preds + "</div>" + (o.notes ? '<p class="rn-muted" style="margin-top:10px;font-size:12px;">' + esc(o.notes) + "</p>" : ""));
  }

  function renderDispatch(rows) {
    var el = $("#dispatchList");
    if (!rows || !rows.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada dispatch alat untuk event ini.</p>';
      return;
    }
    el.innerHTML = rows.map(function (r) {
      var cls = r.status === "completed" ? "ok" : (r.status === "cancelled" ? "danger" : (r.status === "reserved" ? "warning" : "info"));
      return (
        '<div class="rn-ak-disp-row"><span class="rn-ak-disp-time">' + shortTime(r.deployed_at) + "<small>" + dayMonth(r.deployed_at) + "</small></span>" +
        '<span class="rn-ak-disp-ic">' + icon(toolIcon(r.tool_name)) + "</span>" +
        '<span class="rn-ak-disp-id"><b>' + esc(r.tool_name) + "</b><small>Operator: " + esc(r.operator || "-") + "</small></span>" +
        '<span class="rn-ak-disp-dest">' + esc(r.destination || "-") + "</span>" +
        '<span class="chip ' + cls + '">' + esc(r.status_label) + "</span></div>"
      );
    }).join("");
    limitRows(el, 4);
  }

  function renderSites(sites) {
    var el = $("#siteList");
    if (!sites || !sites.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada dispatch dengan lokasi tujuan tercatat.</p>';
      return;
    }
    el.innerHTML = sites.map(function (s) {
      var pct = Math.round(s.progress_pct || 0);
      return (
        '<div class="rn-ak-site-row"><span class="rn-ak-site-pin">' + icon("map-pin") + "</span>" +
        '<span class="rn-ak-site-id"><b>' + esc(s.location) + "</b><small>" + fmt(s.completed) + "/" + fmt(s.total) + " dispatch selesai</small></span>" +
        '<span class="rn-ak-site-prog"><small>Progress</small><span class="rn-kom-batt-bar"><i style="width:' + Math.max(3, pct) + '%"></i></span></span>' +
        '<span class="rn-ak-site-pct">' + pct + "%</span>" +
        '<span class="rn-ak-site-n"><small>Alat</small>' + fmt(s.total) + "</span></div>"
      );
    }).join("");
    limitRows(el, 4);
  }

  var FUEL = [];
  var FUEL_CLS = { kritis: "bad", waspada: "warn" };
  function openFuel(i) {
    var f = FUEL[i];
    if (f) showDrill(f.item_name, (FUEL_LABEL[f.status] || f.status) + " · kapasitas " + fmt(f.kapasitas) + " " + (f.unit || ""), drillItemsHtml([fuelItem(f)]));
  }
  var FUEL_LABEL = { kritis: "Kritis", waspada: "Rendah", aman: "Cukup" };

  function renderFuel(fuel) {
    var el = $("#fuelList");
    if (!fuel || !fuel.length) {
      el.innerHTML = '<p class="rn-muted">Belum ada Stock Observation BBM/oli untuk event ini.</p>';
      return;
    }
    FUEL = fuel;
    el.innerHTML = fuel.map(function (f, i) {
      var cls = FUEL_CLS[f.status] || "";
      var pct = f.kapasitas ? Math.min(100, Math.round(100 * f.stok / f.kapasitas)) : 0;
      return (
        '<div class="rn-ak-fuel-row" role="button" tabindex="0" data-fuel="' + i + '"><span class="rn-ak-fuel-ic ' + cls + '">' + icon(toolIcon(f.item_name)) + "</span>" +
        '<span class="rn-ak-fuel-id"><b>' + esc(f.item_name) + "</b>" + (f.posko_name ? "<small>" + esc(f.posko_name) + "</small>" : "") + '</span><span class="rn-ak-fuel-q">' + fmt(f.stok) + " " + esc(f.unit === "liter" ? "L" : f.unit) + "</span>" +
        '<span class="rn-kom-batt-bar" title="' + pct + '% dari kapasitas ' + fmt(f.kapasitas) + '"><i class="' + cls + '" style="width:' + Math.max(3, pct) + '%"></i></span>' +
        '<span class="rn-ak-fuel-st ' + cls + '">' + esc(FUEL_LABEL[f.status] || f.status) + "</span></div>"
      );
    }).join("");
    limitRows(el, 4);
  }

  var BLOCK_TYPE = { kebutuhan_belum_terpenuhi: "Kebutuhan belum terpenuhi", bbm_kritis: "Stok BBM/oli menipis", alat_rusak: "Rusak / perlu perbaikan" };

  function renderBlockers(rows) {
    var body = $("#blockerBody");
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="4"><em class="rn-muted">Tidak ada hambatan alat kerja saat ini.</em></td></tr>';
      limitRows(body, 3);
      return;
    }
    body.innerHTML = rows.map(function (r) {
      // detail: "lokasi · prioritas X" (kebutuhan), "lokasi · perlu perbaikan" (rusak), "Stok 40.0 liter tersisa" (bbm)
      var detail = String(r.detail || "").replace(/(\d+)\.0\b/g, "$1");
      var parts = detail.split(" · ");
      var oldBbm = r.type === "bbm_kritis" && parts.length === 1;
      var where = oldBbm ? "-" : parts[0];
      var note = oldBbm ? detail : parts.slice(1).join(" · ");
      return (
        '<tr><td title="' + esc(r.label) + '"><span class="rn-ak-cell-ic">' + icon(toolIcon(r.label)) + "</span>" + esc(r.label) + "</td>" +
        '<td title="' + esc(where) + '">' + (r.href ? '<a href="' + esc(r.href) + '">' + esc(where) + "</a>" : esc(where || "-")) + "</td>" +
        '<td title="' + esc(note) + '">' + esc(BLOCK_TYPE[r.type] || r.type) + (note ? ' <small class="rn-muted">· ' + esc(note) + "</small>" : "") + "</td>" +
        '<td><span class="chip ' + (r.severity === "critical" ? "danger" : "warning") + '">' + (r.severity === "critical" ? "Kritis" : "Mendesak") + "</span></td></tr>"
      );
    }).join("");
    limitRows(body, 3);
  }

  function renderSummary(s) {
    function tile(ic, cls, label, value, unit) {
      return '<div class="rn-ak-sum-tile"><small>' + label + '</small><span class="rn-ak-sum-ic ' + cls + '">' + icon(ic) + "</span>" +
        "<b>" + value + (unit ? "<em>" + unit + "</em>" : "") + "</b></div>";
    }
    $("#summaryGrid").innerHTML =
      tile("gauge", "info", "Penggunaan Alat", fmt(s.penggunaan_pct), "%") +
      tile("clock", "ok", "Jam Operasional", fmt(s.jam_operasional), "Jam") +
      tile("truck", "warn", "Dispatch Selesai", fmt(s.dispatch_selesai), "") +
      tile("hammer", "bad", "Kerusakan Baru", fmt(s.kerusakan_baru), "");
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

  var CONDITIONS = [];
  var TO_REQUEST_METHOD = "rescue_net.api_resource_tools.create_requests_from_work_object";

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
    OBJECTS = data.objects || [];
    renderNeeds();
  }

  function setupObjectForm() {
    var form = document.getElementById("objectForm");
    if (!form) return;
    fillConditionSelect(LEGACY_CONDITIONS);  // until the board answers
    form.object_type.addEventListener("change", function () {
      form.work_days_target.value = "";
      applyCondition();
    });
    $("#objectAddBtn").addEventListener("click", function () {
      var d = $("#objectDrawer");
      d.open = true;
      d.scrollIntoView({ behavior: "smooth", block: "start" });
      form.title.focus({ preventScroll: true });
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
        msg.textContent = "Tersimpan — perkiraan alat ada di Matching Kebutuhan Alat.";
        await loadObjects();
      } catch (err) {
        msg.textContent = "Gagal: " + (err && err.message || err) + (/login|permission|akses/i.test(String(err && err.message)) ? " (perlu login)" : "");
      }
    });
    document.addEventListener("click", async function (e) {
      var btn = e.target.closest("[data-to-request]");
      if (!btn) return;
      e.stopPropagation();
      var id = btn.getAttribute("data-to-request");
      var out = document.querySelector('[data-to-request-msg="' + id + '"]');
      btn.disabled = true;
      try {
        var r = await window.RN_FRAPPE.call(TO_REQUEST_METHOD, { work_object: id }, { method: "POST" });
        if (out) out.textContent = r.message || "";
        await loadBoard();
        await loadObjects();
      } catch (err) {
        btn.disabled = false;
        if (out) out.textContent = "Gagal: " + (err && err.message || err);
      }
    }, true);
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId() });
    BOARD_CACHE = data;
    var t = shortTime(data.generated_at);
    $("#workToolUpdated").textContent = "Alat Kerja · Diperbarui " + t;
    $("#workToolMeta").textContent = "Diperbarui " + dayMonth(data.generated_at) + " " + t + " · " +
      fmt((data.asset_registry || []).length) + " aset terdaftar";
    $("#akFootnote").textContent = "Terakhir diperbarui " + dayMonth(data.generated_at) + " " + t + ". " + (data.privacy || "");

    renderKpi(data.totals || {});
    renderCategories(data.categories || []);
    renderOperators(data.operators || []);
    renderNeeds();
    renderDispatch(data.dispatch || []);
    renderSites(data.sites || []);
    renderFuel(data.fuel || []);
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
    document.querySelectorAll("[data-ak-more]").forEach(function (link) {
      link.addEventListener("click", function () {
        var el = document.getElementById(link.getAttribute("data-ak-more"));
        var open = el.classList.toggle("is-all");
        link.textContent = open ? "Lebih sedikit" : link.getAttribute("data-label");
      });
    });
    $("#needList").addEventListener("click", function (e) {
      var row = e.target.closest("[data-object]");
      if (row && !e.target.closest("button")) openObject(row.getAttribute("data-object"));
    });
    $("#needList").addEventListener("keydown", function (e) {
      var row = e.target.closest("[data-object]");
      if (row && e.key === "Enter") openObject(row.getAttribute("data-object"));
    });
    $("#assetOpen").addEventListener("click", openAssets);
    $("#fuelList").addEventListener("click", function (e) {
      var row = e.target.closest("[data-fuel]");
      if (row) openFuel(+row.getAttribute("data-fuel"));
    });
    $("#fuelList").addEventListener("keydown", function (e) {
      var row = e.target.closest("[data-fuel]");
      if (row && e.key === "Enter") openFuel(+row.getAttribute("data-fuel"));
    });
    var mapLink = $("#akMapLink");
    if (mapLink) mapLink.href = "map.html?event=" + encodeURIComponent(getEventId());
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
