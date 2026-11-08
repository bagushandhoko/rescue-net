// Banner: kuota AI bersama (organisasi/platform) habis -> ajak user memasang kunci AI sendiri.
(function () {
  "use strict";
  if (/ai-settings\.html/.test(location.pathname) || document.getElementById("rnAiNotice")) return;
  var base = (window.RN_FRAPPE_BASE || "/rescue-net-frappe/api/method");
  function call(m, args) {
    var u = base + "/" + m;
    var o = { credentials: "same-origin", headers: { Accept: "application/json" } };
    if (args) {
      o.method = "POST";
      o.headers["Content-Type"] = "application/json";
      var t = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
      if (t) o.headers["X-Frappe-CSRF-Token"] = decodeURIComponent(t[1]);
      o.body = JSON.stringify(args);
    }
    return fetch(u, o).then(function (r) { return r.ok ? r.json() : null; });
  }
  call("rescue_net.api_ai.my_ai_notices").then(function (d) {
    var n = d && d.message && d.message.notices && d.message.notices[0];
    if (!n) return;
    var bar = document.createElement("div");
    bar.id = "rnAiNotice";
    bar.setAttribute("role", "status");
    bar.style.cssText = "position:fixed;left:12px;right:12px;bottom:12px;z-index:9000;max-width:640px;margin:0 auto;" +
      "background:#fff8e6;color:#4a3500;border:1px solid #e6c36a;border-radius:12px;padding:12px 14px;" +
      "box-shadow:0 4px 16px rgba(0,0,0,.2);display:flex;gap:10px;align-items:center;font-size:14px";
    var msg = document.createElement("span");
    msg.style.flex = "1";
    msg.textContent = n.message;
    var go = document.createElement("a");
    go.href = "ai-settings.html";
    go.textContent = "Pasang kunci";
    go.style.cssText = "font-weight:700;white-space:nowrap";
    var x = document.createElement("button");
    x.type = "button"; x.textContent = "✕"; x.setAttribute("aria-label", "Tutup");
    x.style.cssText = "border:0;background:none;font-size:18px;cursor:pointer";
    x.addEventListener("click", function () {
      bar.remove();
      call("rescue_net.api_ai.dismiss_ai_notice", { notice: n.id });
    });
    bar.appendChild(msg); bar.appendChild(go); bar.appendChild(x);
    document.body.appendChild(bar);
  }).catch(function () {});
})();

// 🔔 Kotak pemberitahuan (owner 2026-11-08): keputusan posko/organisasi/keanggotaan, penempatan, donasi masuk,
// Saran baru, dst. Tampil hanya untuk pengguna yang login.
(function () {
  if (window.__rnInbox) return; window.__rnInbox = true;
  var API = "/rescue-net-frappe/api/method/rescue_net.api_inbox.";
  function req(m, body) {
    var o = { credentials: "include", headers: { "Accept": "application/json" } };
    if (body) {
      o.method = "POST"; o.headers["Content-Type"] = "application/json";
      var t = /(?:^|;\s*)csrf_token=([^;]+)/.exec(document.cookie);
      if (t) o.headers["X-Frappe-CSRF-Token"] = decodeURIComponent(t[1]);
      o.body = JSON.stringify(body);
    }
    return fetch(API + m, o).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { return j && j.message; });
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var css = document.createElement("style");
  css.textContent = ".rn-bell{position:relative;border:1px solid rgba(104,64,45,.25);background:#fff;border-radius:999px;width:36px;height:36px;font-size:17px;cursor:pointer;flex-shrink:0;margin-left:6px}" +
    ".rn-bell b{position:absolute;top:-4px;right:-4px;background:#d64545;color:#fff;border-radius:999px;font:700 11px/1 system-ui;padding:3px 5px;min-width:18px}" +
    ".rn-bell-pop{position:fixed;z-index:9500;top:60px;right:max(12px,env(safe-area-inset-right,0px));width:min(380px,calc(100vw - 24px));max-height:70vh;overflow:auto;background:#fff;border:1px solid rgba(104,64,45,.2);border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.18);padding:8px}" +
    ".rn-bell-pop h4{margin:4px 6px 8px;font-size:15px}.rn-bell-pop a,.rn-bell-pop div.it{display:block;padding:8px 10px;border-radius:8px;color:inherit;text-decoration:none;font-size:14px;overflow-wrap:anywhere}" +
    ".rn-bell-pop .new{background:#fff6f1}.rn-bell-pop small{display:block;color:#7c6458;font-size:12px;margin-top:2px}";
  document.head.appendChild(css);
  var pop = null, data = null;
  function render(btns) {
    btns.forEach(function (b) { b.innerHTML = "🔔" + (data.unread ? "<b>" + (data.unread > 99 ? "99+" : data.unread) + "</b>" : ""); });
  }
  function open() {
    if (pop) { pop.remove(); pop = null; return; }
    pop = document.createElement("div"); pop.className = "rn-bell-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Pemberitahuan");
    var items = (data && data.items) || [];
    pop.innerHTML = "<h4>Pemberitahuan</h4>" + (items.length ? items.map(function (n) {
      var inner = esc(n.subject) + "<small>" + esc(n.at) + "</small>";
      return n.link ? '<a class="' + (n.read ? "" : "new") + '" href="' + esc(n.link) + '">' + inner + "</a>"
                    : '<div class="it ' + (n.read ? "" : "new") + '">' + inner + "</div>";
    }).join("") : '<div class="it">Belum ada pemberitahuan.</div>');
    document.body.appendChild(pop);
    if (data && data.unread) { req("mark_notifications_read", {}).then(function () { data.unread = 0; render(document.querySelectorAll(".rn-bell")); }); }
  }
  document.addEventListener("click", function (e) {
    if (pop && !pop.contains(e.target) && !e.target.closest(".rn-bell")) { pop.remove(); pop = null; }
  });
  function mount() {
    // hanya satu lonceng: topbar HP bila terlihat, kalau tidak header halaman (owner 2026-11-08: lonceng dobel di HP)
    var top = document.querySelector(".rn-drawer-topbar"), head = document.querySelector("header.topbar");
    var vis = function (el) { return el && el.offsetParent !== null && getComputedStyle(el).display !== "none"; };
    var spots = [vis(top) ? top : (head || top)].filter(Boolean);
    document.querySelectorAll(".rn-bell").forEach(function (x) { if (spots.indexOf(x.parentNode) === -1) x.remove(); });
    var btns = [];
    spots.forEach(function (sp) {
      if (sp.querySelector(".rn-bell")) return;
      var b = document.createElement("button"); b.type = "button"; b.className = "rn-bell"; b.setAttribute("aria-label", "Pemberitahuan");
      b.setAttribute("data-no-i18n", ""); b.addEventListener("click", function (e) { e.stopPropagation(); open(); });
      sp.appendChild(b); btns.push(b);
    });
    return btns;
  }
  function load() {
    req("my_notifications").then(function (d) {
      if (!d || !d.logged_in) return;
      data = d;
      var btns = mount();
      if (!btns.length) setTimeout(function () { render(mount()); }, 1500);
      render(document.querySelectorAll(".rn-bell"));
    }).catch(function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(load, 300); });
  else setTimeout(load, 300);
})();
