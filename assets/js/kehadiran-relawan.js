/* kehadiran-relawan.js — check-in/out relawan + panel pengelola posko (Fase 10h).
 * Aksi masuk antrean localStorage lebih dulu dan diputar ulang dengan offline_id tetap,
 * jadi pengulangan tidak pernah mencatat dua kali (server idempoten). */
(function () {
  "use strict";
  var KEY = "rn_presence_queue";
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
  function uid() { return "kh-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "[]") || []; } catch (e) { return []; } }
  function save(q) { try { localStorage.setItem(KEY, JSON.stringify(q)); } catch (e) { /* penyimpanan diblokir */ } }
  function now() { return new Date().toISOString().replace("T", " ").slice(0, 19); }
  function msg(el, text, kind) { el.textContent = text; el.className = "kh-msg " + (kind || ""); }
  function errText(e) { return String((e && (e.message || e.exception)) || e || "gagal").replace(/<[^>]+>/g, "").slice(0, 200); }
  var params = new URLSearchParams(location.search);

  function renderQueue() {
    var q = load();
    $("khQueue").innerHTML = q.map(function (a) {
      return "<li><span>" + (a.kind === "in" ? "Check-in" : "Check-out") + " · " + esc(a.posko || "") + "</span><span class='kh-muted'>menunggu sinyal</span></li>";
    }).join("");
  }

  function send(a) {
    var args = { offline_id: a.id, at: a.at };
    if (a.posko) args.posko = a.posko;
    if (a.kind === "in") { if (a.token) args.token = a.token; if (a.lat != null) { args.latitude = a.lat; args.longitude = a.lng; } }
    return window.RN_FRAPPE.call("rescue_net.api_presence." + (a.kind === "in" ? "check_in" : "check_out"), args, { method: "POST" });
  }

  function flush() {
    var q = load();
    if (!q.length) return Promise.resolve();
    var a = q[0];
    return send(a).then(function () { save(load().slice(1)); renderQueue(); return flush(); }).catch(function (e) {
      // penolakan server (bukan jaringan) dibuang agar antrean tak macet
      if (navigator.onLine !== false && e && (e.status === 403 || e.status === 417 || /tidak valid|bukan relawan|tidak ada check-in/i.test(errText(e)))) {
        save(load().slice(1)); renderQueue(); msg($("khMsg"), "Dibuang oleh server: " + errText(e), "err"); return flush();
      }
    });
  }

  function act(kind) {
    var posko = $("khPosko").value.trim();
    if (!posko) { msg($("khMsg"), "Isi kode posko dulu.", "err"); return; }
    var a = { kind: kind, id: uid(), posko: posko, at: now(), token: kind === "in" ? (params.get("t") || null) : null, lat: null, lng: null };
    function enqueue() {
      var q = load(); q.push(a); save(q); renderQueue();
      msg($("khMsg"), navigator.onLine === false ? "Tersimpan offline; terkirim saat ada sinyal." : "Mengirim…", "warn");
      flush().then(function () {
        if (!load().length) msg($("khMsg"), kind === "in" ? "Check-in tercatat." : "Check-out tercatat.", "ok");
      });
    }
    if (kind === "in" && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function (p) { a.lat = p.coords.latitude; a.lng = p.coords.longitude; enqueue(); }, enqueue, { timeout: 4000, maximumAge: 60000 });
    } else enqueue();
  }

  function mgrPosko() { var p = $("khPosko").value.trim(); if (!p) msg($("khMgrMsg"), "Isi kode posko di atas.", "err"); return p; }

  function showSite() {
    var p = mgrPosko(); if (!p) return;
    window.RN_FRAPPE.call("rescue_net.api_presence.on_site", { posko: p }).then(function (r) {
      msg($("khMgrMsg"), r.count + " relawan di lokasi" + (r.walk_in_pending ? " · " + r.walk_in_pending + " walk-in perlu ditinjau" : ""), "ok");
      $("khSiteList").innerHTML = r.rows.map(function (x) {
        var tag = x.walk_in ? (x.review_status === "pending" ? " <b style='color:#b88918'>walk-in</b>" : " walk-in ✓") : "";
        var btn = x.walk_in && x.review_status === "pending" ? "<button class='kh-btn alt' data-rev='" + esc(x.name) + "'>Tinjau ✓</button>" : "";
        return "<li><span>" + esc(x.volunteer_name || x.volunteer) + " <span class='kh-muted'>" + esc(x.main_skill || "") + " · sejak " + esc(String(x.in_at).slice(11, 16)) + "</span>" + tag + "</span>" + btn + "</li>";
      }).join("");
    }).catch(function (e) { msg($("khMgrMsg"), errText(e), "err"); });
  }

  function showQr() {
    var p = mgrPosko(); if (!p) return;
    window.RN_FRAPPE.call("rescue_net.api_presence.posko_qr", { posko: p }).then(function (r) {
      var url = location.origin + r.path;
      $("khQr").innerHTML = "";
      if (typeof QRCode === "function") new QRCode($("khQr"), { text: url, width: 200, height: 200, correctLevel: QRCode.CorrectLevel.M });
      msg($("khMgrMsg"), "QR berlaku " + r.berlaku + ". Cetak dan tempel di posko.", "ok");
    }).catch(function (e) { msg($("khMgrMsg"), errText(e), "err"); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (params.get("posko")) $("khPosko").value = params.get("posko");
    $("khIn").addEventListener("click", function () { act("in"); });
    $("khOut").addEventListener("click", function () { act("out"); });
    $("khSite").addEventListener("click", showSite);
    $("khShowQr").addEventListener("click", showQr);
    $("khSiteList").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-rev]"); if (!b) return;
      window.RN_FRAPPE.call("rescue_net.api_presence.review_walk_in", { presence: b.dataset.rev }, { method: "POST" }).then(showSite)
        .catch(function (er) { msg($("khMgrMsg"), errText(er), "err"); });
    });
    window.addEventListener("online", flush);
    renderQueue(); flush();
  });
})();
