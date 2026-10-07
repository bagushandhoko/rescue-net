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
  function getEventId2() { return new URLSearchParams(window.location.search).get("event") || "event-sim-001"; }
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
          '<span class="chip ' + (STATUS_CHIP[p.status] || "") + '">' + (STATUS_LABEL[p.status] || p.status) + "</span></span>" +
        '<span class="rn-pk-card-meta">' + esc(p.category) + "<br>" + esc(p.location) +
          ' · <i class="rn-pk-kind">' + (p.program_kind === "project" ? "Project Base" : "Cash Base") + "</i></span>" +
        '<span class="rn-pk-bar"><span style="width:' + p.progress_percent + '%"></span></span>' +
        '<span class="rn-pk-bar-label"><span>' + p.progress_percent + "%</span></span></span></button>"
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
        ["ringkasan", "rencana", "anggaran", "riwayat"].forEach(function (k) {
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
    if (window.RNIconFill) window.RNIconFill(document);
  }

  function renderDonations(d) {
    var wall = $("#donationWall");
    var pub = d.public || [];
    wall.innerHTML = pub.length
      ? pub.map(function (r) {
          return '<article class="event-card"><div class="event-main"><div>' +
            "<h4>" + esc(r.donor_name) + "</h4>" +
            (r.message ? "<p>" + esc(r.message) + "</p>" : "") +
            '<p class="rn-muted">' + shortDate(r.confirmed_at) + "</p></div>" +
            '<div class="chips"><span class="chip ok">' + rp(r.amount) + "</span></div>" +
            "</div></article>";
        }).join("")
      : '<p class="rn-muted">Belum ada donasi terkonfirmasi untuk program ini.</p>';

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

  async function selectProgram(name) {
    SELECTED = name;
    renderList();
    try {
      var data = await window.RN_FRAPPE.call(DETAIL_METHOD, { program: name });
      renderDetail(data);
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

    if (data.programs && data.programs.length && !SELECTED) {
      selectProgram(data.programs[0].name);
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
    wireDonationActions();
    wirePlanEditing();
    loadBoard().catch(function (err) { console.error("[program board]", err); });
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
  const form =
    document.getElementById(
      "programForm"
    );

  if (!form) return;

  form.addEventListener(
    "submit",
    async e => {
      e.preventDefault();

      await RN_FRAPPE.call(
        "rescue_net.api_donor_program." +
        "create_program",
        {
          disaster_event:
            getEventId(),

          owner_type:
            form.owner_type?.value ||
            "organization",

          owner_id:
            form.owner_id.value.trim(),

          program_name:
            form.program_name.value.trim(),

          program_type:
            form.program_type.value.trim(),

          target_description:
            form.target_description.value
              .trim(),

          target_amount:
            Number(
              form.target_amount.value || 0
            ),

          target_unit:
            form.target_unit?.value ||
            "IDR",

          location:
            form.location?.value?.trim() ||
            null,

          notes:
            form.notes.value.trim()
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
