/* ============================================================
 * scan.js — chain-of-custody scanner (pages/scan.html).
 * Reads a shipment QR (lacak-logistik URL or RN-XXXXXXXX) with the
 * camera (BarcodeDetector) or typed code, and posts it to
 * rescue_net.api_custody.record_scan. Scans are queued in
 * localStorage first (offline-safe) and replayed with a stable
 * offline_id, so a retry can never double-record.
 * ============================================================ */
(function () {
  "use strict";

  var KEY = "rn_custody_queue_v1";
  var API = "rescue_net.api_custody.record_scan";
  var LABEL = { dispatch: "Kirim", transit: "Di jalan", handover: "Serah kurir", arrive: "Tiba", receive: "Terima" };
  var flushing = false, stream = null, timer = null;

  function $(s) { return document.querySelector(s); }
  function esc(s) { return window.RNUI.esc(s); }

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]") || []; } catch (e) { return []; }
  }
  function save(q) { try { localStorage.setItem(KEY, JSON.stringify(q)); } catch (e) { /* storage blocked */ } }

  function msg(text, cls) {
    var el = $("#scMsg");
    el.className = "sc-msg " + (cls || "");
    el.textContent = text;
  }

  function uid() {
    var d = localStorage.getItem("rn_custody_dev");
    if (!d) { d = Math.random().toString(36).slice(2, 8); try { localStorage.setItem("rn_custody_dev", d); } catch (e) {} }
    return d + "-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 6);
  }

  // QR content -> {flow} or {trace}; never trusts anything else in the URL.
  function parseCode(raw) {
    raw = String(raw || "").trim();
    var m = raw.match(/[?&]flow=([^&#\s]+)/);
    if (m) return { flow: decodeURIComponent(m[1]) };
    m = raw.match(/[?&](?:trace|t)=([^&#\s]+)/);
    if (m) raw = decodeURIComponent(m[1]);
    m = raw.toUpperCase().match(/^(?:RN-)?([A-Z0-9]{8})$/);
    return m ? { trace: "RN-" + m[1] } : null;
  }

  function renderQueue() {
    var q = load();
    $("#scQCount").textContent = q.length ? "(" + q.length + " menunggu)" : "(kosong)";
    $("#scQueue").innerHTML = q.map(function (it) {
      return "<li><span>" + esc(LABEL[it.scan_type] || it.scan_type) + " · " +
        esc(it.flow || it.trace) + "</span><span class='sc-muted'>" +
        esc(it.last_error || "menunggu") + "</span></li>";
    }).join("");
  }

  function gps() {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) return resolve({});
      navigator.geolocation.getCurrentPosition(
        function (p) { resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }); },
        function () { resolve({}); },
        { timeout: 4000, maximumAge: 60000 });
    });
  }

  async function flush() {
    if (flushing || !window.RN_FRAPPE || navigator.onLine === false) return;
    flushing = true;
    try {
      var q = load(), keep = [], sent = 0;
      for (var i = 0; i < q.length; i++) {
        var it = q[i];
        try {
          var r = await window.RN_FRAPPE.call(API, it.args);
          sent++;
          if (r && r.scan && r.scan.outcome === "rejected") msg("Ditolak: " + (r.reason || "transisi tidak valid"), "err");
        } catch (e) {
          var m = String((e && e.message) || e || "");
          // permanent refusals are dropped from the queue; network/auth stay queued
          if (/tidak dapat|tidak ditemukan|tidak dikenal|PermissionError|DoesNotExist/i.test(m)) {
            msg("Scan dibuang: " + m, "err");
          } else {
            it.last_error = /login|403|Session|Guest/i.test(m) ? "perlu login" : "gagal, akan dicoba lagi";
            keep.push(it);
          }
        }
      }
      save(keep);
      if (sent && !keep.length) msg("Semua scan terkirim (" + sent + ").", "ok");
    } finally { flushing = false; renderQueue(); }
  }

  async function submit(code) {
    var id = parseCode(code);
    if (!id) { msg("Kode tidak dikenali. Pakai QR kiriman atau RN-XXXXXXXX.", "err"); return; }
    var type = (document.querySelector("input[name=scType]:checked") || {}).value || "dispatch";
    var args = { scan_type: type, offline_id: uid(), scanned_at: new Date().toISOString().replace("T", " ").slice(0, 19) };
    if (id.flow) args.flow = id.flow; else args.trace = id.trace;
    if (type === "receive") {
      var qty = parseFloat($("#scQty").value);
      if (!(qty > 0)) { msg("Isi jumlah diterima lebih dari 0.", "err"); return; }
      args.received_quantity = qty;
      args.received_unit = ($("#scUnit").value || "").trim() || undefined;
    }
    Object.assign(args, await gps());
    var q = load();
    q.push({ scan_type: type, flow: id.flow, trace: id.trace, args: args });
    save(q); renderQueue();
    msg(navigator.onLine === false ? "Tersimpan offline; terkirim saat ada sinyal." : "Mengirim…", "warn");
    await flush();
    if (!load().length) msg("Tercatat: " + (LABEL[type] || type) + " · " + (id.flow || id.trace), "ok");
    $("#scCode").value = "";
  }

  async function startCamera() {
    if (!("BarcodeDetector" in window) || !navigator.mediaDevices) {
      $("#scCamNote").textContent = "Peramban ini belum mendukung pemindai kamera. Ketik kode trace di bawah.";
      return;
    }
    try {
      var det = new window.BarcodeDetector({ formats: ["qr_code"] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      var v = $("#scVideo"); v.srcObject = stream; v.hidden = false; await v.play();
      $("#scStopBtn").hidden = false; $("#scCamBtn").hidden = true;
      var busy = false;
      timer = setInterval(async function () {
        if (busy) return; busy = true;
        try {
          var codes = await det.detect(v);
          if (codes.length) { stopCamera(); await submit(codes[0].rawValue); }
        } catch (e) { /* frame not ready */ }
        busy = false;
      }, 400);
    } catch (e) {
      $("#scCamNote").textContent = "Kamera tidak bisa dibuka (izin ditolak?). Ketik kode trace di bawah.";
    }
  }

  function stopCamera() {
    if (timer) { clearInterval(timer); timer = null; }
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    $("#scVideo").hidden = true; $("#scStopBtn").hidden = true; $("#scCamBtn").hidden = false;
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderQueue();
    $("#scCamBtn").addEventListener("click", startCamera);
    $("#scStopBtn").addEventListener("click", stopCamera);
    $("#scSendBtn").addEventListener("click", function () { submit($("#scCode").value); });
    $("#scCode").addEventListener("keydown", function (e) { if (e.key === "Enter") submit(this.value); });
    $("#scFlushBtn").addEventListener("click", flush);
    $("#scTypes").addEventListener("change", function () {
      $("#scRecvRow").hidden = (document.querySelector("input[name=scType]:checked") || {}).value !== "receive";
    });
    window.addEventListener("online", flush);
    flush();
  });
})();
