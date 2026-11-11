/* ============================================================
 * New dashboard (matches "program khusus.png"): calls
 * rescue_net.api_donor_program.program_board / program_detail
 * (guest, event-wide). Legacy "Buat Program"/"Update Progress"
 * forms below (kept inside <details>) still call
 * api_donor_program.context/create_program/create_update.
 * ============================================================ */
(function () {
  "use strict";

  var BOARD_METHOD = "rescue_net.api_donor_program.program_board";
  var DETAIL_METHOD = "rescue_net.api_donor_program.program_detail";
  var BOARD_CACHE = null;
  var CURRENT_FILTER = "semua";
  var SELECTED = null;

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function esc(s) { return window.RNUI.esc(s); }
  function fmt(n) { return window.RNUI.fmt(n); }
  function rp(n) { return "Rp " + fmt(n); }
  function getEventId2() {
    var q = new URLSearchParams(window.location.search).get("event");
    if (q) return q;
    try { var v = localStorage.getItem("rn_active_event"); if (v) return v.replace(/^disaster_events:/, ""); } catch (e) {}
    return "";
  }
  // owner 2026-11-09: filter bencana di atas + tombol kembali (HP)
  async function setupTopNav() {
    var back = $("#pkBack");
    if (back) back.onclick = function () {
      if (document.referrer && document.referrer.indexOf(location.host) > -1 && history.length > 1) history.back();
      else location.href = "../index.html";
    };
    var sel = $("#pkEventSel"); if (!sel) return;
    var evs = [];
    try { evs = await window.RN_FRAPPE.call("rescue_net.api_ai.public_active_disasters", {}); } catch (e) {}
    evs = Array.isArray(evs) ? evs : ((evs && (evs.events || evs.disasters)) || []);
    var cur = getEventId2();
    var known = function (id) { return evs.some(function (e) { return (e.id || e.name) === id; }); };
    if (evs.length && (!cur || (!known(cur) && !new URLSearchParams(location.search).get("program")))) {   // tanpa ?event / bencana contoh: pilih bencana aktif pertama
      cur = evs[0].id || evs[0].name;
      var u = new URL(location.href); u.searchParams.set("event", cur); history.replaceState(null, "", u.toString());
    }
    sel.innerHTML = evs.map(function (e) { var id = e.id || e.name; return '<option value="' + esc(id) + '"' + (id === cur ? " selected" : "") + ">" + esc(e.title || id) + "</option>"; }).join("") ||
      '<option value="">Tidak ada bencana aktif</option>';
    if (cur && !evs.some(function (e) { return (e.id || e.name) === cur; })) sel.insertAdjacentHTML("afterbegin", '<option value="' + esc(cur) + '" selected>' + esc(cur) + "</option>");
    sel.onchange = function () {
      try { localStorage.setItem("rn_active_event", sel.value); } catch (e) {}
      var u = new URL(location.href); u.searchParams.set("event", sel.value); u.searchParams.delete("program"); u.searchParams.delete("kelola"); location.href = u.toString();
    };
  }
  function shortDate(s) { return window.RNUI.shortDate(s); }

  var STATUS_LABEL = { planned: "Rencana", active: "Aktif", completed: "Selesai", cancelled: "Dibatalkan" };
  var STATUS_CHIP = { planned: "", active: "ok", completed: "", cancelled: "danger" };
  var PRIORITY_CRITICAL = { critical: 1, urgent: 1, high: 1, tinggi: 1, darurat: 1 };

  var DRILL_TITLES = {
    program_aktif: "Program Aktif", program_critical: "Program Critical",
    program_selesai: "Program Selesai", milestone_terlambat: "Milestone Terlambat",
    lokasi_belum_terlayani: "Lokasi Belum Terlayani", butuh_support: "Butuh Support",
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
    $("#programDrillTitle").textContent = DRILL_TITLES[kind] || kind;
    var items = ((BOARD_CACHE.kpi_items || {})[kind + "_items"]) || [];
    $("#programDrillSub").textContent = items.length + " item";
    $("#programDrillBody").innerHTML = drillItemsHtml(items);
    $("#programDrill").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("#programDrill").hidden = true; document.body.style.overflow = ""; }

  function renderKpi(t) {
    $("#kpiAktif").textContent = fmt(t.program_aktif);
    $("#kpiCritical").textContent = fmt(t.program_critical);
    $("#kpiSelesai").textContent = fmt(t.program_selesai);
    $("#kpiTerlambat").textContent = fmt(t.milestone_terlambat);
    $("#kpiLokasi").textContent = fmt(t.lokasi_belum_terlayani);
    $("#kpiSupport").textContent = fmt(t.butuh_support);
  }

  function filteredPrograms() {
    var rows = (BOARD_CACHE && BOARD_CACHE.programs) || [];
    if (CURRENT_FILTER === "aktif") return rows.filter(function (p) { return p.status === "active"; });
    if (CURRENT_FILTER === "critical") return rows.filter(function (p) { return PRIORITY_CRITICAL[(p.priority || "").toLowerCase()] && p.status !== "completed"; });
    if (CURRENT_FILTER === "selesai") return rows.filter(function (p) { return p.status === "completed"; });
    return rows;
  }

  function renderList() {
    var rows = filteredPrograms();
    var el = $("#programList");
    if (!rows.length) {
      el.innerHTML = '<p class="rn-muted" style="padding:8px;">Tidak ada program pada filter ini.</p>';
      return;
    }
    el.innerHTML = rows.map(function (p) {
      var sel = SELECTED === p.name ? " is-selected" : "";
      var cover = p.cover_image_url
        ? '<span class="rn-pk-thumb" style="background-image:url(\'' + esc(p.cover_image_url) + '\')"></span>'
        : '<span class="rn-pk-thumb rn-pk-thumb-ph"><span data-icon="gift"></span></span>';
      return (
        '<button type="button" class="rn-pk-card' + sel + '" data-program="' + esc(p.name) + '">' + cover +
        '<span class="rn-pk-card-body">' +
        '<span class="rn-pk-card-head"><b>' + esc(p.program_name) + '</b>' +
          (p.is_own_hidden ? '<span class="chip danger">Belum Publik</span>' : "") +
          (p.initiator_verified ? '<span class="chip ok" title="Pemrakarsa terverifikasi">✔ Terverifikasi</span>'
            : '<span class="chip warning" title="Pemrakarsa belum terverifikasi">Belum terverifikasi</span>') +
          '<span class="chip ' + (STATUS_CHIP[p.status] || "") + '">' + (STATUS_LABEL[p.status] || p.status) + "</span></span>" +
        '<span class="rn-pk-card-meta"><i class="pk-cat">' + esc(p.category) + "</i> · " + esc(p.location) +
          (p.owner_title ? '<br>oleh <b>' + esc(p.owner_title) + "</b>" : "") + "</span>" +
        (p.donation_channel === "kitabisa" ? '<span class="pk-card-amt"><span class="pk-kb-tag">via Kitabisa</span> ' +
            (p.kitabisa && p.kitabisa.collected != null ? "<b>" + rp(p.kitabisa.collected) + "</b> terkumpul" : "lihat angka di Kitabisa") +
            (p.kitabisa && (p.kitabisa.target || p.budget_target) ? " dari " + rp(p.kitabisa.target || p.budget_target) : "") + "</span>" : "") +
        (p.donation_channel !== "kitabisa" && (Number(p.budget_target) > 0 || Number(p.budget_received) > 0)
          ? '<span class="pk-card-amt"><b>' + rp(p.budget_received) + "</b> terkumpul" + (Number(p.budget_target) > 0 ? " dari " + rp(p.budget_target) : "") + "</span>" +
            '<span class="rn-pk-bar"><span style="width:' + (Number(p.budget_target) > 0 ? Math.min(100, Math.round(p.budget_received / p.budget_target * 100)) : 0) + '%"></span></span>' +
            '<span class="rn-pk-bar-label"><span>' + fmt(p.donor_count || 0) + " donatur</span><span>" + (p.end_date && p.status === "active" ? daysLeft(p.end_date) : "") + "</span></span></span></button>"
          : '<span class="rn-pk-bar"><span style="width:' + p.progress_percent + '%"></span></span>' +
            '<span class="rn-pk-bar-label"><span>' + p.progress_percent + "% progres</span></span></span></button>")
      );
    }).join("");

    el.querySelectorAll("[data-program]").forEach(function (btn) {
      btn.addEventListener("click", function () { selectProgram(btn.getAttribute("data-program")); });
    });
    if (window.RNIconFill) window.RNIconFill(el);
  }

  function setupFilterTabs() {
    $("#programTabs").querySelectorAll(".rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        $("#programTabs").querySelectorAll(".rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        CURRENT_FILTER = tab.getAttribute("data-filter");
        renderList();
      });
    });
  }

  function setupDetailTabs() {
    $("#detailTabs").querySelectorAll(".rn-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        $("#detailTabs").querySelectorAll(".rn-tab").forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        var name = tab.getAttribute("data-tab");
        ["ringkasan", "rencana", "anggaran", "riwayat", "donatur", "ulasan"].forEach(function (k) {
          $("#tab" + k.charAt(0).toUpperCase() + k.slice(1)).hidden = k !== name;
        });
      });
    });
  }

  function evidenceThumb(ev) {
    var url = ev.evidence_url || ev.file_url || "";
    return (
      '<a class="rn-bukti-thumb" href="' + esc(url) + '" target="_blank" rel="noopener">' +
      (url ? '<img src="' + esc(url) + '" alt="">' : "") + "</a>"
    );
  }

  var UPDATE_TYPE_LABEL = { progress: "Progress", spending: "Pengeluaran", handover: "Serah Terima", completion: "Selesai" };

  function renderUpdates(updates) {
    var el = $("#detailUpdates");
    if (!updates || !updates.length) {
      el.innerHTML = '<article class="event-card"><h4>Belum ada riwayat</h4><p>Belum ada update tercatat untuk program ini.</p></article>';
      return;
    }
    el.innerHTML = updates.map(function (u) {
      return (
        '<article class="event-card"><div class="event-main"><div>' +
        "<h4>" + esc(u.update_title) + "</h4><p>" + esc(u.update_notes || "") + "</p>" +
        '<p class="rn-muted">' + shortDate(u.observed_at) + " · " + fmt(u.progress_percent) + "% · " + rp(u.amount_spent) + "</p></div>" +
        '<div class="chips"><span class="chip">' + (UPDATE_TYPE_LABEL[u.update_type] || u.update_type) + "</span></div>" +
        "</div></article>"
      );
    }).join("");
  }

  function renderProject(project, eventId) {
    var wrap = $("#detailProject");
    if (!project) { wrap.hidden = true; return; }
    wrap.hidden = false;
    var designWrap = $("#projectDesignWrap");
    if (project.design_image_url) {
      $("#projectDesignImg").src = project.design_image_url;
      designWrap.hidden = false;
    } else {
      designWrap.hidden = true;
    }
    $("#projectScope").textContent = project.scope_description || "Belum ada uraian lingkup pekerjaan.";
    $("#projectRab").textContent = rp(project.rab_total);
    $("#projectStatus").textContent = project.status_label || project.status || "-";
    $("#projectPelaksana").textContent = project.pelaksana || "Belum ditetapkan";
    $("#projectRabDoc").textContent = project.rab_document_url ? "" : "Dokumen RAB belum diunggah.";
    $("#projectRabDoc").innerHTML = project.rab_document_url
      ? '<a href="' + esc(project.rab_document_url) + '" target="_blank" rel="noopener">Unduh dokumen RAB ↓</a>'
      : "Dokumen RAB belum diunggah.";
    $("#projectTenderLink").href = "pengadaan-tender.html?event=" + encodeURIComponent(eventId || "");
  }

  function renderNotPublicBanner(data) {
    var banner = $("#detailNotPublicBanner");
    var notPublic = data.can_manage && data.program.public_visibility !== "summary_public";
    banner.hidden = !notPublic;
    if (!notPublic) return;
    var btn = $("#recheckPublishBtn");
    var msg = $("#recheckPublishMsg");
    msg.textContent = data.owner_verified === false ? " (belum terverifikasi)" : "";
    if (!btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", async function () {
        msg.textContent = " memproses…";
        try {
          var r = await window.RN_FRAPPE.call("rescue_net.api_donor_program.recheck_and_publish",
            { donor_program: SELECTED }, { method: "POST" });
          msg.textContent = " berhasil dipublikasikan" +
            (r.tenders_opened && r.tenders_opened.length ? " (tender ikut dibuka)" : "") + ".";
          await selectProgram(SELECTED);
          await loadBoard();
        } catch (err) {
          msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    }
  }


  /* ---------- plan: milestones, map, needs, support, verification ---------- */
  var PLAN = null;
  var PLAN_MAP = null;
  var VERIF_LABEL = { belum_dimulai: "Belum Dimulai", dalam_proses: "Dalam Proses", terverifikasi: "Terverifikasi", ditolak: "Ditolak" };
  var SUPPORT_PAGE = { logistik: ["package", "posko-logistik.html", "Ajukan Support"], distribusi: ["truck", "management-distribusi.html", "Ajukan Support"],
    relawan: ["users", "management-relawan.html", "Ajukan Relawan"], alat_kerja: ["wrench", "alat-kerja.html", "Ajukan Alat"] };
  var MS_STATUS = { belum_mulai: "Belum Mulai", berjalan: "Berjalan", selesai: "Selesai" };

  function qty(n) { return fmt(Math.round(Number(n || 0) * 100) / 100); }

  function renderPlan(data) {
    var plan = data.plan;
    var none = '<p class="rn-muted rn-pk-empty">';
    if (!plan) return;

    $("#planMilestones").innerHTML = plan.milestones.length ? plan.milestones.map(function (m) {
      var st = m.milestone_status;
      var mark = st === "selesai" ? '<span class="rn-pk-dot done"></span>' : '<span class="rn-pk-dot ' + (st === "berjalan" ? "run" : "") + '"></span>';
      var right = st === "selesai" ? "Selesai " + shortDate(m.completed_at || m.due_date)
        : st === "berjalan" ? "Berjalan <b>" + m.progress_percent + "%</b>" : "Belum Mulai";
      return '<li class="' + (m.is_late ? "is-late" : "") + '">' + mark + "<span><b>" + esc(m.title) + "</b>" +
        (m.due_date ? "<small>Target " + esc(shortDate(m.due_date)) + (m.is_late ? " · terlambat" : "") + "</small>" : "") + "</span><em>" + right + "</em></li>";
    }).join("") : none + "Belum ada milestone.</p>";

    var lt = plan.location_totals;
    $("#locTotal").textContent = fmt(lt.total) + " Lokasi";
    $("#locServed").textContent = fmt(lt.served) + " Lokasi";
    $("#locUnserved").textContent = fmt(lt.unserved) + " Lokasi";
    drawMap(plan.locations);

    $("#planNeeds").innerHTML = plan.needs.length ? plan.needs.map(function (n) {
      var gap = n.shortfall > 0;
      return '<div class="rn-pk-need"><span><b>' + esc(n.item) + "</b><small>" + qty(n.qty_needed) + " " + esc(n.unit || "") + "</small></span><em class=\"" + (gap ? "gap" : "ok") + '">' +
        (gap ? qty(n.qty_available) + " tersedia / " + qty(n.shortfall) + " kurang" : "Terpenuhi") + "</em></div>";
    }).join("") : none + "Belum ada kebutuhan material.</p>";

    $("#planSupport").innerHTML = Object.keys(SUPPORT_PAGE).map(function (k) {
      var c = plan.support[k], pg = SUPPORT_PAGE[k];
      var tone = c.status === "butuh_support" ? "warning" : c.status === "terpenuhi" ? "good" : "neutral";
      var lab = c.status === "butuh_support" ? "Butuh " + (k === "relawan" ? "Relawan" : k === "alat_kerja" ? "Alat" : "Support") : c.status === "terpenuhi" ? "Terpenuhi" : "Tidak ada kebutuhan";
      return '<div class="rn-pk-sup"><div class="rn-pk-sup-h"><span class="rn-pk-support-icon" data-icon="' + pg[0] + '"></span><b>' + esc(c.label) + "</b></div>" +
        '<span class="chip ' + tone + '">' + esc(lab) + "</span>" +
        (c.items.length ? "<ul>" + c.items.map(function (i) { return "<li><span>" + esc(i.item) + "</span><b>" + qty(i.qty) + " " + esc(i.unit || "") + "</b></li>"; }).join("") + "</ul>" : "") +
        '<a class="btn mini" href="' + pg[1] + "?event=" + encodeURIComponent(getEventId2()) + '">' + pg[2] + "</a></div>";
    }).join("");

    var ups = (data.updates || []).slice(0, 3);
    $("#planField").innerHTML = ups.length ? ups.map(function (u) {
      return "<div><b>" + esc(u.update_title) + "</b><small>" + shortDate(u.observed_at) + " · " + fmt(u.progress_percent) + "%</small></div>";
    }).join("") : none + "Belum ada update lapangan.</p>";

    var v = plan.verification || {};
    $("#planVerif").innerHTML =
      "<div><dt>Status Verifikasi</dt><dd class=\"" + (v.status === "terverifikasi" ? "ok" : "warn") + '">' + esc(VERIF_LABEL[v.status] || "Belum dicatat") + "</dd></div>" +
      "<div><dt>Output Diverifikasi</dt><dd>" + (v.output_target ? fmt(v.output_verified || 0) + " / " + fmt(v.output_target) : "-") + "</dd></div>" +
      "<div><dt>Verifikator</dt><dd>" + esc(v.verifier || "-") + "</dd></div>" +
      "<div><dt>Estimasi Selesai</dt><dd>" + (v.estimated_done ? esc(shortDate(v.estimated_done)) : "-") + "</dd></div>";

    renderEdit(data);
  }

  function drawMap(locs) {
    var host = $("#planMap");
    if (PLAN_MAP) { PLAN_MAP.remove(); PLAN_MAP = null; }
    var pts = (locs || []).filter(function (l) { return l.latitude && l.longitude; });
    if (!window.L || !pts.length) {
      host.innerHTML = '<p class="rn-muted rn-pk-empty">' + (locs && locs.length ? "Lokasi belum punya koordinat." : "Belum ada lokasi implementasi.") + "</p>";
      return;
    }
    host.innerHTML = "";
    PLAN_MAP = L.map(host, { zoomControl: false, attributionControl: false, scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(PLAN_MAP);
    var b = [];
    pts.forEach(function (l) {
      var done = l.location_status === "terlayani";
      L.circleMarker([l.latitude, l.longitude], { radius: 7, color: "#fff", weight: 2, fillColor: done ? "#2fa66a" : "#e8553d", fillOpacity: 1 })
        .bindTooltip(l.title + (done ? " (terlayani)" : " (belum terlayani)")).addTo(PLAN_MAP);
      b.push([l.latitude, l.longitude]);
    });
    PLAN_MAP.fitBounds(window.RNUI.localClusterBounds(b, 150), { padding: [18, 18], maxZoom: 14 });
    setTimeout(function () { if (PLAN_MAP) PLAN_MAP.invalidateSize(); }, 200);
  }

  /* ---------- plan editing (owner / Control Centre) ---------- */
  function planCall(method, args) {
    args.donor_program = SELECTED;
    return window.RN_FRAPPE.call("rescue_net.api_donor_program." + method, args, { method: "POST" })
      .then(function () { return selectProgram(SELECTED); })
      .then(function () { return loadBoard(); })
      .catch(function (e) { $("#planMsg").textContent = (e && e.message) || String(e); });
  }
  function editRow(type, id, text, actions) {
    return '<div class="rn-pk-erow"><span>' + text + "</span><span class=\"rn-pk-eact\">" + actions +
      '<button type="button" class="btn mini" data-del="' + type + '" data-id="' + esc(id) + '">Hapus</button></span></div>';
  }
  function renderEdit(data) {
    if (!data.can_manage) return;
    var plan = data.plan;
    $("#editMilestones").innerHTML = plan.milestones.map(function (m) {
      var next = m.milestone_status === "belum_mulai" ? "berjalan" : m.milestone_status === "berjalan" ? "selesai" : "";
      return editRow("milestone", m.name, "<b>" + esc(m.title) + "</b> · " + MS_STATUS[m.milestone_status] + " " + m.progress_percent + "% · " + esc(shortDate(m.due_date)),
        next ? '<button type="button" class="btn mini" data-ms="' + esc(m.name) + '" data-to="' + next + '">→ ' + MS_STATUS[next] + "</button>" : "");
    }).join("") || '<p class="rn-muted">Belum ada milestone.</p>';
    $("#editLocations").innerHTML = plan.locations.map(function (l) {
      var done = l.location_status === "terlayani";
      return editRow("location", l.name, "<b>" + esc(l.title) + "</b> · " + (done ? "terlayani" : "belum terlayani"),
        '<button type="button" class="btn mini" data-loc="' + esc(l.name) + '" data-to="' + (done ? "belum_terlayani" : "terlayani") + '">' + (done ? "Batalkan" : "Tandai terlayani") + "</button>");
    }).join("") || '<p class="rn-muted">Belum ada lokasi.</p>';
    $("#editNeeds").innerHTML = (plan.all_needs || plan.needs).map(function (n) {
      return editRow("need", n.name, "<b>" + esc(n.item) + "</b> · " + esc(n.kind) + " · " + qty(n.qty_available) + " / " + qty(n.qty_needed) + " " + esc(n.unit || ""),
        '<button type="button" class="btn mini" data-need="' + esc(n.name) + '" data-have="' + n.qty_available + '">Ubah tersedia</button>');
    }).join("") || '<p class="rn-muted">Belum ada kebutuhan.</p>';
    var v = plan.verification || {}, f = $("#verifForm");
    if (f) { f.status.value = v.status || ""; f.output_target.value = v.output_target || ""; f.output_verified.value = v.output_verified || ""; f.verifier.value = v.verifier || ""; f.estimated_done.value = v.estimated_done ? shortDate(v.estimated_done) : ""; }
    $("#planMsg").textContent = "";
  }
  function wirePlanEditing() {
    var tab = $("#tabRencana");
    tab.addEventListener("click", function (e) {
      var t = e.target.closest("button");
      if (!t) return;
      if (t.dataset.del) { if (window.confirm("Hapus item ini?")) planCall("delete_plan_item", { item_type: t.dataset.del, name: t.dataset.id }); }
      else if (t.dataset.ms) planCall("save_plan_item", { item_type: "milestone", name: t.dataset.ms, values: JSON.stringify({ milestone_status: t.dataset.to }) });
      else if (t.dataset.loc) planCall("save_plan_item", { item_type: "location", name: t.dataset.loc, values: JSON.stringify({ location_status: t.dataset.to }) });
      else if (t.dataset.need) {
        var v = window.prompt("Jumlah tersedia", t.dataset.have);
        if (v !== null && v !== "") planCall("save_plan_item", { item_type: "need", name: t.dataset.need, values: JSON.stringify({ qty_available: Number(v) }) });
      }
    });
    tab.querySelectorAll("form[data-add]").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        e.preventDefault();
        var vals = {};
        Array.prototype.forEach.call(f.elements, function (el) { if (el.name && el.value !== "") vals[el.name] = el.type === "number" ? Number(el.value) : el.value; });
        planCall("save_plan_item", { item_type: f.dataset.add, values: JSON.stringify(vals) }).then(function () { f.reset(); });
      });
    });
    $("#verifForm").addEventListener("submit", function (e) {
      e.preventDefault();
      var f = e.target;
      planCall("set_output_verification", { status: f.status.value, output_target: f.output_target.value, output_verified: f.output_verified.value,
        verifier: f.verifier.value, estimated_done: f.estimated_done.value });
    });
    $("#shareProgram").addEventListener("click", function () {
      var url = location.href.split("#")[0];
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { $("#shareProgram").textContent = "Tersalin"; }, function () { window.prompt("Salin tautan", url); });
    });
  }

  function renderDetail(data) {
    var p = data.program;
    $("#detailEmpty").hidden = true;
    $("#detailBody").hidden = false;

    $("#detailName").textContent = p.program_name;
    $("#detailStatus").textContent = STATUS_LABEL[p.status] || p.status;
    $("#detailStatus").className = "chip " + (STATUS_CHIP[p.status] || "");
    $("#detailCategory").textContent = p.category;
    $("#detailCategory").className = "chip neutral";
    var meta = [["map-pin", p.target_location || p.location || "-"]];
    if (p.start_date || p.end_date) meta.push(["clock", "Periode: " + (p.start_date ? shortDate(p.start_date) : "-") + " – " + (p.end_date ? shortDate(p.end_date) : "-")]);
    if (p.partners) meta.push(["users", "Mitra: " + p.partners]);
    if (p.priority) meta.push(["alert-triangle", "Prioritas " + p.priority]);
    $("#detailMeta").innerHTML = meta.map(function (m) { return '<li><span data-icon="' + m[0] + '"></span>' + esc(m[1]) + "</li>"; }).join("");
    var cover = $("#detailCover");
    if (p.cover_image_url) { cover.style.backgroundImage = "url('" + p.cover_image_url + "')"; cover.className = "rn-pk-cover"; cover.innerHTML = ""; }
    else { cover.style.backgroundImage = ""; cover.className = "rn-pk-cover rn-pk-thumb-ph"; cover.innerHTML = '<span data-icon="gift"></span><small>Simulasi</small>'; }

    $("#detailProgressPct").textContent = p.progress_percent + "%";
    $("#detailProgressBar").style.width = p.progress_percent + "%";
    var lt = data.plan && data.plan.location_totals;
    if (lt && lt.total) {
      $("#detailTargetLabel").textContent = "Target Lokasi";
      $("#detailTarget").textContent = fmt(lt.total) + " lokasi";
      $("#detailCurrent").textContent = fmt(lt.served) + " lokasi";
    } else {
      $("#detailTargetLabel").textContent = "Target";
      $("#detailTarget").textContent = fmt(p.target_amount) + " " + (p.target_unit || "");
      $("#detailCurrent").textContent = fmt(p.current_amount) + " " + (p.target_unit || "");
    }
    $("#tabBtnRencana").hidden = !data.can_manage;
    // owner 2026-11-02 23:20: form progres hanya untuk pengelola program yang sedang dibuka
    if (window.RN_OWNER_ONLY) window.RN_OWNER_ONLY.grant(!!data.can_manage);
    var updForm = document.getElementById("programUpdateForm");
    if (updForm && data.can_manage && updForm.program_id && p.name) updForm.program_id.value = p.name;
    if (!data.can_manage && !$("#tabRencana").hidden) { $("#detailTabs .rn-tab[data-tab=ringkasan]").click(); }

    $("#detailDescription").textContent = p.description || p.target_description || "Belum ada deskripsi program.";
    $("#detailOfficer").textContent = p.officer_in_charge_name || "-";
    $("#detailOfficerPhone").textContent = p.officer_in_charge_phone || "";
    $("#detailPeriod").textContent = (p.start_date ? shortDate(p.start_date) : "-") + " – " + (p.end_date ? shortDate(p.end_date) : "-");
    $("#detailBeneficiaries").textContent = p.target_beneficiaries || p.target_description || "-";

    $("#budgetTarget").textContent = rp(p.budget_target);
    $("#budgetReceived").textContent = rp(p.budget_received);
    $("#budgetSpent").textContent = rp(p.budget_spent);

    $("#detailEvidence").innerHTML = (data.bukti || []).length
      ? data.bukti.map(evidenceThumb).join("")
      : '<p class="rn-muted" style="grid-column:1/-1;">Belum ada evidence terhubung ke program ini.</p>';

    PLAN = data;
    renderPlan(data);
    renderProject(data.project, getEventId2());
    renderUpdates(data.updates || []);
    renderNotPublicBanner(data);
    renderDonations(data.donations || {});
    renderBudget(data);
    renderDonorsTop(data);
    renderFund(data);
    renderDocs(data);
    renderBank(data);
    if (window.RNIconFill) window.RNIconFill(document);
  }

  /* ---------- dokumen RAB, gambar kerja, rekening, badge (owner 2026-11-01) ---------- */
  function renderDocs(data) {
    var docs = data.documents || {}, manage = !!data.can_manage;
    var badge = $("#detailVerified");
    if (badge) {
      badge.hidden = false;
      badge.className = "chip " + (data.initiator_verified ? "ok" : "warning");
      badge.textContent = data.initiator_verified ? "✔ Pemrakarsa terverifikasi" : "Pemrakarsa belum terverifikasi";
    }
    // owner 2026-11-02: gambar rencana (PDF / gambar) + RAB bisa beberapa halaman
    function tiles(list, kind, empty) {
      return list.length ? list.map(function (d, i) {
        var thumb = d.pdf ? '<span class="rn-pk-pdf">📄</span>' : '<img src="' + esc(d.url) + '" alt="' + esc(d.label || d.name) + '" loading="lazy">';
        var cap = kind === "rab" ? "Hal. " + (i + 1) + (d.label ? " — " + d.label : "") : (d.label || d.name);
        return '<a class="rn-pk-drawing" href="' + esc(d.url) + '" target="_blank" rel="noopener">' + thumb +
          "<span>" + esc(cap) + "</span>" +
          (manage ? '<button type="button" data-doc-del="' + kind + '" data-url="' + esc(d.url) + '" title="Hapus">✕</button>' : "") + "</a>";
      }).join("") : '<span class="rn-muted">' + empty + "</span>";
    }
    var pages = docs.rab_pages || (docs.rab ? [{ url: docs.rab, name: "RAB.pdf", pdf: true }] : []);
    $("#docRab").innerHTML = '<b class="rn-pk-doc-h" style="display:block;margin-top:10px">📑 Rencana Anggaran Biaya (RAB)' + (pages.length ? " — " + pages.length + " halaman/berkas" : "") + "</b>" +
      '<div class="rn-pk-drawings">' + tiles(pages, "rab", "RAB belum diunggah.") + "</div>";
    $("#docDrawings").innerHTML = '<b class="rn-pk-doc-h" style="display:block;margin-top:10px">📐 Gambar Rencana</b><div class="rn-pk-drawings">' +
      tiles(docs.drawings || [], "gambar", "Gambar rencana belum diunggah.") + "</div>";
    var st = docs.statements || [];
    var ds = $("#docStatements");
    if (ds) ds.innerHTML = '<b class="rn-pk-doc-h" style="display:block;margin-top:10px">🧾 Rekening Koran (transparansi dana)' + (st.length ? " — " + st.length + " berkas" : "") + "</b>" +
      '<div class="rn-pk-drawings">' + tiles(st, "koran", "Rekening koran belum diunggah.") + "</div>";
    $("#docManage").hidden = !manage;
  }

  function renderBank(data) {
    var b = data.bank || {}, box = $("#bankBox");
    if (!box) return;
    var qris = b.qris_url ? '<div class="rn-pk-qris" style="margin-top:8px"><b>Atau bayar dengan QRIS:</b><br>' +
      '<a href="' + esc(b.qris_url) + '" target="_blank" rel="noopener"><img src="' + esc(b.qris_url) + '" alt="QRIS penerimaan donasi program" ' +
      'style="width:220px;max-width:100%;border-radius:8px;border:1px solid var(--line);background:#fff;margin-top:4px"></a>' +
      (data.can_manage ? '<br><button type="button" class="btn mini" data-doc-del="qris" data-url="' + esc(b.qris_url) + '">Hapus QRIS</button>' : "") + "</div>" : "";
    if (b.account_number || b.qris_url) {
      box.hidden = false;
      box.className = "rn-pk-bank" + (b.shown_publicly ? "" : " warn");
      box.innerHTML = (b.account_number ? "Transfer ke rekening pemrakarsa:<br><b>" + esc(b.bank_name) + " " + esc(b.account_number) + "</b>" +
        ' <button type="button" class="btn mini" data-copy="' + esc(b.account_number) + '">Salin</button><br>a.n. ' + esc(b.account_holder) : "") + qris +
        "<br><small>" + (b.shown_publicly
          ? "Setelah transfer, isi formulir di bawah. Donasi tampil di daftar setelah dicek & dikonfirmasi pemrakarsa."
          : "Hanya Anda (pengelola) yang melihat rekening ini — tampil ke publik setelah pemrakarsa terverifikasi.") + "</small>";
    } else if (b.available) {
      box.hidden = false; box.className = "rn-pk-bank warn";
      box.textContent = "Rekening / QRIS pemrakarsa disembunyikan sampai pemrakarsa terverifikasi. Jangan transfer ke rekening atau QRIS yang dikirim lewat pesan pribadi.";
    } else {
      box.hidden = true;
    }
    // Ringkasan juga menampilkan rekening/QRIS (owner 2026-11-08: "nggak ada no rekening apalagi qris" — dulu hanya di tab Anggaran)
    var closed = /^(cancelled|completed)$/i.test(String((data.program || {}).status || ""));
    var top = $("#donateTop"), topBox = $("#bankBoxTop");
    if (closed) {
      box.hidden = false; box.className = "rn-pk-bank warn";
      box.textContent = "Program ini sudah " + (/cancel/i.test(data.program.status) ? "dibatalkan" : "selesai") + " dan tidak menerima donasi lagi.";
      var dfm = $("#donateForm"); if (dfm) dfm.hidden = true;
    } else { var dfo = $("#donateForm"); if (dfo) dfo.hidden = false; }
    if (top && topBox) {
      top.hidden = box.hidden;
      topBox.className = box.className; topBox.innerHTML = box.innerHTML;
      var go = $("#donateTopGo");
      if (go) {
        go.hidden = closed || !(b.account_number || b.qris_url) || !b.shown_publicly;
        go.onclick = null;   // tombol membuka lembar donasi (data-open-donate)
      }
    }
    box.hidden = true;                 // owner 2026-11-08: rekening/QRIS hanya di Ringkasan, tidak di tab Anggaran
    var f = $("#bankForm");
    if (f && data.can_manage && b.account_number) {
      f.bank_name.value = b.bank_name; f.account_number.value = b.account_number; f.account_holder.value = b.account_holder;
    }
  }

  function readBase64(file) {
    return new Promise(function (ok, bad) {
      var r = new FileReader();
      r.onload = function () { ok(String(r.result).split(",")[1] || ""); };
      r.onerror = function () { bad(new Error("Gagal membaca file")); };
      r.readAsDataURL(file);
    });
  }

  function wireDocForms() {
    var API = "rescue_net.api_donor_program.";
    function upload(formId, msgId, kind) {
      var f = $(formId);
      if (!f || f.dataset.wired) return;
      f.dataset.wired = "1";
      f.addEventListener("submit", async function (e) {
        e.preventDefault();
        var m = $(msgId), file = f.file.files[0];
        if (!file) return;
        if (file.size > 10 * 1024 * 1024) { m.textContent = "File terlalu besar (maks. 10 MB)."; return; }
        m.textContent = "Mengunggah…";
        try {
          await window.RN_FRAPPE.call(API + "upload_program_file", { donor_program: SELECTED, kind: kind, filename: file.name,
            content_base64: await readBase64(file), label: f.label ? f.label.value : "",
            redacted: f.redacted && f.redacted.checked ? 1 : 0 }, { method: "POST" });
          m.textContent = "Terunggah."; f.reset();
          await selectProgram(SELECTED);
        } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
      });
    }
    upload("#rabForm", "#rabMsg", "rab");
    upload("#drawForm", "#drawMsg", "gambar");
    upload("#qrisForm", "#qrisMsg", "qris");
    upload("#koranForm", "#koranMsg", "koran");
    var bf = $("#bankForm");
    if (bf && !bf.dataset.wired) {
      bf.dataset.wired = "1";
      bf.addEventListener("submit", async function (e) {
        e.preventDefault();
        var m = $("#bankMsg"); m.textContent = "Menyimpan…";
        try {
          await window.RN_FRAPPE.call(API + "set_program_bank", { donor_program: SELECTED, bank_name: bf.bank_name.value,
            account_number: bf.account_number.value, account_holder: bf.account_holder.value }, { method: "POST" });
          m.textContent = "Tersimpan.";
          await selectProgram(SELECTED);
        } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
      });
    }
    if (!document.body.dataset.docWired) {
      document.body.dataset.docWired = "1";
      document.addEventListener("click", async function (e) {
        var cp = e.target.closest("[data-copy]");
        if (cp) {
          e.preventDefault();
          try { await navigator.clipboard.writeText(cp.dataset.copy); cp.textContent = "Tersalin"; } catch (x) { window.prompt("Salin nomor rekening:", cp.dataset.copy); }
          return;
        }
        var del = e.target.closest("[data-doc-del]");
        if (!del) return;
        e.preventDefault();
        if (window.confirm && !window.confirm("Hapus dokumen ini?")) return;
        try {
          await window.RN_FRAPPE.call(API + "remove_program_file", { donor_program: SELECTED, kind: del.dataset.docDel,
            file_url: del.dataset.url || null }, { method: "POST" });
          await selectProgram(SELECTED);
        } catch (err) { window.alert((err && err.message) || err); }
      });
    }
  }

  function renderDonations(d) {
    var wall = $("#donationWall");
    var pub = d.public || [];
    var tt = $("#donationWallTitle");
    if (tt) tt.textContent = "Daftar Donatur (terkonfirmasi) — " + pub.length + " donatur · total " + rp(d.total_received || 0);
    wall.className = "pk-donors";
    wall.innerHTML = pub.length ? pub.map(donorRow).join("") +
        '<div class="pk-don-total"><span>Total ' + pub.length + " donatur</span><b>" + rp(d.total_received || 0) + "</b></div>"
      : '<p class="rn-muted">Belum ada donasi terkonfirmasi untuk program ini.</p>';
    var tc = $("#tabDonCount"); if (tc) tc.textContent = pub.length ? "(" + pub.length + ")" : "";
    var pr = $("#pkPrayers");
    if (pr) {
      var msgs = pub.filter(function (r) { return r.message; });
      pr.innerHTML = msgs.length ? msgs.map(function (r) {
        return '<div class="pk-prayer"><span class="pk-av">' + initial(r.donor_name) + '</span><div><b>' + esc(r.donor_name) +
          '</b> <small>' + ago(r.confirmed_at) + "</small><p>" + esc(r.message) + "</p></div></div>";
      }).join("") : '<p class="rn-muted">Belum ada doa atau pesan dukungan.</p>';
    }

    var pendingSection = $("#donationPendingSection");
    var pendingList = $("#donationPending");
    if (d.can_manage) {
      pendingSection.hidden = false;
      var pending = d.pending || [];
      pendingList.innerHTML = pending.length
        ? pending.map(function (r) {
            return '<article class="event-card" data-donation="' + esc(r.name) + '"><div class="event-main"><div>' +
              "<h4>" + esc(r.donor_name) + (r.is_anonymous ? " (ingin anonim di publik)" : "") + "</h4>" +
              '<p class="rn-muted">Kontak: ' + esc(r.donor_contact || "-") + " · " + shortDate(r.creation) + "</p>" +
              (r.message ? "<p>" + esc(r.message) + "</p>" : "") +
              "</div><div class=\"chips\"><span class=\"chip\">" + rp(r.amount) + "</span></div></div>" +
              '<div class="form-actions">' +
              '<button type="button" class="btn primary" data-donate-act="confirm">Konfirmasi Diterima</button>' +
              '<button type="button" class="btn" data-donate-act="reject">Tolak</button>' +
              '<span class="form-message" data-donate-msg></span></div></article>';
          }).join("")
        : '<p class="rn-muted">Tidak ada donasi menunggu konfirmasi.</p>';
    } else {
      pendingSection.hidden = true;
      pendingList.innerHTML = "";
    }
  }

  function wireDonationActions() {
    var form = $("#donateForm");
    if (form && !form.dataset.wired) {
      form.dataset.wired = "1";
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var msg = $("#donateMsg");
        if (!SELECTED) { msg.textContent = "Pilih program dulu."; return; }
        var amount = Number(form.amount.value || 0);
        if (!(amount > 0)) { msg.textContent = "Nominal tidak valid."; return; }
        msg.textContent = "Mengirim…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_donor_program.create_cash_donation", {
            donor_program: SELECTED,
            amount: amount,
            is_anonymous: form.is_anonymous.checked ? 1 : 0,
            message: (form.message.value || "").trim() || null,
          }, { method: "POST" });
          msg.textContent = "Terkirim — menunggu konfirmasi lembaga penerima.";
          setTimeout(function () { if (typeof closeDonate === "function") closeDonate(); }, 2500);
          form.reset();
          await selectProgram(SELECTED);
        } catch (err) {
          msg.textContent = "Gagal: " + ((err && err.message) || err) +
            (/login|permission|akses|diperlukan/i.test(String(err && err.message)) ? " (perlu login sebagai donatur)" : "");
        }
      });
    }

    var pendingList = $("#donationPending");
    if (pendingList && !pendingList.dataset.wired) {
      pendingList.dataset.wired = "1";
      pendingList.addEventListener("click", async function (e) {
        var btn = e.target.closest("[data-donate-act]");
        if (!btn) return;
        var card = btn.closest("[data-donation]");
        var msg = card.querySelector("[data-donate-msg]");
        var act = btn.getAttribute("data-donate-act");
        var note = null;
        if (act === "reject") {
          note = window.prompt("Alasan menolak donasi ini (opsional):", "") || null;
        }
        msg.textContent = " memproses…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_donor_program.decide_cash_donation", {
            donation: card.getAttribute("data-donation"), action: act, note: note,
          }, { method: "POST" });
          await selectProgram(SELECTED);
        } catch (err) {
          msg.textContent = " gagal: " + ((err && err.message) || err);
        }
      });
    }
  }


  // ---- Kelola Program (owner 2026-11-08): pemrakarsa langsung melihat langkah pengelolaan ----
  function goManage(tab, sel) {
    var t = $("#detailTabs .rn-tab[data-tab=" + tab + "]"); if (t) t.click();
    setTimeout(function () {
      var el = $(sel); if (!el) return;
      if (el.tagName === "DETAILS") el.open = true;
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      var f = el.querySelector && el.querySelector("input,textarea,select"); if (f) try { f.focus({ preventScroll: true }); } catch (e) {}
    }, 60);
  }

  // ---- Anggaran & realisasi + daftar penyumbang (owner 2026-11-08) ----
  function renderBudget(data) {
    var p = data.program || {};
    var tgt = Number(p.budget_target || 0), rec = Number(p.budget_received || 0), spent = Number(p.budget_spent || 0);
    var left = rec - spent;
    var el = $("#budgetLeft"); if (el) el.textContent = rp(left);
    var pct = function (a, b) { return b > 0 ? Math.min(100, Math.round(a / b * 100)) : 0; };
    var bars = $("#budgetBars");
    if (bars) bars.innerHTML =
      (tgt > 0 ? '<div><label><span>Dana terkumpul dari target</span><b>' + pct(rec, tgt) + '%</b></label><div class="bar"><i style="width:' + pct(rec, tgt) + '%"></i></div></div>' : "") +
      '<div><label><span>Dana terpakai dari yang diterima</span><b>' + pct(spent, rec) + '%</b></label><div class="bar spent"><i style="width:' + pct(spent, rec) + '%"></i></div></div>';
    var rows = (data.updates || []).filter(function (u) { return Number(u.amount_spent || 0) > 0; });
    var list = $("#realisasiList");
    if (list) list.innerHTML = rows.length ? rows.map(function (u) {
      return '<div class="row one" title="' + esc(u.update_notes || "") + '"><span class="nm">' + esc(u.update_title) + '</span><span class="dt">' + shortDate(u.observed_at) + "</span><b>" + rp(u.amount_spent) + "</b></div>";
    }).join("") + '<div class="row"><span><b>Total realisasi</b></span><b>' + rp(spent) + "</b></div>"
      : '<p class="rn-muted">Belum ada realisasi anggaran tercatat.</p>';
    var f = $("#realisasiForm");
    if (f) {
      f.hidden = !data.can_manage;
      if (!f.dataset.wired) {
        f.dataset.wired = "1";
        f.addEventListener("submit", async function (e) {
          e.preventDefault();
          var m = $("#realisasiMsg"); m.textContent = "Menyimpan…";
          try {
            await window.RN_FRAPPE.call("rescue_net.api_donor_program.create_special_program_update", {
              program: SELECTED, update_title: f.update_title.value.trim(), update_type: "spending",
              amount_spent: Number(f.amount_spent.value || 0), update_notes: f.update_notes.value.trim() || null }, { method: "POST" });
            m.textContent = "Tercatat."; f.reset();
            await selectProgram(SELECTED);
          } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
        });
      }
    }
  }
  function renderDonorsTop(data) {
    var box = $("#donorsTop"); if (!box) return;
    var d = data.donations || {}, pub = d.public || [];
    box.hidden = false;
    $("#donorsTopSum").textContent = (d.donor_count || pub.length) + " penyumbang · " + rp(d.total_received || 0);
    $("#donorsTopList").className = "pk-donors";
    $("#donorsTopList").innerHTML = pub.length ? pub.slice(0, 5).map(donorRow).join("")
      : '<p class="rn-muted">Belum ada donasi terkonfirmasi. Jadilah penyumbang pertama.</p>';
    var all = $("#donorsTopAll");
    all.hidden = pub.length <= 5;
    all.onclick = function () { var t = $("#detailTabs .rn-tab[data-tab=donatur]"); if (t) t.click(); var w = $("#donationWallTitle"); if (w) w.scrollIntoView({ behavior: "smooth" }); };
  }


  // ---- gaya Kitabisa/LAZISMU (owner 2026-11-08: "kombinasikan") ----
  function initial(name) {
    var n = String(name || "").replace(/^\[SIMULASI\]\s*/i, "").trim();
    return /^donatur anonim/i.test(n) || !n ? "♥" : esc(n.charAt(0).toUpperCase());
  }
  function ago(ts) {
    if (!ts) return "";
    var t = new Date(String(ts).replace(" ", "T")), s = (Date.now() - t.getTime()) / 1000;
    if (s < 0 && s > -86400) return "baru saja";          // jam server vs jam perangkat berbeda zona
    if (!(s >= 0)) return shortDate(ts);
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + " menit lalu";
    if (s < 86400) return Math.round(s / 3600) + " jam lalu";
    if (s < 86400 * 30) return Math.round(s / 86400) + " hari lalu";
    return shortDate(ts);
  }
  function donorRow(r) {
    return '<div class="pk-don"><span class="pk-av' + (/anonim/i.test(r.donor_name) ? " anon" : "") + '">' + initial(r.donor_name) + '</span>' +
      '<span class="pk-don-main"><b class="pk-don-name">' + esc(r.donor_name) + '</b><small>' + ago(r.confirmed_at) + '</small></span>' +
      '<b class="pk-don-amt">' + rp(r.amount) + "</b></div>";
  }
  function daysLeft(end) {
    if (!end) return "";
    var d = Math.ceil((new Date(String(end) + "T23:59:59") - Date.now()) / 86400000);
    return d > 0 ? d + " hari lagi" : "Berakhir";
  }
  function renderFund(data) {
    var p = data.program || {}, box = $("#pkFund"); if (!box) return;
    var d = data.donations || {}, rec = Number(p.budget_received || 0), tgt = Number(p.budget_target || 0);
    var open = !/^(cancelled|completed)$/i.test(String(p.status || ""));
    box.hidden = false;
    $("#pkOwner").textContent = data.owner_title || "-";
    $("#pkOwnerV").hidden = !data.initiator_verified;
    $("#pkRaised").textContent = rp(rec);
    $("#pkOfTarget").textContent = tgt > 0 ? "terkumpul dari " + rp(tgt) : "terkumpul";
    $("#pkBar").style.width = (tgt > 0 ? Math.min(100, rec / tgt * 100) : 0) + "%";
    $("#pkDonors").textContent = fmt(d.donor_count || (d.public || []).length || 0);
    $("#pkDays").textContent = open ? daysLeft(p.end_date) : (/cancel/i.test(p.status) ? "Dibatalkan" : "Selesai");
    var hasPay = !!((data.bank || {}).account_number || (data.bank || {}).qris_url) && (data.bank || {}).shown_publicly;
    var kb = data.donation_channel === "kitabisa" ? (data.kitabisa || {}) : null;
    if (kb) {
      if (kb.open === false) open = false;
      var kbTgt = Number(kb.target || tgt || 0), kbRec = kb.collected == null ? null : Number(kb.collected);
      $("#pkRaised").textContent = kbRec == null ? "Lihat di Kitabisa" : rp(kbRec);
      $("#pkOfTarget").textContent = (kbRec == null ? "" : "terkumpul") + (kbTgt ? " dari " + rp(kbTgt) : "") +
        (kb.figures_at ? " · per " + shortDate(kb.figures_at) + ", sumber Kitabisa" : "");
      $("#pkBar").style.width = (kbTgt > 0 && kbRec != null ? Math.min(100, kbRec / kbTgt * 100) : 0) + "%";
      $("#pkDonors").textContent = kb.donor_count == null ? "—" : fmt(kb.donor_count);
      $("#pkOwner").textContent = data.owner_title || kb.organizer || "-";
      if (!open && kb.open === false) $("#pkDays").textContent = "Campaign Kitabisa ditutup";
    }
    document.querySelectorAll("[data-open-donate]").forEach(function (b) {
      b.disabled = !open;
      b.textContent = kb ? "Donasi di Kitabisa →" : "Donasi Sekarang";
    });
    var st = $("#pkSticky"); if (st) st.hidden = !open;
    var badge = $("#pkKbBadge");
    if (!badge && $("#pkFund")) { badge = document.createElement("div"); badge.id = "pkKbBadge"; badge.className = "pk-kb"; $("#pkFund").insertBefore(badge, $("#pkFund").firstChild); }
    if (badge) {
      badge.hidden = !kb;
      if (kb) badge.innerHTML = '<span class="pk-kb-tag">Melalui Kitabisa</span> Donasi diproses di <a href="' + esc(kb.url) + '" target="_blank" rel="noopener">halaman Kitabisa</a>' +
        (kb.title ? ' — "' + esc(kb.title) + '"' : "") + '. Di sini: penggunaan dana, posko penerima, dan bukti lapangan.';
    }
    var dt = $("#donateTop"); if (dt && kb) dt.hidden = true;
    var dtl = $("#donorsTopList"); if (dtl && kb && !(data.donations && (data.donations.public || []).length)) dtl.innerHTML = '<p class="rn-muted">Daftar donatur ada di <a href="' + esc(kb.url) + '" target="_blank" rel="noopener">halaman Kitabisa</a>.</p>';
    var wall = $("#donationWall"); if (wall && kb && !(data.donations && (data.donations.public || []).length)) wall.innerHTML = '<p class="rn-muted">Donasi program ini diproses Kitabisa; daftar donatur lengkap ada di <a href="' + esc(kb.url) + '" target="_blank" rel="noopener">halaman Kitabisa</a>.</p>';
    DONATE_CTX = { data: data, open: open, hasPay: hasPay, kb: kb };
  }
  var DONATE_CTX = null, PK_METHOD = "qris";
  function payBox() {
    var b = (DONATE_CTX && DONATE_CTX.data.bank) || {}, el = $("#pkPayBox");
    if (!el) return;
    if (!(b.account_number || b.qris_url) || !b.shown_publicly) {
      el.innerHTML = '<p class="rn-muted">Rekening/QRIS pemrakarsa belum tersedia untuk publik (pemrakarsa belum terverifikasi).</p>'; return;
    }
    if (PK_METHOD === "qris" && !b.qris_url) PK_METHOD = "bank";
    document.querySelectorAll(".pk-methods [data-method]").forEach(function (x) {
      x.classList.toggle("is-on", x.getAttribute("data-method") === PK_METHOD);
      x.disabled = x.getAttribute("data-method") === "qris" ? !b.qris_url : !b.account_number;
    });
    el.innerHTML = PK_METHOD === "qris"
      ? '<img src="' + esc(b.qris_url) + '" alt="QRIS pemrakarsa" class="pk-qris"><small>Pindai dengan aplikasi bank / e-wallet. Pastikan nama penerima sesuai pemrakarsa.</small>'
      : '<div class="pk-bankline"><span>' + esc(b.bank_name) + '</span><b>' + esc(b.account_number) + '</b><button type="button" class="btn mini" data-copy="' +
        esc(b.account_number) + '">Salin</button></div><small>a.n. ' + esc(b.account_holder) + "</small>";
  }
  function openDonate() {
    if (!DONATE_CTX || !DONATE_CTX.open) return;
    if (DONATE_CTX.kb && DONATE_CTX.kb.url) { window.open(DONATE_CTX.kb.url, "_blank", "noopener"); return; }
    var sh = $("#pkSheet"); if (!sh) return;
    $("#pkSheetProg").textContent = (DONATE_CTX.data.program || {}).program_name || "";
    payBox();
    sh.hidden = false; document.body.style.overflow = "hidden";
    checkLogin();
  }
  function closeDonate() { var sh = $("#pkSheet"); if (sh) sh.hidden = true; document.body.style.overflow = ""; }
  // audit 2026-11-11 (T3): status akun — login saja belum cukup, akun Rescue-Net harus aktif
  async function rnAccountStatus() {
    try { return await window.RN_FRAPPE.call("rescue_net.api_auth.account_status", {}); } catch (e) { return { logged_in: false }; }
  }
  function rnRegMsg(st) {
    return st.rn_status === "pending"
      ? "Akun Rescue-Net Anda masih menunggu verifikasi admin. Fitur ini bisa dipakai setelah akun aktif."
      : 'Akun Anda sudah login tetapi belum terdaftar di Rescue-Net. <a href="auth.html#daftar">Lengkapi pendaftaran</a>.';
  }
  async function checkLogin() {
    var st = await rnAccountStatus();
    var logged = !!(st.logged_in && st.registered);
    $("#pkLoginNote").hidden = logged;
    if (st.logged_in && !st.registered) $("#pkLoginNote").innerHTML = rnRegMsg(st);
    $("#donateForm").hidden = !logged;
    var lb = $("#pkLoginBtn"); if (lb) lb.href = "auth.html?next=" + encodeURIComponent(location.pathname.split("/").pop() + location.search);
  }
  function wireDonateSheet() {
    if (document.body.dataset.pkSheet) return; document.body.dataset.pkSheet = "1";
    document.addEventListener("click", function (e) {
      if (e.target.closest("[data-open-donate]")) { e.preventDefault(); openDonate(); return; }
      if (e.target.closest("[data-close-donate]") || e.target.id === "pkSheet") { closeDonate(); return; }
      var pre = e.target.closest("#pkPresets [data-amt]");
      if (pre) {
        document.querySelectorAll("#pkPresets [data-amt]").forEach(function (x) { x.classList.toggle("is-on", x === pre); });
        $("#pkCustom").value = ""; var af = $("#pkAmountField"); if (af) af.value = pre.getAttribute("data-amt"); return;
      }
      var m = e.target.closest(".pk-methods [data-method]");
      if (m && !m.disabled) { PK_METHOD = m.getAttribute("data-method"); payBox(); }
    });
    var c = $("#pkCustom");
    if (c) c.addEventListener("input", function () {
      document.querySelectorAll("#pkPresets [data-amt]").forEach(function (x) { x.classList.remove("is-on"); });
      var af = $("#pkAmountField"); if (af) af.value = c.value;
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDonate(); });
  }


  function wireChannel(data) {
    var cf = $("#channelForm"), ff = $("#kbFigForm"); if (!cf) return;
    var kbMode = data.donation_channel === "kitabisa", kb = data.kitabisa || {};
    $("#channelNow").textContent = kbMode ? "Melalui Kitabisa" : "Dikelola sendiri";
    cf.querySelectorAll("input[name=channel]").forEach(function (r) { r.checked = r.value === (kbMode ? "kitabisa" : "sendiri"); });
    cf.kitabisa_url.value = kb.url || "";
    var syncUrl = function () { $("#kbUrlWrap").hidden = !cf.querySelector("input[name=channel][value=kitabisa]").checked; };
    syncUrl();
    ff.hidden = !kbMode;
    if (kbMode) {
      ff.collected.value = kb.collected == null ? "" : kb.collected;
      ff.donor_count.value = kb.donor_count == null ? "" : kb.donor_count;
      ff.as_of.value = kb.figures_at || new Date().toISOString().slice(0, 10);
    }
    if (cf.dataset.wired) return; cf.dataset.wired = "1";
    cf.addEventListener("change", syncUrl);
    cf.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = $("#channelMsg"), ch = cf.querySelector("input[name=channel]:checked").value;
      m.textContent = "Menyimpan…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_donor_program.set_donation_channel",
          { donor_program: SELECTED, channel: ch, kitabisa_url: cf.kitabisa_url.value.trim() || null }, { method: "POST" });
        m.textContent = r && r.warning ? r.warning : "Tersimpan.";
        await selectProgram(SELECTED);
      } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
    });
    ff.addEventListener("submit", async function (e) {
      e.preventDefault();
      var m = $("#kbFigMsg"); m.textContent = "Menyimpan…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_donor_program.set_kitabisa_figures", { donor_program: SELECTED,
          collected: ff.collected.value || 0, donor_count: ff.donor_count.value || 0, as_of: ff.as_of.value || null }, { method: "POST" });
        m.textContent = "Tersimpan."; await selectProgram(SELECTED);
      } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
    });
    $("#kbRefresh").addEventListener("click", async function () {
      var m = $("#kbFigMsg"); m.textContent = "Membaca Kitabisa…";
      try { await window.RN_FRAPPE.call("rescue_net.api_donor_program.refresh_kitabisa", { donor_program: SELECTED }, { method: "POST" });
        m.textContent = "Diperbarui."; await selectProgram(SELECTED);
      } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
    });
  }

  function renderManagePanel(data) {
    var panel = $("#managePanel"); if (!panel) return;
    if (!data || !data.can_manage) { panel.hidden = true; return; }
    panel.hidden = false;
    var p = data.program || {}, b = data.bank || {}, docs = data.documents || {}, don = data.donations || {};
    var pending = (don.pending || []).length;
    var hasInfo = !!(p.description && (p.officer_in_charge_name || p.contact_person));
    var kbMode = data.donation_channel === "kitabisa";
    var steps = [
      ["done", "Cara pengelolaan donasi: " + (kbMode ? "Melalui Kitabisa" : "Dikelola sendiri (rekening/QRIS)"), kbMode ? "Ubah / isi angka Kitabisa" : "Ganti ke Kitabisa", "ringkasan", "#channelBox"],
      [hasInfo ? "done" : "todo", "Data program (deskripsi, sasaran, penanggung jawab)", "Ubah data", "ringkasan", "#infoBox"],
      [b.account_number ? "done" : "todo", b.account_number ? "Rekening: " + (b.bank_name || "") + " " + b.account_number : "Rekening penerimaan donasi belum diisi", b.account_number ? "Ubah rekening" : "Isi rekening", "ringkasan", "#bankForm"],
      [b.qris_url ? "done" : "todo", b.qris_url ? "QRIS sudah dipasang" : "QRIS belum diunggah", b.qris_url ? "Ganti QRIS" : "Unggah QRIS", "ringkasan", "#qrisForm"],
      [pending ? "alert" : "done", pending ? pending + " donasi masuk menunggu konfirmasi Anda" : "Tidak ada donasi menunggu konfirmasi", pending ? "Konfirmasi sekarang" : "Lihat donasi", "donatur", "#donationPendingSection"],
      [(docs.statements || []).length ? "done" : "todo", "Rekening koran untuk transparansi (" + (docs.statements || []).length + " berkas)", "Unggah rekening koran", "ringkasan", "#koranForm"]
    ];
    if (kbMode) steps = steps.filter(function (x) { return x[4] !== "#bankForm" && x[4] !== "#qrisForm"; });
    var verified = data.initiator_verified;
    $("#manageSteps").innerHTML = steps.map(function (s, i) {
      return '<li class="' + s[0] + '"><span>' + esc(s[1]) + '</span><button type="button" class="btn mini" data-manage-go="' + i + '">' + esc(s[2]) + "</button></li>";
    }).join("") + (verified ? "" : '<li class="alert"><span>Pemrakarsa belum terverifikasi — rekening &amp; QRIS baru tampil ke publik setelah verifikasi.</span></li>');
    $("#manageSteps").querySelectorAll("[data-manage-go]").forEach(function (btn) {
      btn.addEventListener("click", function () { var s = steps[+btn.getAttribute("data-manage-go")]; goManage(s[3], s[4]); });
    });
    var ST = { planned: "Direncanakan — belum menerima donasi", active: "Aktif — siap menerima donasi",
               completed: "Selesai", cancelled: "Dibatalkan" };
    var NEXT = { planned: ["active", "cancelled"], active: ["completed", "cancelled"], completed: ["active"], cancelled: [] };
    var cur = String(p.status || "planned").toLowerCase();
    $("#statusNow").textContent = "Status: " + (ST[cur] || cur);
    $("#statusBox").querySelectorAll("[data-set-status]").forEach(function (btn) {
      var to = btn.getAttribute("data-set-status");
      btn.hidden = (NEXT[cur] || []).indexOf(to) === -1;
      btn.onclick = async function () {
        var note = null;
        if (to === "cancelled") {
          note = window.prompt("Alasan pembatalan program (wajib, tampil di catatan program):", "");
          if (!note) return;
        } else if (window.confirm && !window.confirm("Ubah status program menjadi '" + ST[to] + "'?")) return;
        var m = $("#statusMsg"); m.textContent = "Menyimpan…";
        try {
          await window.RN_FRAPPE.call("rescue_net.api_donor_program.set_program_status", { donor_program: SELECTED, status: to, note: note }, { method: "POST" });
          m.textContent = "";
          await selectProgram(SELECTED);
        } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
      };
    });
    wireChannel(data);
    var f = $("#infoForm");
    if (f) {
      ["description", "target_beneficiaries", "target_description", "budget_target", "location", "start_date", "end_date",
       "officer_in_charge_name", "officer_in_charge_phone", "contact_person", "contact_phone"].forEach(function (k) {
        if (f[k]) f[k].value = p[k] == null ? "" : (k === "budget_target" && !p[k] ? "" : String(p[k]).slice(0, k.indexOf("date") > -1 ? 10 : 4000));
      });
      if (!f.dataset.wired) {
        f.dataset.wired = "1";
        f.addEventListener("submit", async function (e) {
          e.preventDefault();
          var m = $("#infoMsg"), vals = {};
          Array.prototype.forEach.call(f.elements, function (el) { if (el.name) vals[el.name] = el.value; });
          m.textContent = "Menyimpan…";
          try {
            await window.RN_FRAPPE.call("rescue_net.api_donor_program.update_program_info", { donor_program: SELECTED, values: JSON.stringify(vals) }, { method: "POST" });
            m.textContent = "Tersimpan.";
            await selectProgram(SELECTED);
          } catch (err) { m.textContent = "Gagal: " + ((err && err.message) || err); }
        });
      }
    }
    if (!panel.dataset.autoscrolled && /[?&]kelola=1\b/.test(location.search)) {
      panel.dataset.autoscrolled = "1";
      setTimeout(function () { panel.scrollIntoView({ behavior: "smooth", block: "start" }); }, 200);
    }
  }

  // ---- Ulasan publik (owner 2026-11-02 22:40, dikerjakan 2026-11-09) ----
  var REV_RATING = 0;
  function stars(n) { var o = ""; for (var i = 1; i <= 5; i++) o += i <= n ? "★" : "☆"; return o; }
  async function loadReviews(name) {
    var box = $("#ulasan"); if (!box) return;
    var r;
    try { r = await window.RN_FRAPPE.call("rescue_net.api_donor_program.program_reviews", { donor_program: name }); }
    catch (e) { $("#revList").innerHTML = '<p class="rn-muted">Ulasan belum bisa dimuat.</p>'; return; }
    if (SELECTED !== name) return;
    $("#tabRevCount").textContent = r.count ? "(" + r.count + ")" : "";
    $("#revAvg").textContent = r.count ? stars(Math.round(r.average)) + " " + String(r.average).replace(".", ",") + " · " + r.count + " ulasan" : "Belum ada ulasan";
    $("#revDist").innerHTML = r.count ? [5, 4, 3, 2, 1].map(function (k) {
      var c = r.distribution[String(k)] || 0, pct = Math.round(c * 100 / r.count);
      return '<div class="rn-rev-bar"><span>' + k + '★</span><i><b style="width:' + pct + '%"></b></i><span>' + c + "</span></div>";
    }).join("") : "";
    $("#revForm").hidden = !r.can_review;
    $("#revLogin").hidden = !r.login_required;
    $("#revOwnerNote").hidden = !r.can_reply;
    REV_RATING = r.mine ? r.mine.rating : 0;
    paintStars();
    var f = $("#revForm");
    if (r.mine) { f.comment.value = r.mine.comment || ""; f.anonymous.checked = !!r.mine.anonymous; $("#revSubmit").textContent = "Perbarui Ulasan"; }
    else { f.comment.value = ""; f.anonymous.checked = false; $("#revSubmit").textContent = "Kirim Ulasan"; }
    $("#revList").innerHTML = r.reviews.length ? r.reviews.map(function (v) {
      return '<div class="rn-rev-item' + (v.hidden ? " is-hidden" : "") + '">' +
        '<div class="rn-rev-head"><b>' + esc(v.reviewer) + (v.mine ? " (Anda)" : "") + '</b><span class="rn-rev-stars">' + stars(v.rating) + "</span><small>" + esc(v.date) + "</small>" +
        (v.hidden ? ' <span class="chip">disembunyikan</span>' : "") + "</div>" +
        (v.comment ? "<p>" + esc(v.comment) + "</p>" : "") +
        (v.reply ? '<div class="rn-rev-reply"><b>Jawaban penyelenggara</b>' + (v.reply_date ? " <small>" + esc(v.reply_date) + "</small>" : "") + "<p>" + esc(v.reply) + "</p></div>" : "") +
        (r.can_reply ? '<form class="rn-rev-replyform" data-rev="' + esc(v.name) + '"><textarea maxlength="1000" rows="2" placeholder="Tulis jawaban…">' + esc(v.reply || "") + '</textarea><button class="btn ghost mini" type="submit">' + (v.reply ? "Ubah Jawaban" : "Jawab") + "</button></form>" : "") +
        (r.can_moderate ? '<button class="btn ghost mini" type="button" data-rev-mod="' + esc(v.name) + '" data-st="' + (v.hidden ? "published" : "hidden") + '">' + (v.hidden ? "Tampilkan lagi" : "Sembunyikan") + "</button>" : "") +
        "</div>";
    }).join("") : '<p class="rn-muted">Belum ada ulasan untuk program ini.</p>';
  }
  function paintStars() {
    var b = document.querySelectorAll("#revStars button");
    Array.prototype.forEach.call(b, function (x) { x.classList.toggle("on", Number(x.dataset.v) <= REV_RATING); x.setAttribute("aria-pressed", Number(x.dataset.v) <= REV_RATING ? "true" : "false"); });
  }
  function setupReviews() {
    var st = $("#revStars"); if (!st) return;
    st.addEventListener("click", function (e) { var b = e.target.closest("button[data-v]"); if (!b) return; REV_RATING = Number(b.dataset.v); paintStars(); });
    $("#revForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      var msg = $("#revMsg");
      if (!REV_RATING) { msg.textContent = "Pilih nilai bintang dulu."; return; }
      msg.textContent = "Mengirim…";
      try {
        await window.RN_FRAPPE.call("rescue_net.api_donor_program.submit_review", { donor_program: SELECTED, rating: REV_RATING,
          comment: this.comment.value, anonymous: this.anonymous.checked ? 1 : 0 }, { method: "POST" });
        msg.textContent = "Terima kasih, ulasan tersimpan.";
        loadReviews(SELECTED);
      } catch (err) { msg.textContent = "Gagal: " + ((err && err.message) || err); }
    });
    $("#revList").addEventListener("submit", async function (e) {
      var f = e.target.closest(".rn-rev-replyform"); if (!f) return;
      e.preventDefault();
      try {
        await window.RN_FRAPPE.call("rescue_net.api_donor_program.reply_review", { review: f.dataset.rev, reply: f.querySelector("textarea").value }, { method: "POST" });
        loadReviews(SELECTED);
      } catch (err) { alert("Gagal: " + ((err && err.message) || err)); }
    });
    $("#revList").addEventListener("click", async function (e) {
      var b = e.target.closest("[data-rev-mod]"); if (!b) return;
      var reason = b.dataset.st === "hidden" ? prompt("Alasan menyembunyikan ulasan ini?") : "";
      if (b.dataset.st === "hidden" && !reason) return;
      try {
        await window.RN_FRAPPE.call("rescue_net.api_donor_program.moderate_review", { review: b.dataset.revMod, status: b.dataset.st, reason: reason }, { method: "POST" });
        loadReviews(SELECTED);
      } catch (err) { alert("Gagal: " + ((err && err.message) || err)); }
    });
    if (location.hash === "#ulasan") setTimeout(function () { var t = $("#detailTabs .rn-tab[data-tab=ulasan]"); if (t) t.click(); }, 800);
  }

  async function selectProgram(name) {
    SELECTED = name;
    renderList();
    try {
      var data = await window.RN_FRAPPE.call(DETAIL_METHOD, { program: name });
      renderDetail(data);
      renderManagePanel(data);
      loadReviews(name);
    } catch (err) {
      console.error("[program detail]", err);
    }
  }

  async function loadBoard() {
    var data = await window.RN_FRAPPE.call(BOARD_METHOD, { disaster_event: getEventId2() });
    BOARD_CACHE = data;
    $("#programUpdated").textContent = "Program · Diperbarui " + String(data.generated_at || "").slice(11, 16);
    $("#programStatus").textContent = fmt((data.programs || []).length) + " program ditemukan.";

    renderKpi(data.totals || {});
    renderList();

    var wanted = new URLSearchParams(location.search).get("program");
    if (wanted && !SELECTED) {
      selectProgram(wanted);            // tautan langsung ke satu program (juga tujuan login pemrakarsa)
    } else if (data.programs && data.programs.length && !SELECTED) {
      // buka program yang masih menerima donasi lebih dulu (bukan yang batal/selesai)
      var open = data.programs.filter(function (p) { return !/^(cancelled|completed)$/i.test(String(p.status || "")); });
      selectProgram((open[0] || data.programs[0]).name);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return;
    document.querySelectorAll(".rn-pk-kpi .rn-kpi-btn").forEach(function (btn) {
      btn.addEventListener("click", function () { openDrill(btn.getAttribute("data-kpi")); });
    });
    document.querySelectorAll("#programDrill [data-close]").forEach(function (el) { el.addEventListener("click", closeDrill); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrill(); });
    setupFilterTabs();
    setupDetailTabs();
    setupReviews();
    wireDonationActions();
    wireDonateSheet();
    wireDocForms();
    wirePlanEditing();
    setupTopNav().then(function () { return loadBoard(); }).catch(function (err) { console.error("[program board]", err); });
  });
})();

