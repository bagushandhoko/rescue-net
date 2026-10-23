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
