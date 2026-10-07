/* Search & Found — mock-up layout (pass 2, 2026-10-07).
 * KPI row, kind tabs, Papan Pencocokan, Reunifikasi aktif, Status Identifikasi,
 * Klaim & Serah Terima, Foto Bukti, Aksi Verifikasi. Names are never on the
 * public board: the code, age and gender are; an operator opens the full
 * record through restricted_record ("Tinjau Detail"). */
(function () {
  "use strict";
  var U = window.RNUI;
  var esc = U.esc;
  var API = "rescue_net.api_search_found.";
  var CTX = null;
  var TAB = "orang";
  var SHOW_ALL = false;
  var BOARD_LIMIT = 2;

  var ID_STATES = [
    ["belum_teridentifikasi", "Belum Teridentifikasi", "#f59e0b"],
    ["proses_identifikasi", "Proses Identifikasi", "#6b8fd6"],
    ["teridentifikasi", "Teridentifikasi", "#2fa66a"],
    ["tidak_dapat_diidentifikasi", "Tidak Dapat Diidentifikasi", "#9aa0a6"]
  ];
  var CLAIM_LABEL = {
    menunggu_verifikasi: ["Menunggu Verifikasi", "warning"], terverifikasi: ["Terverifikasi", "good"],
    siap_diserahkan: ["Siap Diserahkan", "info"], selesai: ["Selesai", "good"], ditolak: ["Ditolak", "danger"]
  };
  var CLAIM_NEXT = { menunggu_verifikasi: "terverifikasi", terverifikasi: "siap_diserahkan", siap_diserahkan: "selesai" };
  var CLAIM_NEXT_LABEL = { terverifikasi: "Verifikasi", siap_diserahkan: "Siap serah", selesai: "Selesaikan" };

  function $(id) { return document.getElementById(id); }
  function call(method, args, post) {
    return window.RN_FRAPPE.call(API + method, args || {}, post ? { method: "POST" } : undefined);
  }
  function statusMsg(msg) { var el = $("sfStatus"); if (el) el.textContent = msg; }
  function errMsg(e) { return (e && e.message) || String(e); }
  function safe(v) { return v === null || v === undefined || v === "" ? "n/a" : v; }
  function eventId() { return U.eventId("event-sim-001"); }
  function rowId(r) { return r ? r.name || r.id || r.legacy_id || "" : ""; }
  function reportStatus(r) { return r ? r.report_status || r.status || "" : ""; }
  function matchStatus(r) { return r ? r.match_status || r.status || "" : ""; }
  function canManage() { return CTX && CTX.mode === "manager"; }
  function isPublic() { return !CTX || CTX.mode === "public"; }

  function genderLabel(g) { return g === "laki-laki" ? "L" : g === "perempuan" ? "P" : ""; }
  function who(b) {
    var bits = [b.code || "-"];
    var age = b.age_years ? b.age_years + " th" : "";
    var g = genderLabel(b.gender);
    if (age || g) bits.push("(" + [age, g].filter(Boolean).join(", ") + ")");
    return bits.join(" ");
  }
  function shortWhen(s) {
    if (!s) return "";
    var t = String(s).replace("T", " ");
    return t.slice(0, 16);
  }
  function initials(b) { return (b.code || "?").replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase(); }
  function avatar(b, kind) {
    var icon = kind === "aset" ? "box" : kind === "hewan" ? "heart" : "user";
    return '<span class="rn-sf-av"><span class="rn-sf-ico" data-icon="' + icon + '"></span><em>' + esc(initials(b)) + "</em></span>";
  }

  /* ---------- derive the board from older backends (no kpis / board keys) ---------- */
  function derive(ctx) {
    var missing = ctx.missing || [], found = ctx.found || [], matches = ctx.matches || [];
    function n(rows, kind) { return rows.filter(function (r) { return (r.subject_type || "orang") === kind; }).length; }
    var reunited = matches.filter(function (m) { return matchStatus(m) === "reunited"; }).length;
    ctx.kpis = ctx.kpis || {
      orang_hilang: { n: n(missing, "orang") }, korban_ditemukan: { n: n(found, "orang") },
      belum_teridentifikasi: { n: n(found, "orang") }, reunifikasi: { n: reunited },
      aset_hilang: { n: n(missing, "aset") }, barang_ditemukan: { n: n(found, "aset") }
    };
    ctx.board = ctx.board || { orang: { possible: [], active: [] }, aset: { possible: [], active: [] }, hewan: { possible: [], active: [] } };
    ctx.identification = ctx.identification || { belum_teridentifikasi: n(found, "orang"), proses_identifikasi: 0, teridentifikasi: 0, tidak_dapat_diidentifikasi: 0 };
    ctx.claims = ctx.claims || [];
    ctx.photos = ctx.photos || { count: 0, items: [] };
    return ctx;
  }

  /* ---------- KPI ---------- */
  function setKpi(idNum, idDelta, k) {
    var v = $(idNum), d = $(idDelta);
    if (v) v.textContent = k ? U.fmt(k.n) : "-";
    if (d) {
      var add = k && k.new_24h;
      d.textContent = add ? "↑ " + add + " baru 24 jam" : "tetap 24 jam";
      d.className = add ? "rn-sf-up" : "";
    }
  }
  function renderKpis() {
    var k = CTX.kpis;
    setKpi("kpiMissing", "kpiMissingD", k.orang_hilang);
    setKpi("kpiFound", "kpiFoundD", k.korban_ditemukan);
    setKpi("kpiUnident", "kpiUnidentD", k.belum_teridentifikasi);
    setKpi("kpiReunited", "kpiReunitedD", k.reunifikasi);
    setKpi("kpiAsset", "kpiAssetD", k.aset_hilang);
    setKpi("kpiItems", "kpiItemsD", k.barang_ditemukan);
  }

  /* ---------- Papan Pencocokan ---------- */
  function scoreBadge(s) {
    if (s == null) return "";
    var tone = s >= 80 ? "hi" : s >= 55 ? "mid" : "lo";
    return '<span class="rn-sf-score ' + tone + '">' + esc(s) + "%</span>";
  }
  function pairCard(p, idx, kind) {
    var m = p.missing, f = p.found;
    var btns = '<button type="button" class="btn rn-sf-b" data-act="detail" data-i="' + idx + '">Tinjau Detail</button>';
    if (canManage()) btns += '<button type="button" class="btn primary rn-sf-b" data-act="case" data-i="' + idx + '">Buat Kasus Reunifikasi</button>';
    return '<article class="rn-sf-pair">' +
      '<div class="rn-sf-faces">' + avatar(m, kind) + avatar(f, kind) + scoreBadge(p.score) + "</div>" +
      '<div class="rn-sf-pairbody"><div class="rn-sf-pairtext">' +
      "<div><b>" + esc(who(m)) + "</b><small>Dilaporkan hilang " + esc(shortWhen(m.time) || "-") + "</small>" +
      (m.place ? '<small><span class="rn-sf-pin" data-icon="map-pin"></span>' + esc(m.place) + "</small>" : "") + "</div>" +
      "<div><small>Ditemukan di " + esc(f.place || "-") + "</small><small>" + esc(shortWhen(f.time)) + "</small></div></div>" +
      '<div class="rn-sf-pairbtns">' + btns + "</div></div></article>";
  }
  function renderBoard() {
    var list = $("boardList"), more = $("boardMore"), title = $("boardTitle");
    if (!list) return;
    var kind = TAB === "korban" ? "orang" : TAB;
    if (TAB === "korban") {
      title.textContent = "Korban Ditemukan";
      var rows = (CTX.found || []).filter(function (f) { return (f.subject_type || "orang") === "orang"; });
      list.innerHTML = rows.length ? rows.map(foundRow).join("") : emptyMsg("Belum ada korban ditemukan yang dilaporkan.");
      more.hidden = true;
      return;
    }
    title.textContent = TAB === "aset" ? "Papan Pencocokan Aset / Barang" : TAB === "hewan" ? "Papan Pencocokan Hewan" : "Papan Pencocokan (Possible Matches)";
    var pairs = ((CTX.board || {})[kind] || { possible: [] }).possible;
    CTX._pairs = pairs;
    var shown = SHOW_ALL ? pairs : pairs.slice(0, BOARD_LIMIT);
    list.innerHTML = shown.length ? shown.map(function (p, i) { return pairCard(p, i, kind); }).join("") :
      emptyMsg("Belum ada kandidat pencocokan. Kandidat muncul otomatis saat ada laporan hilang dan ditemukan yang mirip.");
    more.hidden = pairs.length <= BOARD_LIMIT;
    more.textContent = SHOW_ALL ? "Tampilkan lebih sedikit" : "+ Lihat semua kemungkinan kecocokan (" + pairs.length + ")";
  }
  function emptyMsg(t) { return '<p class="rn-muted rn-sf-empty">' + esc(t) + "</p>"; }
  function foundRow(f) {
    var st = f.identification_status || "belum_teridentifikasi";
    if (f.report_status === "reunited") st = "teridentifikasi";
    var lab = (ID_STATES.filter(function (s) { return s[0] === st; })[0] || ID_STATES[0])[1];
    var sel = "";
    if (canManage()) {
      sel = '<select class="rn-sf-idsel" data-found="' + esc(f.name) + '">' + ID_STATES.map(function (s) {
        return '<option value="' + s[0] + '"' + (s[0] === st ? " selected" : "") + ">" + esc(s[1]) + "</option>";
      }).join("") + "</select>";
    }
    return '<article class="rn-sf-reunirow">' + avatar({ code: f.person_code }, "orang") +
      "<div><b>" + esc(who({ code: f.person_code, age_years: f.age_years, gender: f.gender })) + "</b><small>" +
      esc(f.found_location || "-") + " · " + esc(shortWhen(f.found_time || f.observed_at)) + "</small></div>" +
      (sel || '<span class="chip warning">' + esc(lab) + "</span>") + "</article>";
  }

  /* ---------- Reunifikasi aktif ---------- */
  function renderReuni() {
    var el = $("reuniList");
    var kind = TAB === "korban" ? "orang" : TAB;
    var rows = ((CTX.board || {})[kind] || { active: [] }).active;
    el.innerHTML = rows.length ? rows.map(function (p) {
      var btn = canManage() && p.match
        ? '<button type="button" class="btn mini" data-act="reunite" data-match="' + esc(p.match) + '">Tandai bersatu</button>' : "";
      return '<article class="rn-sf-reunirow">' + avatar(p.missing, kind) +
        "<div><b>" + esc(who(p.missing)) + "</b><small>Ditemukan di " + esc(p.found.place || "-") + "</small><small>" +
        esc(shortWhen(p.found.time)) + "</small>" + btn + "</div>" +
        '<span class="chip good">Siap Reunifikasi</span></article>';
    }).join("") : emptyMsg("Belum ada kasus reunifikasi aktif.");
  }

  /* ---------- Status identifikasi (donut) ---------- */
  function renderIdent() {
    var counts = CTX.identification || {};
    var total = ID_STATES.reduce(function (a, s) { return a + (counts[s[0]] || 0); }, 0);
    var svg = $("idDonut"), legend = $("idLegend");
    var R = 42, C = 2 * Math.PI * R, off = 0, out = "";
    if (!total) {
      out = '<circle cx="60" cy="60" r="' + R + '" fill="none" stroke="#eadfd9" stroke-width="16"/>';
    } else {
      ID_STATES.forEach(function (s) {
        var n = counts[s[0]] || 0;
        if (!n) return;
        var len = (n / total) * C;
        out += '<circle cx="60" cy="60" r="' + R + '" fill="none" stroke="' + s[2] + '" stroke-width="16" stroke-dasharray="' +
          len.toFixed(2) + " " + (C - len).toFixed(2) + '" stroke-dashoffset="' + (-off).toFixed(2) + '" transform="rotate(-90 60 60)"/>';
        off += len;
      });
    }
    svg.innerHTML = out;
    legend.innerHTML = ID_STATES.map(function (s) {
      var n = counts[s[0]] || 0;
      return '<li><i style="background:' + s[2] + '"></i><span>' + esc(s[1]) + "</span><b>" + n + " (" +
        (total ? Math.round((n / total) * 100) : 0) + "%)</b></li>";
    }).join("");
    $("idTotal").textContent = U.fmt(total);
  }

  /* ---------- Klaim ---------- */
  function renderClaims() {
    var body = $("claimBody");
    var rows = CTX.claims || [];
    body.innerHTML = rows.length ? rows.slice(0, 6).map(function (c) {
      var st = CLAIM_LABEL[c.claim_status] || [c.claim_status || "-", "warning"];
      var next = CLAIM_NEXT[c.claim_status];
      var act = canManage() && next
        ? '<button type="button" class="btn mini" data-act="claim" data-claim="' + esc(c.name) + '" data-to="' + next + '">' + esc(CLAIM_NEXT_LABEL[next]) + "</button>" : "";
      return "<tr><td>" + esc(c.claim_code) + "</td><td>" + esc(c.item_description) + "<small>" + esc(c.kind === "aset" ? "Aset" : "Barang") + "</small>" +
        '</td><td><span class="chip ' + st[1] + '">' + esc(st[0]) + "</span>" + act + "</td><td>" + esc(c.location_text || "-") + "</td><td>" +
        esc(U.shortDate(c.observed_at)) + "</td></tr>";
    }).join("") : '<tr><td colspan="5" class="rn-muted">Belum ada klaim.</td></tr>';
  }

  /* ---------- Foto bukti ---------- */
  function renderPhotos() {
    var grid = $("photoGrid"), p = CTX.photos || { count: 0, items: [] };
    var ev = "evidence.html?event=" + encodeURIComponent(eventId());
    $("photoAll").href = ev; $("photoAdd").href = ev; $("actEvidence").href = ev;
    if (p.items && p.items.length) {
      grid.innerHTML = p.items.map(function (i) {
        return '<figure><img loading="lazy" src="' + esc(i.url) + '" alt="' + esc(i.caption || "Foto bukti") + '"><figcaption>' +
          esc(i.posko || "") + "<br>" + esc(shortWhen(i.at)) + "</figcaption></figure>";
      }).join("");
    } else {
      var n = Math.min(p.count || 0, 6), tiles = "";
      for (var i = 0; i < n; i++) tiles += '<figure class="rn-sf-ph"><span class="rn-sf-ico" data-icon="camera"></span><figcaption>Terbatas</figcaption></figure>';
      grid.innerHTML = tiles + '<p class="rn-muted rn-sf-empty">' + (p.count
        ? U.fmt(p.count) + " foto bukti tersimpan. Foto wajah hanya tampil untuk operator berwenang."
        : "Belum ada foto bukti.") + "</p>";
    }
  }

  /* ---------- All reports (operator follow-up) ---------- */
  function evidenceLink(type, id) {
    if (!id) return "";
    return '<br><a href="evidence.html?event=' + encodeURIComponent(eventId()) + "&object_type=" + encodeURIComponent(type) +
      "&object_id=" + encodeURIComponent(id) + '">Add Evidence</a>';
  }
  function card(title, body, chip) {
    return '<article class="event-card"><div class="event-main"><div><h4>' + title + "</h4><p>" + body + "</p></div>" +
      '<div class="chips">' + (chip ? '<span class="chip warning">' + esc(chip) + "</span>" : "") + "</div></div></article>";
  }
  function renderLists() {
    var missing = CTX.missing || [], found = CTX.found || [], matches = CTX.matches || [];
    $("missingReports").innerHTML = missing.length ? missing.map(function (m) {
      return card(esc(safe(m.person_code)) + " · " + esc((m.subject_type || "orang")),
        "Last seen: " + esc(safe(m.last_seen_location)) + " · " + esc(safe(m.last_seen_time)) + "<br>" + esc(safe(m.description)) +
        "<br>Clothing: " + esc(safe(m.clothing_description)) + evidenceLink("missing_person_report", rowId(m)), reportStatus(m));
    }).join("") : card("Belum ada laporan hilang", "Tambahkan laporan hilang.", "empty");
    $("foundReports").innerHTML = found.length ? found.map(function (f) {
      return card(esc(safe(f.person_code)) + " · " + esc((f.subject_type || "orang")),
        "Found: " + esc(safe(f.found_location)) + " · " + esc(safe(f.found_time)) + "<br>" + esc(safe(f.description)) +
        "<br>Clothing: " + esc(safe(f.clothing_description)) + evidenceLink("found_person_report", rowId(f)), reportStatus(f));
    }).join("") : card("Belum ada laporan ditemukan", "Tambahkan laporan ditemukan.", "empty");
    $("matches").innerHTML = matches.length ? matches.map(function (m) {
      var id = rowId(m), st = matchStatus(m), btn = "";
      if (canManage()) {
        if (st === "proposed") btn += '<button type="button" class="btn primary" data-act="matchto" data-match="' + esc(id) + '" data-to="confirmed">Konfirmasi</button>';
        if (st === "confirmed") btn += '<button type="button" class="btn primary" data-act="matchto" data-match="' + esc(id) + '" data-to="reunited">Mark Reunited</button>';
        if (st === "proposed" || st === "confirmed") btn += '<button type="button" class="btn" data-act="matchto" data-match="' + esc(id) + '" data-to="rejected">Reject</button>';
      }
      return '<article class="event-card"><div class="event-main"><div><h4>' + esc(safe(m.missing_person_code || m.missing_report)) + " ↔ " +
        esc(safe(m.found_person_code || m.found_report)) + "</h4><p>Skor: " + esc(m.match_score == null ? "n/a" : m.match_score + "%") +
        " · Basis: " + esc(safe(m.match_basis || m.match_reason)) + "</p></div>" +
        '<div class="chips"><span class="chip warning">' + esc(safe(st)) + "</span>" + btn + "</div></div></article>";
    }).join("") : card("Belum ada match", "Match dibuat dari papan pencocokan.", "empty");
  }

  function renderAll() {
    renderKpis(); renderBoard(); renderReuni(); renderIdent(); renderClaims(); renderPhotos(); renderLists();
    var pub = isPublic();
    ["missingDrawer", "foundDrawer", "claimDrawer"].forEach(function (id) { var d = $(id); if (d) d.hidden = pub; });
    var acts = $("sfActions"); if (acts) acts.hidden = pub;
    $("sfUpdated").textContent = CTX.generated_at ? "Terakhir diperbarui: " + shortWhen(CTX.generated_at) : "";
    if (window.RNIconFill) window.RNIconFill(document);
    statusMsg(pub ? "Mode publik: data pribadi disembunyikan. Login untuk melapor." : "Dimuat.");
  }

  /* ---------- Drill / actions ---------- */
  function openDrill(title, sub, html) {
    $("sfDetailTitle").textContent = title; $("sfDetailSub").textContent = sub || ""; $("sfDetailBody").innerHTML = html;
    $("sfDetail").hidden = false; document.body.style.overflow = "hidden";
  }
  function closeDrill() { $("sfDetail").hidden = true; document.body.style.overflow = ""; }

  function side(label, b, rec) {
    var rows = [["Kode", b.code], ["Usia / jenis kelamin", [b.age_years ? b.age_years + " th" : "", b.gender || ""].filter(Boolean).join(" · ") || "-"],
      ["Lokasi", b.place], ["Waktu", shortWhen(b.time)], ["Pakaian", b.clothing], ["Ciri", b.description]];
    if (rec) {
      rows.splice(1, 0, ["Nama lengkap", rec.person_name || "-"]);
      if (rec.reporter) rows.push(["Pelapor", [rec.reporter.name, rec.reporter.contact].filter(Boolean).join(" · ") || "-"]);
    }
    return '<div class="rn-sf-side"><h4>' + esc(label) + "</h4><dl>" + rows.map(function (r) {
      return "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1] == null || r[1] === "" ? "-" : r[1]) + "</dd>";
    }).join("") + "</dl></div>";
  }
  async function showDetail(p) {
    var recM = null, recF = null;
    if (canManage()) {
      try {
        recM = await call("restricted_record", { doctype: "RN Missing Person Report", name: p.missing.id });
        recF = await call("restricted_record", { doctype: "RN Found Person Report", name: p.found.id });
      } catch (e) { /* no right on that posko: stay masked */ }
    }
    openDrill("Detail Kecocokan " + (p.score == null ? "" : p.score + "%"),
      canManage() ? "Data lengkap hanya untuk operator berwenang." : "Data pribadi disembunyikan. Login sebagai operator untuk detail lengkap.",
      '<div class="rn-sf-sides">' + side("Laporan hilang", p.missing, recM) + side("Laporan ditemukan", p.found, recF) + "</div>");
  }
  async function createCase(p, btn) {
    if (!window.confirm("Buat kasus reunifikasi untuk " + (p.missing.code || "") + " ↔ " + (p.found.code || "") + "?")) return;
    btn.disabled = true;
    try {
      var id = p.match;
      if (!id) id = (await call("propose_match", { missing_report: p.missing.id, found_report: p.found.id }, true)).match;
      if (p.status !== "confirmed") await call("update_match_status", { match: id, new_status: "confirmed", review_notes: "Kasus reunifikasi dibuat dari papan pencocokan." }, true);
      await load();
    } catch (e) { statusMsg(errMsg(e)); btn.disabled = false; }
  }
  async function setMatch(id, to) {
    var notes = to === "reunited" ? "Keluarga sudah dikonfirmasi dan dipertemukan." : to === "rejected" ? (window.prompt("Alasan penolakan", "") || "") : "";
    try { await call("update_match_status", { match: id, new_status: to, review_notes: notes }, true); await load(); }
    catch (e) { statusMsg(errMsg(e)); }
  }

  function onClick(e) {
    var t = e.target.closest("[data-act],[data-sf-open],[data-tab],[data-close],#boardMore,#actMatch");
    if (!t) return;
    if (t.hasAttribute("data-close")) return closeDrill();
    if (t.id === "boardMore") { SHOW_ALL = !SHOW_ALL; return renderBoard(), window.RNIconFill && window.RNIconFill(document); }
    if (t.id === "actMatch") { TAB = "orang"; SHOW_ALL = true; setTab(); $("boardList").scrollIntoView({ behavior: "smooth", block: "center" }); return load(); }
    if (t.dataset.tab) { TAB = t.dataset.tab; SHOW_ALL = false; return setTab(); }
    if (t.dataset.sfOpen) {
      var d = $(t.dataset.sfOpen);
      if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); }
      return;
    }
    var act = t.dataset.act, p = (CTX._pairs || [])[Number(t.dataset.i)];
    if (act === "detail" && p) return showDetail(p);
    if (act === "case" && p) return createCase(p, t);
    if (act === "reunite") return setMatch(t.dataset.match, "reunited");
    if (act === "matchto") return setMatch(t.dataset.match, t.dataset.to);
    if (act === "claim") {
      call("update_claim_status", { claim: t.dataset.claim, new_status: t.dataset.to }, true).then(load).catch(function (er) { statusMsg(errMsg(er)); });
    }
  }
  function setTab() {
    document.querySelectorAll("#sfTabs [data-tab]").forEach(function (b) { b.classList.toggle("is-active", b.dataset.tab === TAB); });
    if (CTX) { renderBoard(); renderReuni(); if (window.RNIconFill) window.RNIconFill(document); }
  }

  /* ---------- Forms ---------- */
  function val(form, name) { return form[name] ? String(form[name].value || "").trim() : ""; }
  function bindForm(id, method, build, doneMsg) {
    var form = $(id);
    if (!form) return;
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      statusMsg("Menyimpan…");
      try { await call(method, build(form), true); }
      catch (err) { return statusMsg(errMsg(err)); }
      statusMsg(doneMsg); form.reset(); await load();
    });
  }
  function personPayload(form, place, time, who) {
    var p = {
      person_code: val(form, "person_code"), person_name: val(form, "person_name"), disaster_event: eventId(),
      description: val(form, "description"), clothing_description: val(form, "clothing_description"),
      subject_type: val(form, "subject_type") || "orang", age_years: val(form, "age_years"), gender: val(form, "gender"),
      reporter_name: val(form, who + "_name") || val(form, "reporter_name"),
      reporter_contact: val(form, who + "_contact") || val(form, "reporter_contact")
    };
    p[place] = val(form, place); p[time] = val(form, time);
    return p;
  }

  async function load() {
    statusMsg("Memuat Search & Found…");
    var ctx = await window.RN_FRAPPE.call(API + "dashboard", { disaster_event: eventId() });
    CTX = derive(ctx || {});
    renderAll();
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.RN_FRAPPE) return statusMsg("Frappe client tidak tersedia.");
    document.addEventListener("click", onClick);
    document.addEventListener("change", function (e) {
      var s = e.target.closest(".rn-sf-idsel");
      if (!s) return;
      call("set_identification_status", { found_report: s.dataset.found, new_status: s.value }, true).then(load).catch(function (er) { statusMsg(errMsg(er)); });
    });
    bindForm("missingForm", "create_missing_report", function (f) { return personPayload(f, "last_seen_location", "last_seen_time", "reporter"); }, "Laporan hilang disimpan.");
    bindForm("foundForm", "create_found_report", function (f) { return personPayload(f, "found_location", "found_time", "finder"); }, "Laporan ditemukan disimpan.");
    bindForm("claimForm", "create_claim", function (f) {
      return { kind: val(f, "kind"), item_description: val(f, "item_description"), location_text: val(f, "location_text"),
        claimant_name: val(f, "claimant_name"), claimant_contact: val(f, "claimant_contact"), disaster_event: eventId() };
    }, "Klaim diajukan.");
    var r = $("refreshSf");
    if (r) r.addEventListener("click", function () { load().catch(function (e) { statusMsg(errMsg(e)); }); });
    load().catch(function (e) { statusMsg(errMsg(e)); });
  });
})();