function getEventId() {
  return (
    new URLSearchParams(
      location.search
    ).get("event") ||
    "event-sim-001"
  );
}


function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}


function rupiah(n) {
  return new Intl.NumberFormat(
    "id-ID"
  ).format(
    Number(n || 0)
  );
}


function setText(id, value) {
  const el =
    document.getElementById(id);

  if (el) {
    el.textContent = value;
  }
}


function programCard(p) {
  return `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(p.program_name)}</h4>

          <p>
            Type: ${safe(p.program_type)}<br>
            Owner:
            ${safe(p.owner_type)} /
            ${safe(p.owner_id)}<br>
            Target:
            ${rupiah(p.target_amount)}
            ${safe(p.target_unit)}<br>
            Progress:
            ${safe(p.progress_percent)}%
          </p>
        </div>

        <div class="chips">
          <span class="chip warning">
            ${safe(p.program_status || p.status)}
          </span>
        </div>
      </div>
    </article>
  `;
}


async function loadPrograms() {
  const eventId =
    getEventId();

  const target =
    document.getElementById(
      "programListLegacy"
    );

  // api_donor_program.context is login-only (it carries create-form context).
  // The modern board (loadBoard → program_board, guest-allowed) is the real
  // list; this legacy <details> directory just degrades to a hint for guests.
  let ctx;
  try {
    ctx =
      await RN_FRAPPE.call(
        "rescue_net.api_donor_program.context",
        {
          disaster_event:
            eventId
        }
      );
  } catch (e) {
    if (target) {
      target.innerHTML = `
        <article class="event-card">
          <h4>Login untuk direktori lengkap</h4>
          <p>Daftar program di atas tetap tampil untuk umum.
             Masuk sebagai pengelola untuk direktori &amp; form program.</p>
        </article>`;
    }
    return;
  }

  const programs =
    ctx.programs || [];

  if (target) {
    target.innerHTML =
      programs.length
        ? programs
            .map(programCard)
            .join("")
        : `
          <article class="event-card">
            <h4>Belum ada program</h4>
            <p>
              Belum ada Donor Program pada event ini.
            </p>
          </article>
        `;
  }
}


