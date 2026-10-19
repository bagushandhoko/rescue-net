/* ============================================================
 * rn-offline-outbox.js — field forms keep working without signal
 * (owner 2026-10-19). Load right after rn-frappe-client.js.
 *
 *  - SAVE: a POST to one of the field-form methods below, made while
 *    offline (or failing on the network), is kept on the phone with a
 *    client id and sent later through rescue_net.api_offline.replay,
 *    which records each id exactly once (no double entries).
 *  - READ: the last answer of a few PUBLIC boards is kept on the phone so
 *    the page still shows "data terakhir" offline. Never medical data,
 *    contacts or anything login-only. (The service worker itself never
 *    caches /api/method/ answers — that rule stays.)
 *  - A small badge shows how many items wait to be sent; tap it to see
 *    them, retry, or remove one that the server refused.
 * Forms with their own offline queue (Laporan Masyarakat, Scan QR, Kartu
 * Keluarga, Kehadiran Relawan) are left alone.
 * ============================================================ */
(function () {
  "use strict";
  if (!window.RN_FRAPPE || !window.RN_FRAPPE.call || window.RNOutbox) return;

  var BOX_KEY = "rn_outbox_v1";
  var CACHE_KEY = "rn_board_cache_v1:";
  var DEV_KEY = "rn_device_id_v1";
  var SAVE = {
    "rescue_net.api_logistics.create_need": "Kebutuhan posko",
    "rescue_net.api_logistics.create_stock_observation": "Catat stok",
    "rescue_net.api_logistics.receive_aid_offer_and_update_stock": "Terima kiriman",
    "rescue_net.api_logistics.confirm_reported_need": "Konfirmasi kebutuhan",
    "rescue_net.api_control_centre.set_posko_beneficiary": "Jiwa dilayani",
    "rescue_net.api_medical.create_case": "Pasien baru",
    "rescue_net.api_medical.update_case_status": "Status pasien",
    "rescue_net.api_medical.record_supply_use": "Pemakaian obat/alat",
    "rescue_net.api_shelter.create_occupancy": "Okupansi shelter",
    "rescue_net.api_shelter.create_need": "Kebutuhan shelter",
    "rescue_net.api_kitchen.create_production": "Produksi dapur",
    "rescue_net.api_resource_tools.create_work_object": "Kondisi lapangan",
    "rescue_net.api_recovery.create_update": "Progres recovery"
  };
  var READ = {
    "rescue_net.api_control_centre.active_disasters_board": 1,
    "rescue_net.api_control_centre.event_poskos": 1,
    "rescue_net.api_control_centre.logistik_board": 1,
    "rescue_net.api_control_centre.logistik_open_needs": 1,
    "rescue_net.api_control_centre.ecosystem_board": 1,
    "rescue_net.api_shelter.shelter_board": 1,
    "rescue_net.api_kitchen.kitchen_board": 1,
    "rescue_net.api_resource_tools.tools_board": 1,
    "rescue_net.api_resource_tools.work_objects_board": 1,
    "rescue_net.api_recovery.recovery_board": 1,
    "rescue_net.api_public_needs.board": 1
  };

  var original = window.RN_FRAPPE.call.bind(window.RN_FRAPPE);
  var flushing = false;

  function load() { try { return JSON.parse(localStorage.getItem(BOX_KEY) || "[]") || []; } catch (e) { return []; } }
  function store(q) { try { localStorage.setItem(BOX_KEY, JSON.stringify(q)); } catch (e) { /* storage full / blocked */ } render(); }
  function device() {
    var d = null;
    try { d = localStorage.getItem(DEV_KEY); } catch (e) {}
    if (!d) { d = "dev-" + Math.random().toString(36).slice(2, 10); try { localStorage.setItem(DEV_KEY, d); } catch (e) {} }
    return d;
  }
  function newId() { return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10); }
  // a network problem, not an answer from the server
  function isNetworkError(err) {
    return !!err && (!err.status || err.transient || err.status === 502 || err.status === 503 || err.status === 504);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function when(t) { var d = new Date(t); return isNaN(d) ? "" : d.toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }

  function enqueue(method, args) {
    var q = load();
    var item = { id: newId(), method: method, label: SAVE[method], args: args || {}, created: Date.now(), status: "pending", error: "" };
    q.push(item);
    store(q);
    toast("Tidak ada sinyal — " + item.label + " disimpan di HP dan akan dikirim otomatis saat ada sinyal.");
    return { offline_queued: true, outbox_id: item.id, message: "Tersimpan di HP, menunggu sinyal." };
  }

  function cacheKey(method, args) { return CACHE_KEY + method + ":" + JSON.stringify(args || {}); }

  window.RN_FRAPPE.call = async function (method, args, options) {
    var verb = String((options && options.method) || "GET").toUpperCase();
    if (SAVE[method] && verb === "POST") {
      if (!navigator.onLine) return enqueue(method, args);
      try { return await original(method, args, options); }
      catch (err) { if (isNetworkError(err)) return enqueue(method, args); throw err; }
    }
    if (READ[method] && verb === "GET") {
      try {
        var res = await original(method, args, options);
        try { localStorage.setItem(cacheKey(method, args), JSON.stringify({ at: Date.now(), data: res })); } catch (e) { /* full */ }
        return res;
      } catch (err) {
        if (!isNetworkError(err)) throw err;
        var hit = null;
        try { hit = JSON.parse(localStorage.getItem(cacheKey(method, args)) || "null"); } catch (e) {}
        if (!hit) throw err;
        banner("Offline — menampilkan data terakhir (" + when(hit.at) + "). Data akan diperbarui saat ada sinyal.");
        return hit.data;
      }
    }
    return original(method, args, options);
  };

  async function flush() {
    if (flushing || !navigator.onLine) return;
    var q = load().filter(function (x) { return x.status === "pending"; });
    if (!q.length) return;
    flushing = true;
    try {
      for (var i = 0; i < q.length; i++) {
        var it = q[i];
        try {
          await original("rescue_net.api_offline.replay", {
            method: it.method, args: JSON.stringify(it.args), client_event_id: it.id,
            device_id: device(), created_local_at: new Date(it.created).toISOString()
          }, { method: "POST" });
          store(load().filter(function (x) { return x.id !== it.id; }));
        } catch (err) {
          if (isNetworkError(err)) break;                         // still no real signal: try later
          var all = load(), msg = (err && err.message) || String(err);
          if (err.status === 401 || (err.status === 403 && /login/i.test(msg))) { banner("Login dulu agar data offline bisa dikirim."); break; }
          all.forEach(function (x) { if (x.id === it.id) { x.status = "failed"; x.error = msg; } });
          store(all);
        }
      }
      var left = load().filter(function (x) { return x.status === "pending"; }).length;
      if (!left) toast("Semua data offline sudah terkirim.");
    } finally { flushing = false; }
  }

  // ---- UI: badge + list, toast, banner ----------------------------------
  var CSS = ".rn-ob-badge{position:fixed;right:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px));z-index:9998;border:0;border-radius:999px;padding:10px 14px;background:#2d211b;color:#fff;font:600 13px/1.2 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.25);cursor:pointer}" +
    ".rn-ob-badge.has-failed{background:#a92f2f}" +
    ".rn-ob-panel{position:fixed;right:14px;bottom:calc(64px + env(safe-area-inset-bottom,0px));z-index:9999;width:min(380px,calc(100vw - 28px));max-height:60vh;overflow:auto;background:#fff;color:#2d211b;border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,.25);padding:12px;font:13px/1.4 system-ui,sans-serif}" +
    ".rn-ob-panel h4{margin:0 0 8px;font-size:14px}.rn-ob-row{border-top:1px solid #eee;padding:8px 0;display:grid;gap:4px}" +
    ".rn-ob-row small{color:#7c6458}.rn-ob-row .err{color:#a92f2f}.rn-ob-actions{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}" +
    ".rn-ob-actions button,.rn-ob-row button{border:1px solid #ddd;background:#fff;border-radius:8px;padding:4px 10px;font:inherit;cursor:pointer}" +
    ".rn-ob-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(70px + env(safe-area-inset-bottom,0px));z-index:10000;max-width:min(520px,calc(100vw - 28px));background:#2d211b;color:#fff;border-radius:12px;padding:10px 14px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.25)}" +
    ".rn-ob-banner{position:sticky;top:env(safe-area-inset-top,0px);z-index:9997;background:#fff1da;color:#7a4a0d;border-bottom:1px solid #f0c98a;padding:8px 14px;font:13px/1.4 system-ui,sans-serif}";

  function ensureCss() {
    if (document.getElementById("rn-ob-css")) return;
    var st = document.createElement("style"); st.id = "rn-ob-css"; st.textContent = CSS; document.head.appendChild(st);
  }

  function render() {
    if (!document.body) return;
    ensureCss();
    var q = load(), badge = document.getElementById("rnObBadge");
    if (!q.length) { if (badge) badge.remove(); var p0 = document.getElementById("rnObPanel"); if (p0) p0.remove(); return; }
    var failed = q.filter(function (x) { return x.status === "failed"; }).length;
    if (!badge) {
      badge = document.createElement("button"); badge.type = "button"; badge.id = "rnObBadge"; badge.className = "rn-ob-badge";
      badge.addEventListener("click", togglePanel); document.body.appendChild(badge);
    }
    badge.classList.toggle("has-failed", failed > 0);
    badge.textContent = (q.length - failed ? (q.length - failed) + " data menunggu sinyal" : "") +
      (failed ? (q.length - failed ? " · " : "") + failed + " gagal terkirim" : "");
    if (document.getElementById("rnObPanel")) fillPanel();
  }

  function togglePanel() {
    var p = document.getElementById("rnObPanel");
    if (p) { p.remove(); return; }
    p = document.createElement("div"); p.id = "rnObPanel"; p.className = "rn-ob-panel"; p.setAttribute("role", "dialog");
    document.body.appendChild(p); fillPanel();
  }

  function fillPanel() {
    var p = document.getElementById("rnObPanel"); if (!p) return;
    var q = load();
    p.innerHTML = "<h4>Data tersimpan di HP</h4>" + q.map(function (x) {
      return '<div class="rn-ob-row"><b>' + esc(x.label) + "</b><small>" + esc(when(x.created)) +
        (x.status === "failed" ? ' · <span class="err">ditolak server: ' + esc(x.error) + "</span>" : " · menunggu sinyal") + "</small>" +
        (x.status === "failed" ? '<div><button type="button" data-ob-retry="' + esc(x.id) + '">Coba lagi</button> <button type="button" data-ob-drop="' + esc(x.id) + '">Hapus</button></div>' : "") +
        "</div>";
    }).join("") + '<div class="rn-ob-actions"><button type="button" id="rnObSend">Kirim sekarang</button><button type="button" id="rnObClose">Tutup</button></div>';
    p.querySelector("#rnObSend").onclick = function () { flush(); };
    p.querySelector("#rnObClose").onclick = function () { p.remove(); };
    p.querySelectorAll("[data-ob-drop]").forEach(function (b) {
      b.onclick = function () { store(load().filter(function (x) { return x.id !== b.getAttribute("data-ob-drop"); })); };
    });
    p.querySelectorAll("[data-ob-retry]").forEach(function (b) {
      b.onclick = function () {
        var all = load(); all.forEach(function (x) { if (x.id === b.getAttribute("data-ob-retry")) { x.status = "pending"; x.error = ""; } });
        store(all); flush();
      };
    });
  }

  var toastTimer = null;
  function toast(text) {
    if (!document.body) return;
    ensureCss();
    var t = document.getElementById("rnObToast");
    if (!t) { t = document.createElement("div"); t.id = "rnObToast"; t.className = "rn-ob-toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = text;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.remove(); }, 6000);
  }

  function banner(text) {
    if (!document.body) return;
    ensureCss();
    var b = document.getElementById("rnObBanner");
    if (!b) { b = document.createElement("div"); b.id = "rnObBanner"; b.className = "rn-ob-banner"; b.setAttribute("role", "status"); document.body.prepend(b); }
    b.textContent = text;
  }

  window.addEventListener("online", function () { var b = document.getElementById("rnObBanner"); if (b) b.remove(); flush(); });
  window.addEventListener("offline", function () { banner("Tidak ada sinyal. Isian formulir lapangan tetap bisa disimpan dan akan dikirim otomatis."); });
  document.addEventListener("DOMContentLoaded", function () { render(); flush(); });
  setInterval(flush, 60000);

  window.RNOutbox = { flush: flush, items: load, saveMethods: SAVE };
})();
