/* Asisten AI di setiap halaman (owner 2026-11-02).
 * Loaded by rn-mobile-drawer.js. API: rescue_net.api_assistant.status / chat.
 * Not logged in / no AI key / quota spent / key rejected → friendly guidance instead of an error. */
(function () {
  "use strict";
  if (window.RNAIChat || /cetak-label|scan\.html|offline\.html/.test(location.pathname)) return;
  // loaded before the API client (rn-frappe-client.js): start once the page has fully loaded
  if (!window.RN_FRAPPE) { window.addEventListener("load", function () { if (window.RN_FRAPPE) boot(); }); return; }
  boot();

  function boot() {
  if (window.RNAIChat) return;
  window.RNAIChat = true;

  var API = "rescue_net.api_assistant.";
  var PREFIX = location.pathname.indexOf("/pages/") !== -1 ? "../" : (location.pathname.indexOf("/rescue-net") === 0 ? "" : "rescue-net/");
  var HKEY = "rnAiChatHistory";
  var qs = new URLSearchParams(location.search);
  var POSKO_PAGE = /posko|shelter|dapur|kelola-posko/.test(location.pathname);
  var STATE = { open: false, status: null, org: "" };

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function href(p) { return PREFIX + String(p).replace(/^\/?(rescue-net\/)?/, ""); }
  function history() { try { return JSON.parse(sessionStorage.getItem(HKEY) || "[]"); } catch (e) { return []; } }
  function saveHistory(h) { try { sessionStorage.setItem(HKEY, JSON.stringify(h.slice(-12))); } catch (e) {} }
  function eventId() { return window.rnActiveEvent || qs.get("event") || ""; }

  // answer text → safe HTML with line breaks and clickable relative Rescue-Net links
  function fmt(text) {
    var h = esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    h = h.replace(/(^|[\s(])((?:\.\.\/)?pages\/[\w\-]+\.html(?:[?#][\w\-=&%:.#]*)?)/g, function (_, pre, p) {
      return pre + '<a href="' + esc(href(p.replace(/^\.\.\//, ""))) + '">' + p + "</a>";
    });
    return h.replace(/\n/g, "<br>");
  }

  var css = ".rn-aic-btn{position:fixed;left:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px));z-index:9990;border:0;border-radius:999px;" +
    "padding:11px 16px;background:linear-gradient(135deg,#ef523d,#e8835d);color:#fff;font:700 14px/1 system-ui,sans-serif;box-shadow:0 8px 24px rgba(200,70,40,.35);cursor:pointer}" +
    ".rn-aic-panel{position:fixed;left:14px;bottom:calc(66px + env(safe-area-inset-bottom,0px));z-index:9991;width:min(420px,calc(100vw - 28px));" +
    "height:min(560px,calc(100dvh - 110px));display:flex;flex-direction:column;background:#fff;color:#2d211b;border-radius:16px;box-shadow:0 18px 50px rgba(0,0,0,.28);" +
    "font:14px/1.45 system-ui,sans-serif;overflow:hidden}" +
    ".rn-aic-panel[hidden]{display:none}.rn-aic-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 14px;background:#fff4ef;border-bottom:1px solid rgba(0,0,0,.08)}" +
    ".rn-aic-head b{font-size:15px}.rn-aic-head small{display:block;color:#7a6a60;font-size:12px}.rn-aic-x{border:0;background:none;font-size:22px;cursor:pointer;color:#7a6a60}" +
    ".rn-aic-log{flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px}" +
    ".rn-aic-q{align-self:flex-end;background:#ef523d;color:#fff;border-radius:14px 14px 4px 14px;padding:8px 12px;max-width:85%;overflow-wrap:anywhere}" +
    ".rn-aic-a{align-self:flex-start;background:#f6efe9;border-radius:14px 14px 14px 4px;padding:8px 12px;max-width:92%;overflow-wrap:anywhere}" +
    ".rn-aic-a a{color:#c4442f;font-weight:700}.rn-aic-note{background:#fff6e8;border:1px solid rgba(224,138,30,.45);border-radius:12px;padding:10px 12px;font-size:13px}" +
    ".rn-aic-note a{color:#c4442f;font-weight:700}.rn-aic-sugs{display:flex;flex-wrap:wrap;gap:6px}.rn-aic-sugs button{border:1px solid rgba(104,64,45,.2);background:#fff;border-radius:999px;padding:6px 10px;font:12px system-ui,sans-serif;cursor:pointer}" +
    ".rn-aic-form{display:flex;gap:8px;padding:10px;border-top:1px solid rgba(0,0,0,.08)}.rn-aic-form textarea{flex:1;resize:none;height:44px;border:1px solid rgba(0,0,0,.18);border-radius:10px;padding:8px 10px;font:14px system-ui,sans-serif}" +
    ".rn-aic-form button{border:0;border-radius:10px;padding:0 14px;background:#ef523d;color:#fff;font-weight:700;cursor:pointer}.rn-aic-form button:disabled{opacity:.5}" +
    ".rn-aic-key{display:inline-block;margin-top:4px;font-size:12px;color:#c4442f;font-weight:700;text-decoration:none}" +
    ".rn-aic-act{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#fff;border:1px solid rgba(239,82,61,.45);border-radius:12px;padding:8px 10px;font-size:13px}" +
    ".rn-aic-act button{border:0;border-radius:8px;padding:6px 12px;background:#2f9a5c;color:#fff;font-weight:700;cursor:pointer;flex:0 0 auto}.rn-aic-act button:disabled{opacity:.6}" +
    ".rn-aic-org{font-size:12px;margin-top:4px}.rn-aic-org select{font-size:12px;padding:2px 4px}" +
    "@media print{.rn-aic-btn,.rn-aic-panel{display:none!important}}";

  var SUGGEST = POSKO_PAGE
    ? ["Apa yang perlu saya tindak di posko ini?", "Stok apa yang hampir habis atau kedaluwarsa?", "Bagaimana cara menerima relawan yang menawarkan diri?"]
    : ["Bencana aktif apa saja sekarang?", "Ringkas situasi bencana ini", "Posko mana yang butuh bantuan logistik?", "Bagaimana cara mendaftarkan posko?"];

  function el(html) { var d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstChild; }

  function mount() {
    var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    var btn = el('<button type="button" class="rn-aic-btn" aria-haspopup="dialog">🤖 Tanya AI</button>');
    var panel = el('<section class="rn-aic-panel" role="dialog" aria-label="Asisten AI Rescue-Net" hidden>' +
      '<div class="rn-aic-head"><div><b>🤖 Asisten AI Rescue-Net</b><small id="rnAicSrc">Bantu atur posko &amp; cari data</small>' +
      '<div class="rn-aic-org" id="rnAicOrg" hidden></div><a class="rn-aic-key" id="rnAicKey" href="#">⚙ Atur kunci AI</a></div>' +
      '<button type="button" class="rn-aic-x" aria-label="Tutup">×</button></div>' +
      '<div class="rn-aic-log" id="rnAicLog"></div>' +
      '<form class="rn-aic-form" id="rnAicForm"><textarea name="q" placeholder="Tulis pertanyaan…" maxlength="1500"></textarea><button type="submit">Kirim</button></form></section>');
    document.body.appendChild(btn); document.body.appendChild(panel);
    panel.querySelector("#rnAicKey").href = href("pages/ai-settings.html");
    btn.addEventListener("click", toggle);
    panel.querySelector(".rn-aic-x").addEventListener("click", toggle);
    panel.querySelector("#rnAicForm").addEventListener("submit", function (e) { e.preventDefault(); send(); });
    panel.querySelector("textarea").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
    panel.addEventListener("click", function (e) {
      var s = e.target.closest("[data-sug]");
      if (s) { panel.querySelector("textarea").value = s.dataset.sug; send(); }
      var act = e.target.closest("[data-aic-act]");
      if (act) runAction(act);
    });
  }

  function log() { return document.getElementById("rnAicLog"); }
  function add(html, cls) { var d = document.createElement("div"); d.className = cls; d.innerHTML = html; log().appendChild(d); log().scrollTop = log().scrollHeight; return d; }

  function note(status, message, settings) {
    var link = settings ? ' <a href="' + esc(href(settings)) + '">Buka AI Settings ›</a>' : "";
    var html = {
      login: 'Login dulu untuk memakai Asisten AI. <a href="' + esc(href("pages/auth.html?next=" + encodeURIComponent(location.pathname.replace(/^.*\/pages\//, "") + location.search))) + '">Login ›</a>',
      no_key: esc(message) + link,
      quota: "⚠️ " + esc(message) + link,
      key_rejected: "⚠️ " + esc(message) + link,
      rate: "⏳ " + esc(message),
      disabled: esc(message) + link,
      forbidden: esc(message),
    }[status] || ("⚠️ " + esc(message || "Asisten AI belum bisa dipakai.") + link);
    add(html, "rn-aic-note");
    // owner 2026-11-02: "jika belum isi key-nya, otomatis pindahkan ke halaman setting-nya"
    // (own/shared key only — a chosen organisation without a key is the org admin's job, not this user's)
    if ((status === "no_key" || status === "key_rejected") && settings && !STATE.org && !/ai-settings\.html/.test(location.pathname)) {
      add("Membuka halaman AI Settings…", "rn-aic-note");
      setTimeout(function () { location.href = href(settings) + (settings.indexOf("?") === -1 ? "?" : "&") + "from=ai-chat"; }, 1500);
    }
  }

  async function loadStatus() {
    var s;
    try { s = await window.RN_FRAPPE.call(API + "status", STATE.org ? { organization_id: STATE.org } : {}); }
    catch (e) { s = { status: "error", message: (e && e.message) || "Gagal memeriksa AI." }; }
    STATE.status = s;
    var src = document.getElementById("rnAicSrc");
    src.textContent = s.status === "ok" ? "Memakai " + (s.source || "kunci AI") : "Bantu atur posko & cari data";
    var orgBox = document.getElementById("rnAicOrg");
    var orgs = s.organizations || [];
    if (orgs.length) {
      orgBox.hidden = false;
      orgBox.innerHTML = 'Kunci AI: <select id="rnAicOrgSel"><option value="">pribadi / bersama</option>' + orgs.map(function (o) {
        return '<option value="' + esc(o.id) + '"' + (o.id === STATE.org ? " selected" : "") + ">" + esc(o.title) + "</option>"; }).join("") + "</select>";
      orgBox.querySelector("select").addEventListener("change", function (e) { STATE.org = e.target.value; log().innerHTML = ""; start(); });
    }
    return s;
  }

  async function start() {
    var s = await loadStatus();
    var h = history();
    if (s.status !== "ok") { note(s.status, s.message, s.settings); return; }
    if (!h.length) {
      add("Halo! Saya bisa membantu <b>mengatur posko</b> (langkah &amp; halaman yang dipakai) dan <b>mencari data</b> Rescue-Net (posko, organisasi, bencana, kebutuhan, stok). Saya juga bisa <b>menjelaskan cara memakai Rescue-Net</b>, dan mengusulkan <b>pengaturan</b> (status &amp; kontak posko, kebutuhan, stok, relawan, profil relawan Anda) — perubahan baru terjadi setelah Anda menekan <b>Jalankan</b>.", "rn-aic-a");
      add('<div class="rn-aic-sugs">' + SUGGEST.map(function (x) { return '<button type="button" data-sug="' + esc(x) + '">' + esc(x) + "</button>"; }).join("") + "</div>", "");
    } else {
      h.forEach(function (x) { add(esc(x.q), "rn-aic-q"); add(fmt(x.a), "rn-aic-a"); });
    }
  }

  function toggle() {
    var panel = document.querySelector(".rn-aic-panel");
    STATE.open = panel.hidden;
    panel.hidden = !STATE.open;
    if (STATE.open && !log().childElementCount) start();
    if (STATE.open) setTimeout(function () { panel.querySelector("textarea").focus(); }, 50);
  }

  // network drop / gateway / Cloudflare 52x — worth one retry, not the user's key
  function transient(e) {
    var st = e && e.status;
    return !st || st === 408 || st === 502 || st === 503 || st === 504 || (st >= 520 && st <= 527);
  }

  async function send() {
    var panel = document.querySelector(".rn-aic-panel");
    var ta = panel.querySelector("textarea"), b = panel.querySelector("button[type=submit]");
    var q = ta.value.trim();
    if (!q || b.disabled) return;
    if (STATE.status && STATE.status.status !== "ok") { note(STATE.status.status, STATE.status.message, STATE.status.settings); return; }
    ta.value = ""; b.disabled = true;
    add(esc(q), "rn-aic-q");
    var wait = add("Sedang berpikir…", "rn-aic-a");
    var h = history();
    try {
      var args = {
        question: q, page: document.title + " — " + location.pathname, disaster_event: eventId() || null,
        posko: POSKO_PAGE ? (qs.get("id") || qs.get("posko") || null) : null,
        organization_id: STATE.org || null, history: JSON.stringify(h.slice(-6)),
      };
      var r;
      try { r = await window.RN_FRAPPE.call(API + "chat", args, { method: "POST" }); }
      catch (e1) {
        // owner 2026-11-02: "Frappe HTTP 520 / 525" — the connection dropped on the way (Cloudflare / signal).
        // Try once more after a short pause before showing an error.
        if (!transient(e1)) throw e1;
        wait.innerHTML = "Koneksi terputus sebentar, mencoba lagi…";
        await new Promise(function (ok) { setTimeout(ok, 2500); });
        r = await window.RN_FRAPPE.call(API + "chat", args, { method: "POST" });
      }
      wait.remove();
      if (r.status !== "ok") { STATE.status = r; note(r.status, r.message, r.settings); return; }
      add(fmt(r.answer), "rn-aic-a");
      // owner 2026-11-02: actions the AI proposes — the user decides by pressing "Jalankan"
      (r.actions || []).forEach(function (a) {
        add('<div class="rn-aic-act"><span>⚡ ' + esc(a.label) + '</span><button type="button" data-aic-act="' +
          esc(JSON.stringify({ action: a.action, params: a.params })) + '">Jalankan</button></div>', "");
      });
      h.push({ q: q, a: r.answer }); saveHistory(h);
    } catch (e) {
      wait.remove();
      if (transient(e)) {
        add("📶 Koneksi ke server terputus (" + esc(String((e && e.status) || "jaringan")) + "). Periksa sinyal/internet lalu kirim lagi — pertanyaan Anda: <i>" + esc(q) + "</i>", "rn-aic-note");
      } else {
        note("error", (e && e.message) || "Permintaan gagal.", null);
      }
    } finally { b.disabled = false; }
  }

  async function runAction(btn) {
    var spec = JSON.parse(btn.getAttribute("data-aic-act"));
    var label = btn.parentNode.querySelector("span").textContent.replace(/^⚡\s*/, "");
    if (!window.confirm("Jalankan: " + label + "?")) return;
    btn.disabled = true; btn.textContent = "Menjalankan…";
    var args = { action: spec.action, params: JSON.stringify(spec.params || {}) };
    try {
      if (spec.action === "armada_position") {
        if (!navigator.geolocation) throw new Error("HP/peramban tidak mendukung GPS.");
        var p = await new Promise(function (ok, bad) {
          navigator.geolocation.getCurrentPosition(ok, function () { bad(new Error("Izin lokasi ditolak.")); }, { enableHighAccuracy: true, timeout: 20000 });
        });
        args.latitude = p.coords.latitude; args.longitude = p.coords.longitude; args.accuracy_m = p.coords.accuracy;
      }
      var r = await window.RN_FRAPPE.call(API + "run_action", args, { method: "POST" });
      btn.textContent = "✓ Selesai"; add("✅ " + esc(r.message || "Selesai."), "rn-aic-a");
    } catch (e) {
      btn.disabled = false; btn.textContent = "Jalankan";
      add("⚠️ " + esc((e && e.message) || e), "rn-aic-note");
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
  }
})();