function setupProgramForm() {
  // owner 2026-11-08: a real member (e.g. LAZISMU) picks its organisation instead of typing an ID
  const form = document.getElementById("programForm");
  if (!form) return;
  const sel = document.getElementById("ownerSelect");
  const msg = document.getElementById("programFormMsg");
  RN_FRAPPE.call("rescue_net.api_community_cluster.my_memberships", {})
    .then(r => {
      const orgs = ((r && r.memberships) || []).filter(m => m.status === "approved");
      sel.innerHTML = orgs.length
        ? orgs.map(m => `<option value="${safe(m.organization)}">${safe(m.organization_title || m.organization)}</option>`).join("")
        : '<option value="">Anda belum menjadi anggota organisasi yang disetujui</option>';
    })
    .catch(() => { sel.innerHTML = '<option value="">Login dulu untuk membuat program</option>'; });
  const ch = document.getElementById("createChannel"), kbw = document.getElementById("createKbWrap");
  if (ch && kbw) ch.addEventListener("change", () => { kbw.hidden = ch.value !== "kitabisa"; form.kitabisa_url.required = ch.value === "kitabisa"; });
  form.addEventListener("submit", async e => {
    e.preventDefault();
    if (!sel.value) { msg.textContent = "Pilih organisasi dulu."; return; }
    msg.textContent = "Menyimpan…";
    try {
      const r = await RN_FRAPPE.call("rescue_net.api_donor_program.create_special_program", {
        disaster_event: getEventId(),
        owner_type: "organization",
        owner_id: sel.value,
        program_name: form.program_name.value.trim(),
        description: form.description.value.trim() || null,
        target_beneficiaries: form.target_beneficiaries.value.trim() || null,
        target_location: form.target_location.value.trim() || null,
        budget_target: Number(form.budget_target.value || 0),
        status: "active"
      }, { method: "POST" });
      const id = r && (r.program || r.id);
      if (id && form.donation_channel && form.donation_channel.value === "kitabisa") {
        try {
          const c = await RN_FRAPPE.call("rescue_net.api_donor_program.set_donation_channel",
            { donor_program: id, channel: "kitabisa", kitabisa_url: form.kitabisa_url.value.trim() }, { method: "POST" });
          if (c && c.warning) alert(c.warning);
        } catch (e2) { alert("Program dibuat, tetapi link Kitabisa belum tersimpan: " + ((e2 && e2.message) || e2)); }
      }
      msg.textContent = "Program dibuat. Membuka panel kelola…";
      const url = new URL(location.href);
      if (id) { url.searchParams.set("program", id); url.searchParams.set("kelola", "1"); }
      location.href = url.toString();
    } catch (err) {
      msg.textContent = "Gagal: " + ((err && err.message) || err);
    }
  });
}


function setupUpdateForm() {
  const form =
    document.getElementById(
      "programUpdateForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_donor_program." +
        "create_update",
        {
          program:
            form.program_id.value.trim(),

          update_type:
            form.update_type.value.trim(),

          progress_percent:
            Number(
              form.progress_percent.value ||
              0
            ),

          amount_spent:
            Number(
              form.amount_spent.value ||
              0
            ),

          update_title:
            form.update_title.value
              .trim(),

          update_notes:
            form.update_notes.value
              .trim()
        },
        {
          method: "POST"
        }
      );

      form.reset();

      await loadPrograms();
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  () => {
    if (!window.RN_FRAPPE) {
      return;
    }

    setupProgramForm();
    setupUpdateForm();

    const refresh =
      document.getElementById(
        "refreshPrograms"
      );

    if (refresh) {
      refresh.addEventListener(
        "click",
        () =>
          loadPrograms()
            .catch(err => console.error(err))
      );
    }

    loadPrograms()
      .catch(err => console.error(err));
  }
);
