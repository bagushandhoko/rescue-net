/* kartu-keluarga.js — putaran distribusi, kartu QR keluarga, pencatatan penerimaan (Fase 10b langkah 3).
 * API: rescue_net.api_aid_card.*  (semua butuh login pengelola shelter; QR = token buram RNK-XXXXXXXX). */
(function () {
  "use strict";
  var API = "rescue_net.api_aid_card.";
  var QKEY = "rn_aidcard_queue_v1";
  var posko = "", rounds = [], flushing = false, stream = null, timer = null, pending = null;

  function $(s) { return document.querySelector(s); }
  function esc(s) { return window.RNUI.esc(s); }
  function call(m, a) { return window.RN_FRAPPE.call(API + m, a || {}); }
  function msg(t, c) { var e = $("#kkMsg"); e.className = "kk-msg " + (c || ""); e.textContent = t; }
  function ldq() { try { return JSON.parse(localStorage.getItem(QKEY) || "[]") || []; } catch (e) { return []; } }
  function svq(q) { try { localStorage.setItem(QKEY, JSON.stringify(q)); } catch (e) { /* blocked */ } renderQ(); }
  function renderQ() { var n = ldq().length; $("#kkQ").textContent = n ? n + " penerimaan menunggu sinyal." : ""; }
  function uid() { return "aid-" + Math.random().toString(36).slice(2, 8) + "-" + Date.now().toString(36); }
  function nowStr() { return new Date().toISOString().replace("T", " ").slice(0, 19); }

  var STATE = {
    eligible: ["Boleh menerima.", "ok"], already: ["SUDAH menerima pada putaran ini", "err"], invalid: ["Kartu tidak dikenal.", "err"],
    revoked: ["Kartu sudah dicabut / diganti.", "err"], closed: ["Putaran belum dibuka / sudah ditutup.", "err"],
    wrong_posko: ["Kartu milik shelter lain.", "err"], not_present: ["Keluarga tidak lagi tercatat di shelter.", "err"],
    recorded: ["Penerimaan tercatat.", "ok"]
  };
  function show(r) {
    var s = STATE[r.state] || [r.state, "warn"];
    msg(s[0] + (r.state === "already" && r.received_at ? " (" + String(r.received_at).slice(0, 16) + ")" : "") +
      (r.household_code ? " — " + r.household_code : ""), s[1]);
  }

  async function loadShelters() {
    var rows = [];
    try { rows = await call("my_shelters"); } catch (e) { $("#kkAuth").textContent = "Perlu login sebagai pengelola shelter."; return; }
    if (!rows.length) { $("#kkAuth").textContent = "Anda tidak mengelola shelter mana pun."; return; }
    $("#kkPosko").innerHTML = rows.map(function (r) { return '<option value="' + esc(r.name) + '">' + esc(r.title || r.name) + "</option>"; }).join("");
    $("#kkMain").hidden = false;
    $("#kkPosko").addEventListener("change", loadAll);
    loadAll();
  }

  async function loadAll() { posko = $("#kkPosko").value; await Promise.all([loadRounds(), loadHouseholds()]); loadReceipts(); }

  async function loadRounds() {
    rounds = await call("list_rounds", { posko: posko });
    $("#kkRounds").innerHTML = rounds.length ? rounds.map(function (r) {
      return "<li><span><b>" + esc(r.title) + "</b> <span class='kk-muted'>" + esc(r.status === "open" ? "dibuka" : "ditutup") + " · " + r.received + "/" + r.households + " keluarga</span></span>" +
        "<button class='kk-btn alt' data-toggle='" + esc(r.round) + "' data-to='" + (r.status === "open" ? "closed" : "open") + "'>" + (r.status === "open" ? "Tutup" : "Buka lagi") + "</button></li>";
    }).join("") : "<li class='kk-muted'>Belum ada putaran.</li>";
    var open = rounds.filter(function (r) { return r.status === "open"; });
    $("#kkRoundSel").innerHTML = (open.length ? open : rounds).map(function (r) { return '<option value="' + esc(r.round) + '">' + esc(r.title) + (r.status === "open" ? "" : " (ditutup)") + "</option>"; }).join("");
  }

  async function loadHouseholds() {
    var hs = await call("list_households", { posko: posko });
    $("#kkHouseholds").innerHTML = hs.length ? hs.map(function (h) {
      return "<li><span><b>" + esc(h.household_code) + "</b> <span class='kk-muted'>" + h.members_count + " orang · " + (h.token ? "kartu aktif" : "belum ada kartu") + "</span></span>" +
        "<span><button class='kk-btn alt' data-issue='" + esc(h.household) + "'>" + (h.token ? "Cetak" : "Terbitkan") + "</button>" +
        (h.token ? " <button class='kk-btn alt' data-reissue='" + esc(h.household) + "'>Ganti (hilang)</button>" : "") + "</span></li>";
    }).join("") : "<li class='kk-muted'>Belum ada keluarga tercatat di shelter ini.</li>";
    $("#kkHouseholds")._rows = hs;
  }

  async function loadReceipts() {
    var r = $("#kkRoundSel").value;
    if (!r) { $("#kkReceipts").innerHTML = ""; $("#kkCount").textContent = ""; return; }
    var rows = await call("list_receipts", { round: r });
    $("#kkCount").textContent = "(" + rows.length + ")";
    $("#kkReceipts").innerHTML = rows.map(function (x) {
      return "<li><b>" + esc(x.household_code) + "</b><span class='kk-muted'>" + esc(String(x.received_at).slice(0, 16)) + (x.items_note ? " · " + esc(x.items_note) : "") + "</span></li>";
    }).join("") || "<li class='kk-muted'>Belum ada penerimaan.</li>";
  }

  function printCards(cards) {
    var box = $("#kkPrint");
    box.innerHTML = '<div class="kk-sheet">' + cards.map(function (c, i) {
      return '<div class="kk-tag"><div class="qr" id="kkqr' + i + '"></div><b>' + esc(c.household_code) + "</b><div>" + esc(c.members_count) + " orang · " + esc(c.token) + "</div><div style='font-size:11px'>Kartu bantuan — tunjukkan ke petugas</div></div>";
    }).join("") + "</div>";
    cards.forEach(function (c, i) {
      if (typeof QRCode === "function") new QRCode($("#kkqr" + i), { text: c.token, width: 140, height: 140, correctLevel: QRCode.CorrectLevel.M });
    });
    setTimeout(function () { window.print(); }, 400);
  }

  async function issue(household, reissue) {
    var c = await call("issue_card", { household: household, reissue: reissue ? 1 : 0 });
    var h = ($("#kkHouseholds")._rows || []).filter(function (x) { return x.household === household; })[0];
    return Object.assign({ household_code: c.household_code, members_count: c.members_count, token: c.token }, h ? {} : {});
  }

  async function flush() {
    if (flushing || navigator.onLine === false) return;
    flushing = true;
    try {
      var q = ldq(), keep = [];
      for (var i = 0; i < q.length; i++) {
        try { await call("record_receipt", q[i]); }
        catch (e) {
          var m = String((e && e.message) || e || "");
          if (!/tidak dapat|tidak ditemukan|PermissionError|DoesNotExist/i.test(m)) keep.push(q[i]);
        }
      }
      svq(keep);
    } finally { flushing = false; }
    loadRounds(); loadReceipts();
  }

  async function check(code) {
    var round = $("#kkRoundSel").value;
    if (!round) return msg("Pilih putaran dulu.", "err");
    code = String(code || "").trim();
    var m = code.toUpperCase().match(/(?:RNK-)?([A-Z0-9]{8})\s*$/);
    if (!m) return msg("Kode tidak dikenali. Format RNK-XXXXXXXX.", "err");
    pending = null; $("#kkRecord").hidden = true;
    try {
      var r = await call("check_card", { token: "RNK-" + m[1], round: round });
      show(r);
      if (r.ok) { pending = { token: "RNK-" + m[1], round: round }; $("#kkRecord").hidden = false; }
    } catch (e) { msg((e && e.message) || "Gagal memeriksa kartu.", "err"); }
  }

  async function record() {
    if (!pending) return;
    var args = { token: pending.token, round: pending.round, items_note: $("#kkItems").value.trim() || undefined, offline_id: uid(), received_at: nowStr() };
    pending = null; $("#kkRecord").hidden = true;
    var q = ldq(); q.push(args); svq(q);
    msg(navigator.onLine === false ? "Tersimpan offline; terkirim saat ada sinyal." : "Mengirim…", "warn");
    await flush();
    if (!ldq().length) msg("Penerimaan tercatat.", "ok");
    $("#kkCode").value = ""; $("#kkItems").value = "";
  }

  async function startCam() {
    if (!("BarcodeDetector" in window) || !navigator.mediaDevices) { $("#kkCamNote").textContent = "Peramban belum mendukung pemindai kamera. Ketik kodenya."; return; }
    try {
      var det = new window.BarcodeDetector({ formats: ["qr_code"] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      var v = $("#kkVideo"); v.srcObject = stream; v.hidden = false; await v.play();
      $("#kkCam").hidden = true; $("#kkCamStop").hidden = false;
      var busy = false;
      timer = setInterval(async function () {
        if (busy) return; busy = true;
        try { var c = await det.detect(v); if (c.length) { stopCam(); $("#kkCode").value = c[0].rawValue; await check(c[0].rawValue); } } catch (e) { /* frame belum siap */ }
        busy = false;
      }, 400);
    } catch (e) { $("#kkCamNote").textContent = "Kamera tidak bisa dibuka (izin ditolak?). Ketik kodenya."; }
  }
  function stopCam() {
    if (timer) { clearInterval(timer); timer = null; }
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    $("#kkVideo").hidden = true; $("#kkCamStop").hidden = true; $("#kkCam").hidden = false;
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderQ();
    $("#kkRAdd").addEventListener("click", async function () {
      var t = $("#kkRTitle").value.trim();
      if (!t) return msg("Judul putaran wajib diisi.", "err");
      try { await call("create_round", { posko: posko, title: t, item_note: $("#kkRNote").value.trim() || undefined }); $("#kkRTitle").value = ""; $("#kkRNote").value = ""; await loadRounds(); loadReceipts(); msg("Putaran dibuat.", "ok"); }
      catch (e) { msg((e && e.message) || "Gagal membuat putaran.", "err"); }
    });
    $("#kkRounds").addEventListener("click", async function (e) {
      var b = e.target.closest("button[data-toggle]"); if (!b) return;
      await call("set_round_status", { round: b.dataset.toggle, status: b.dataset.to }); loadRounds();
    });
    $("#kkHouseholds").addEventListener("click", async function (e) {
      var b = e.target.closest("button"); if (!b) return;
      try {
        if (b.dataset.reissue && !confirm("Cabut kartu lama dan terbitkan kartu baru?")) return;
        var id = b.dataset.issue || b.dataset.reissue;
        var c = await issue(id, !!b.dataset.reissue);
        await loadHouseholds(); printCards([c]);
      } catch (err) { msg((err && err.message) || "Gagal menerbitkan kartu.", "err"); }
    });
    $("#kkIssueAll").addEventListener("click", async function () {
      try {
        var hs = $("#kkHouseholds")._rows || [], cards = [];
        for (var i = 0; i < hs.length; i++) cards.push(await issue(hs[i].household, false));
        await loadHouseholds(); if (cards.length) printCards(cards);
      } catch (err) { msg((err && err.message) || "Gagal menerbitkan kartu.", "err"); }
    });
    $("#kkRoundSel").addEventListener("change", loadReceipts);
    $("#kkCam").addEventListener("click", startCam);
    $("#kkCamStop").addEventListener("click", stopCam);
    $("#kkCheck").addEventListener("click", function () { check($("#kkCode").value); });
    $("#kkCode").addEventListener("keydown", function (e) { if (e.key === "Enter") check(this.value); });
    $("#kkRecord").addEventListener("click", record);
    window.addEventListener("online", flush);
    loadShelters().then(flush);
  });
})();
