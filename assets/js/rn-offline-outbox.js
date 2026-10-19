/* ============================================================
 * rn-offline-outbox.js — Rescue-Net works offline (owner 2026-10-19).
 * Load right after rn-frappe-client.js.
 *
 * 1. DATA PACK: after login (and every 30 min while online) the app
 *    downloads the current data of the user's own posko(s) and
 *    organisation(s) (rescue_net.api_offline.pack — same read methods
 *    and permissions as the pages) into IndexedDB on the phone.
 * 2. OFFLINE: the pages keep their normal screens — every read the page
 *    makes is answered from the pack / last answer when there is no
 *    signal, with a banner saying how old the data is.
 * 3. SAVE: field forms saved offline wait in an outbox on the phone.
 * 4. SIGNAL BACK: a notification, then the outbox is sent once each
 *    (rescue_net.api_offline.replay — never twice), the pack is
 *    downloaded again and a SUMMARY shows what was sent, what was
 *    refused (bentrok) and what changed on the server meanwhile,
 *    compared with the data the phone had while offline.
 * Logging out (or another user logging in) wipes the pack.
 * ============================================================ */
(function () {
  "use strict";
  if (!window.RN_FRAPPE || !window.RN_FRAPPE.call || window.RNOutbox) return;

  var BOX_KEY = "rn_outbox_v1";
  var META_KEY = "rn_offline_meta_v1";
  var SUMMARY_KEY = "rn_sync_summary_v1";
  var DEV_KEY = "rn_device_id_v1";
  var PACK_MAX_AGE = 30 * 60 * 1000;
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
  var LABEL = {
    "rescue_net.api_control_centre.posko_detail": "Detail posko",
    "rescue_net.api_control_centre.logistik_board": "Logistik posko",
    "rescue_net.api_control_centre.logistik_open_needs": "Kebutuhan terbuka",
    "rescue_net.api_control_centre.event_poskos": "Daftar posko",
    "rescue_net.api_control_centre.ecosystem_board": "Ekosistem penanganan",
    "rescue_net.api_control_centre.posko_distribusi_board": "Distribusi posko",
    "rescue_net.api_logistics.dashboard": "Stok & kebutuhan posko",
    "rescue_net.api_medical.dashboard": "Data medis posko",
    "rescue_net.api_shelter.dashboard": "Data shelter",
    "rescue_net.api_shelter.shelter_board": "Papan shelter",
    "rescue_net.api_kitchen.dashboard": "Data dapur",
    "rescue_net.api_kitchen.kitchen_board": "Papan dapur",
    "rescue_net.api_resource_tools.tools_board": "Alat kerja",
    "rescue_net.api_resource_tools.work_objects_board": "Kondisi lapangan",
    "rescue_net.api_recovery.recovery_board": "Recovery"
  };
  // reads never kept on the phone (writes / actions / per-session gates)
  var NO_CACHE = /\.(create|update|record|set_|confirm|receive|claim|assign|book|cancel|reject|fulfill|issue|delete|save|check_in|check_out|review|replay|pack|login|logout|upload|send|posko_broadcast)/;

  var original = window.RN_FRAPPE.call.bind(window.RN_FRAPPE);
  var flushing = false, packing = false;

  // ---- small helpers ----------------------------------------------------
  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* full / blocked */ } }
  function device() { var d = lsGet(DEV_KEY, null); if (!d) { d = "dev-" + Math.random().toString(36).slice(2, 10); lsSet(DEV_KEY, d); } return d; }
  function newId() { return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10); }
  function isNetworkError(err) { return !!err && (!err.status || err.transient || err.status === 502 || err.status === 503 || err.status === 504); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function when(t) { var d = new Date(t); return isNaN(d) ? "" : d.toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  function norm(v) { return String(v == null ? "" : v).replace(/^(disaster_events|posko_nodes):/, "").trim(); }
  // fuzzy key: method + posko + event, so a page asking with slightly different
  // arguments (event prefix, extra filters) still finds the downloaded answer
  function keyOf(method, args) {
    args = args || {};
    var posko = args.posko || args.id || args.target_posko || args.source_posko || "";
    var ev = args.disaster_event || args.event || args.disaster_event_id || "";
    var extra = args.dimension ? "|" + args.dimension : "";
    return method + "|" + norm(posko) + "|" + norm(ev) + extra;
  }

  // ---- IndexedDB store (pack + last answers) -----------------------------
  var dbp = null;
  function db() {
    if (dbp) return dbp;
    dbp = new Promise(function (resolve, reject) {
      if (!window.indexedDB) { reject(new Error("no indexedDB")); return; }
      var r = indexedDB.open("rn-offline", 1);
      r.onupgradeneeded = function () { r.result.createObjectStore("reads"); };
      r.onsuccess = function () { resolve(r.result); };
      r.onerror = function () { reject(r.error); };
    });
    return dbp;
  }
  function tx(mode, fn) {
    return db().then(function (d) {
      return new Promise(function (resolve, reject) {
        var t = d.transaction("reads", mode), st = t.objectStore("reads"), out = fn(st);
        t.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : undefined); };
        t.onerror = function () { reject(t.error); };
      });
    });
  }
  function put(key, value) { return tx("readwrite", function (st) { st.put(value, key); }).catch(function () {}); }
  function get(key) { return tx("readonly", function (st) { return st.get(key); }).catch(function () { return undefined; }); }
  function allReads() {
    return db().then(function (d) {
      return new Promise(function (resolve) {
        var out = {}, t = d.transaction("reads", "readonly"), c = t.objectStore("reads").openCursor();
        c.onsuccess = function () { var cur = c.result; if (cur) { out[cur.key] = cur.value; cur.continue(); } else resolve(out); };
        c.onerror = function () { resolve(out); };
      });
    }).catch(function () { return {}; });
  }
  function wipe() { lsSet(META_KEY, {}); return tx("readwrite", function (st) { st.clear(); }).catch(function () {}); }

  async function findRead(method, args) {
    var k = keyOf(method, args), hit = await get(k);
    if (hit) return hit;
    var parts = k.split("|"), all = await allReads(), best = null;
    Object.keys(all).forEach(function (key) {           // same method + same posko, or same event, newest first
      var p = key.split("|");
      if (p[0] !== method) return;
      var ok = (parts[1] && p[1] === parts[1]) || (!parts[1] && parts[2] && p[2] === parts[2]) || (!parts[1] && !parts[2]);
      if (ok && (!best || all[key].at > best.at)) best = all[key];
    });
    return best;
  }

  // ---- outbox -----------------------------------------------------------
  function load() { return lsGet(BOX_KEY, []) || []; }
  function store(q) { lsSet(BOX_KEY, q); render(); }
  function enqueue(method, args) {
    var q = load(), item = { id: newId(), method: method, label: SAVE[method], args: args || {}, created: Date.now(), status: "pending", error: "" };
    q.push(item); store(q);
    toast("Tidak ada sinyal — " + item.label + " disimpan di HP dan dikirim saat ada sinyal.");
    return { offline_queued: true, outbox_id: item.id, message: "Tersimpan di HP, menunggu sinyal." };
  }

  // ---- the wrapper every page goes through -----------------------------
  window.RN_FRAPPE.call = async function (method, args, options) {
    var verb = String((options && options.method) || "GET").toUpperCase();
    if (SAVE[method] && verb === "POST") {
      if (!navigator.onLine) return enqueue(method, args);
      try { return await original(method, args, options); }
      catch (err) { if (isNetworkError(err)) return enqueue(method, args); throw err; }
    }
    if (verb === "GET" && !NO_CACHE.test(method)) {
      var meta = lsGet(META_KEY, {}) || {};
      if (!navigator.onLine) {
        var off = await findRead(method, args);
        if (off) { banner("Offline — data posko Anda dari " + when(off.at) + ". Isian baru disimpan di HP."); return off.data; }
      }
      try {
        var res = await original(method, args, options);
        if (meta.user && meta.user !== "Guest") put(keyOf(method, args), { at: Date.now(), data: res, method: method });
        if (method === "rescue_net.api_auth.session_info") checkUser(res);
        return res;
      } catch (err) {
        if (!isNetworkError(err)) throw err;
        var hit = await findRead(method, args);
        if (!hit) throw err;
        banner("Offline — data posko Anda dari " + when(hit.at) + ". Isian baru disimpan di HP.");
        return hit.data;
      }
    }
    return original(method, args, options);
  };

  // ---- data pack ----------------------------------------------------------
  function checkUser(s) {
    var meta = lsGet(META_KEY, {}) || {}, user = s && s.user;
    if (!user || user === "Guest") { if (meta.user) { wipe(); } return; }
    if (meta.user && meta.user !== user) wipe();
    if (!meta.user || meta.user !== user || !meta.at || Date.now() - meta.at > PACK_MAX_AGE) downloadPack();
  }

  async function downloadPack(force) {
    if (packing || !navigator.onLine) return null;
    packing = true;
    try {
      var p = await original("rescue_net.api_offline.pack", {});
      for (var i = 0; i < p.entries.length; i++) {
        var e = p.entries[i];
        await put(keyOf(e.method, e.args), { at: Date.now(), data: e.data, method: e.method, args: e.args });
      }
      lsSet(META_KEY, { user: p.user, at: Date.now(), poskos: p.poskos, events: p.events, count: p.entries.length });
      render();
      return p;
    } catch (err) { return null; }
    finally { packing = false; }
  }

  // ---- compare old (offline) data with the fresh server data ----------------
  function rowKey(r) { return r && (r.name || r.id || r.code || r.legacy_id); }
  function rowLabel(r) { return r.title || r.item_name || r.item || r.patient_code || r.resource_name || r.meal_name || r.shelter_name || r.name || r.id; }
  var SKIP_FIELDS = /^(modified|generated_at|updated_at|observed_at|source_updated_at|last_|percent|age|ago|minutes|hours|sort|rank|href)/;
  function rowsOf(data, path, out) {
    out = out || [];
    if (Array.isArray(data)) {
      if (data.length && typeof data[0] === "object" && data[0] && rowKey(data[0])) out.push({ path: path, rows: data });
      else data.forEach(function (x, i) { if (x && typeof x === "object") rowsOf(x, path + "[" + i + "]", out); });
    } else if (data && typeof data === "object") {
      Object.keys(data).forEach(function (k) { rowsOf(data[k], path ? path + "." + k : k, out); });
    }
    return out;
  }
  function diffData(oldData, newData) {
    var changes = [], oldLists = {};
    rowsOf(oldData, "").forEach(function (l) { oldLists[l.path] = l.rows; });
    rowsOf(newData, "").forEach(function (l) {
      var before = {}, seen = {};
      (oldLists[l.path] || []).forEach(function (r) { before[rowKey(r)] = r; });
      l.rows.forEach(function (r) {
        var k = rowKey(r); seen[k] = 1;
        var o = before[k];
        if (!o) { if (oldLists[l.path]) changes.push({ kind: "baru", id: k, label: rowLabel(r) }); return; }
        var fields = Object.keys(r).filter(function (f) {
          return !SKIP_FIELDS.test(f) && typeof r[f] !== "object" && String(r[f]) !== String(o[f]);
        });
        if (fields.length) changes.push({ kind: "berubah", id: k, label: rowLabel(r),
          detail: fields.slice(0, 3).map(function (f) { return f + ": " + (o[f] == null ? "-" : o[f]) + " → " + (r[f] == null ? "-" : r[f]); }) });
      });
      (oldLists[l.path] || []).forEach(function (r) { if (!seen[rowKey(r)]) changes.push({ kind: "hilang", id: rowKey(r), label: rowLabel(r) }); });
    });
    return changes;
  }
  function argIds(args) {
    var ids = [];
    Object.keys(args || {}).forEach(function (k) { if (/^(medical_case|need|aid_offer|project_id|resource_profile|flow|work_object|posko)$/.test(k) && args[k]) ids.push(String(args[k])); });
    return ids;
  }

  // ---- sync -----------------------------------------------------------------
  async function flush(opts) {
    opts = opts || {};
    if (flushing || !navigator.onLine) return;
    var pending = load().filter(function (x) { return x.status === "pending"; });
    if (!pending.length && !opts.refresh) return;
    flushing = true;
    var sent = [], refused = [], dup = 0, stopped = false;
    try {
      notify("Sinyal kembali", pending.length ? "Menyinkronkan " + pending.length + " data dari HP…" : "Memperbarui data posko…");
      var before = await allReads();
      for (var i = 0; i < pending.length; i++) {
        var it = pending[i];
        try {
          var r = await original("rescue_net.api_offline.replay", {
            method: it.method, args: JSON.stringify(it.args), client_event_id: it.id,
            device_id: device(), created_local_at: new Date(it.created).toISOString()
          }, { method: "POST" });
          if (r && r.duplicate) dup++;
          sent.push(it);
          store(load().filter(function (x) { return x.id !== it.id; }));
        } catch (err) {
          if (isNetworkError(err)) { stopped = true; break; }
          var msg = (err && err.message) || String(err);
          if (err.status === 401 || (err.status === 403 && /login/i.test(msg))) { banner("Login dulu agar data offline bisa dikirim."); stopped = true; break; }
          refused.push({ item: it, error: msg });
          var all = load(); all.forEach(function (x) { if (x.id === it.id) { x.status = "failed"; x.error = msg; } }); store(all);
        }
      }
      if (stopped) return;
      var fresh = await downloadPack(true);
      var changes = [];
      if (fresh) {
        fresh.entries.forEach(function (e) {
          var k = keyOf(e.method, e.args), old = before[k];
          if (!old) return;
          diffData(old.data, e.data).forEach(function (c) {
            c.where = (LABEL[e.method] || e.method.split(".").pop()) + (e.args.posko ? " · " + e.args.posko : "");
            changes.push(c);
          });
        });
      }
      // a refused offline item, or one whose record also changed on the server = bentrok
      var touched = {};
      sent.concat(refused.map(function (x) { return x.item; })).forEach(function (it) { argIds(it.args).forEach(function (id) { touched[id] = it.label; }); });
      var clashes = changes.filter(function (c) { return c.kind === "berubah" && touched[c.id]; });
      var summary = { at: Date.now(), sent: sent.map(function (x) { return x.label; }), duplicate: dup,
                      refused: refused.map(function (x) { return { label: x.item.label, error: x.error }; }),
                      clashes: clashes, changes: changes.slice(0, 200), total_changes: changes.length };
      lsSet(SUMMARY_KEY, summary);
      if (sent.length || refused.length || changes.length) {
        notify("Sinkron selesai", sent.length + " terkirim · " + refused.length + " ditolak · " + changes.length + " perubahan di server");
        showSummary(summary);
      }
    } finally { flushing = false; render(); }
  }

  // ---- UI ---------------------------------------------------------------------
  var CSS = ".rn-ob-badge{position:fixed;right:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px));z-index:9998;border:0;border-radius:999px;padding:10px 14px;background:#2d211b;color:#fff;font:600 13px/1.2 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.25);cursor:pointer}" +
    ".rn-ob-badge.ok{background:#1f7a50}.rn-ob-badge.has-failed{background:#a92f2f}" +
    ".rn-ob-panel{position:fixed;right:14px;bottom:calc(64px + env(safe-area-inset-bottom,0px));z-index:9999;width:min(420px,calc(100vw - 28px));max-height:70vh;overflow:auto;background:#fff;color:#2d211b;border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,.25);padding:14px;font:13px/1.45 system-ui,sans-serif}" +
    ".rn-ob-panel h4{margin:0 0 6px;font-size:15px}.rn-ob-panel h5{margin:12px 0 4px;font-size:13px}.rn-ob-row{border-top:1px solid #eee;padding:7px 0;display:grid;gap:3px}" +
    ".rn-ob-row small,.rn-ob-muted{color:#7c6458}.rn-ob-err{color:#a92f2f}.rn-ob-ok{color:#1f7a50}.rn-ob-actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}" +
    ".rn-ob-actions button,.rn-ob-row button{border:1px solid #ddd;background:#fff;border-radius:8px;padding:5px 10px;font:inherit;cursor:pointer}" +
    ".rn-ob-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(70px + env(safe-area-inset-bottom,0px));z-index:10000;max-width:min(520px,calc(100vw - 28px));background:#2d211b;color:#fff;border-radius:12px;padding:10px 14px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.25)}" +
    ".rn-ob-banner{position:sticky;top:env(safe-area-inset-top,0px);z-index:9997;background:#fff1da;color:#7a4a0d;border-bottom:1px solid #f0c98a;padding:8px 14px;font:13px/1.4 system-ui,sans-serif;display:flex;gap:10px;align-items:center;flex-wrap:wrap}" +
    ".rn-ob-banner button{border:1px solid #d9a35a;background:#fff;border-radius:8px;padding:4px 10px;font:inherit;cursor:pointer}";
  function ensureCss() { if (document.getElementById("rn-ob-css")) return; var st = document.createElement("style"); st.id = "rn-ob-css"; st.textContent = CSS; document.head.appendChild(st); }

  function render() {
    if (!document.body) return;
    ensureCss();
    var q = load(), meta = lsGet(META_KEY, {}) || {}, badge = document.getElementById("rnObBadge");
    var failed = q.filter(function (x) { return x.status === "failed"; }).length, waiting = q.length - failed;
    if (!q.length && !meta.user) { if (badge) badge.remove(); return; }
    if (!badge) { badge = document.createElement("button"); badge.type = "button"; badge.id = "rnObBadge"; badge.className = "rn-ob-badge"; badge.addEventListener("click", togglePanel); document.body.appendChild(badge); }
    badge.classList.toggle("has-failed", failed > 0);
    badge.classList.toggle("ok", !q.length);
    badge.textContent = q.length
      ? (waiting ? waiting + " data menunggu sinyal" : "") + (failed ? (waiting ? " · " : "") + failed + " ditolak" : "")
      : "Offline siap · " + (meta.poskos || []).length + " posko";
    if (document.getElementById("rnObPanel") && !document.getElementById("rnObPanel").dataset.summary) fillPanel();
  }

  function togglePanel() {
    var p = document.getElementById("rnObPanel");
    if (p) { p.remove(); return; }
    p = document.createElement("div"); p.id = "rnObPanel"; p.className = "rn-ob-panel"; p.setAttribute("role", "dialog");
    document.body.appendChild(p); fillPanel();
  }

  function fillPanel() {
    var p = document.getElementById("rnObPanel"); if (!p) return;
    delete p.dataset.summary;
    var q = load(), meta = lsGet(META_KEY, {}) || {}, last = lsGet(SUMMARY_KEY, null);
    p.innerHTML = "<h4>Mode offline</h4>" +
      '<div class="rn-ob-muted">' + (meta.user
        ? "Data " + (meta.poskos || []).length + " posko Anda tersimpan di HP (diunduh " + esc(when(meta.at)) + ")." +
          ((meta.poskos || []).length ? "<br>" + (meta.poskos || []).slice(0, 6).map(function (x) { return esc(x.title || x.name); }).join(", ") + ((meta.poskos || []).length > 6 ? ", …" : "") : "")
        : "Login dulu agar data posko Anda diunduh ke HP.") + "</div>" +
      "<h5>Menunggu dikirim (" + q.length + ")</h5>" +
      (q.length ? q.map(function (x) {
        return '<div class="rn-ob-row"><b>' + esc(x.label) + "</b><small>" + esc(when(x.created)) +
          (x.status === "failed" ? ' · <span class="rn-ob-err">ditolak server: ' + esc(x.error) + "</span>" : " · menunggu sinyal") + "</small>" +
          (x.status === "failed" ? '<div><button type="button" data-ob-retry="' + esc(x.id) + '">Coba lagi</button> <button type="button" data-ob-drop="' + esc(x.id) + '">Hapus</button></div>' : "") + "</div>";
      }).join("") : '<div class="rn-ob-muted">Tidak ada.</div>') +
      '<div class="rn-ob-actions"><button type="button" id="rnObSend">Sinkronkan sekarang</button>' +
      (last ? '<button type="button" id="rnObLast">Ringkasan sinkron terakhir</button>' : "") +
      '<button type="button" id="rnObClose">Tutup</button></div>';
    p.querySelector("#rnObSend").onclick = function () { flush({ refresh: true }); };
    p.querySelector("#rnObClose").onclick = function () { p.remove(); };
    if (last) p.querySelector("#rnObLast").onclick = function () { showSummary(last); };
    p.querySelectorAll("[data-ob-drop]").forEach(function (b) { b.onclick = function () { store(load().filter(function (x) { return x.id !== b.getAttribute("data-ob-drop"); })); }; });
    p.querySelectorAll("[data-ob-retry]").forEach(function (b) {
      b.onclick = function () { var all = load(); all.forEach(function (x) { if (x.id === b.getAttribute("data-ob-retry")) { x.status = "pending"; x.error = ""; } }); store(all); flush(); };
    });
  }

  function showSummary(s) {
    if (!document.body) return;
    ensureCss();
    var p = document.getElementById("rnObPanel");
    if (!p) { p = document.createElement("div"); p.id = "rnObPanel"; p.className = "rn-ob-panel"; p.setAttribute("role", "dialog"); document.body.appendChild(p); }
    p.dataset.summary = "1";
    var counts = {};
    s.sent.forEach(function (l) { counts[l] = (counts[l] || 0) + 1; });
    var groups = {};
    s.changes.forEach(function (c) { (groups[c.where] = groups[c.where] || []).push(c); });
    p.innerHTML = "<h4>Ringkasan sinkron</h4><div class='rn-ob-muted'>" + esc(when(s.at)) + "</div>" +
      "<h5 class='rn-ob-ok'>Terkirim dari HP (" + s.sent.length + ")</h5>" +
      (s.sent.length ? Object.keys(counts).map(function (l) { return "<div>✓ " + esc(l) + (counts[l] > 1 ? " ×" + counts[l] : "") + "</div>"; }).join("") : "<div class='rn-ob-muted'>Tidak ada.</div>") +
      (s.duplicate ? "<div class='rn-ob-muted'>" + s.duplicate + " sudah pernah terkirim sebelumnya (tidak dicatat dua kali).</div>" : "") +
      "<h5 class='rn-ob-err'>Bentrok / ditolak (" + (s.refused.length + s.clashes.length) + ")</h5>" +
      (s.refused.length || s.clashes.length
        ? s.refused.map(function (r) { return "<div class='rn-ob-row'><b>" + esc(r.label) + "</b><small class='rn-ob-err'>Ditolak server: " + esc(r.error) + "</small><small>Data di server sudah berbeda dari data offline Anda. Periksa lalu isi ulang bila perlu.</small></div>"; }).join("") +
          s.clashes.map(function (c) { return "<div class='rn-ob-row'><b>" + esc(c.label) + "</b><small>Anda mengubahnya saat offline, dan data ini juga berubah di server:</small><small>" + esc((c.detail || []).join(" · ")) + "</small></div>"; }).join("")
        : "<div class='rn-ob-muted'>Tidak ada.</div>") +
      "<h5>Berubah di server sejak data offline Anda (" + s.total_changes + ")</h5>" +
      (s.changes.length ? Object.keys(groups).map(function (g) {
        return "<div class='rn-ob-row'><b>" + esc(g) + "</b>" + groups[g].slice(0, 8).map(function (c) {
          return "<small>" + (c.kind === "baru" ? "+ baru: " : c.kind === "hilang" ? "− tidak ada lagi: " : "~ ") + esc(c.label) +
            (c.detail ? " (" + esc(c.detail.join(" · ")) + ")" : "") + "</small>";
        }).join("") + (groups[g].length > 8 ? "<small>… dan " + (groups[g].length - 8) + " lagi</small>" : "") + "</div>";
      }).join("") : "<div class='rn-ob-muted'>Tidak ada perubahan.</div>") +
      '<div class="rn-ob-actions"><button type="button" id="rnObReload">Muat ulang halaman</button><button type="button" id="rnObClose2">Tutup</button></div>';
    p.querySelector("#rnObReload").onclick = function () { location.reload(); };
    p.querySelector("#rnObClose2").onclick = function () { p.remove(); };
  }

  var toastTimer = null;
  function toast(text) {
    if (!document.body) return; ensureCss();
    var t = document.getElementById("rnObToast");
    if (!t) { t = document.createElement("div"); t.id = "rnObToast"; t.className = "rn-ob-toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = text; clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.remove(); }, 6000);
  }
  function banner(text, withSync) {
    if (!document.body) return; ensureCss();
    var b = document.getElementById("rnObBanner");
    if (!b) { b = document.createElement("div"); b.id = "rnObBanner"; b.className = "rn-ob-banner"; b.setAttribute("role", "status"); document.body.prepend(b); }
    b.innerHTML = "<span>" + esc(text) + "</span>" + (withSync ? '<button type="button" id="rnObBannerSync">Sinkronkan sekarang</button>' : "");
    var s = document.getElementById("rnObBannerSync"); if (s) s.onclick = function () { b.remove(); flush({ refresh: true }); };
  }
  // system notification when allowed (installed app), always an in-page message too
  function notify(title, body) {
    toast(title + " — " + body);
    try {
      if (window.Notification && Notification.permission === "granted") {
        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
          navigator.serviceWorker.ready.then(function (r) { r.showNotification(title, { body: body, icon: "/rescue-net/assets/img/pwa/icon-192.png", tag: "rn-sync" }); });
        } else { new Notification(title, { body: body }); }
      }
    } catch (e) { /* notifications blocked */ }
  }
  function askNotifications() {
    try { if (window.Notification && Notification.permission === "default") Notification.requestPermission(); } catch (e) {}
  }

  window.addEventListener("online", function () {
    var pend = load().filter(function (x) { return x.status === "pending"; }).length;
    banner(pend ? "Sinyal kembali — " + pend + " data siap disinkron." : "Sinyal kembali — memperbarui data posko.", true);
    notify("Sinyal kembali", pend ? pend + " data dari HP siap disinkron." : "Data posko diperbarui.");
    setTimeout(function () { flush({ refresh: true }); }, 4000);
  });
  window.addEventListener("offline", function () { banner("Tidak ada sinyal. Data posko Anda tetap terbuka dari HP; isian baru disimpan dan dikirim nanti."); });
  document.addEventListener("DOMContentLoaded", function () {
    render();
    if (!navigator.onLine) { banner("Tidak ada sinyal. Data posko Anda tetap terbuka dari HP; isian baru disimpan dan dikirim nanti."); return; }
    original("rescue_net.api_auth.session_info").then(function (s) {
      checkUser(s);
      if (s && s.user && s.user !== "Guest") askNotifications();
    }).catch(function () {});
    flush();
  });
  setInterval(function () { flush(); }, 60000);

  window.RNOutbox = { flush: flush, items: load, saveMethods: SAVE, downloadPack: downloadPack, diff: diffData, keyOf: keyOf, wipe: wipe };
})();
