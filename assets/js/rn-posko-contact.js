/* ============================================================
 * rn-posko-contact.js — contact bar at the top of every posko page
 * (posko-detail, posko-logistik, posko-distribusi, posko-medis-detail,
 * shelter-detail, dapur-umum). Owner rule 2026-10-18: the phone /
 * WhatsApp number is shown only to a logged-in user; a guest sees a
 * "login untuk melihat" link. The server enforces it
 * (rescue_net.api_control_centre.posko_contact never sends a number to
 * a guest) — this file only renders.
 * Needs ?id= (or ?posko=) in the URL; without it nothing is shown.
 * ============================================================ */
(function () {
  "use strict";

  if (!window.RN_FRAPPE || !window.RN_FRAPPE.call) return;

  var qs = new URLSearchParams(location.search);
  var posko = qs.get("id") || qs.get("posko") || "";
  if (!posko) return;

  function esc(s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); }
  function digits(n) { return String(n || "").replace(/[^\d+]/g, ""); }
  function waNumber(n) {
    var d = digits(n).replace(/^\+/, "");
    if (d.indexOf("0") === 0) d = "62" + d.slice(1);
    return d;
  }

  var CSS =
    ".rn-posko-contact{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin:0 0 14px;" +
    "padding:10px 14px;border:1px solid var(--line,rgba(104,64,45,.14));border-radius:14px;" +
    "background:var(--panel,#fff);color:var(--text,#2d211b);font-size:14px;line-height:1.35}" +
    ".rn-posko-contact .rn-pc-label{font-weight:700;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--coral,#ef6f5e)}" +
    ".rn-posko-contact .rn-pc-who{color:var(--muted,#7c6458)}" +
    ".rn-posko-contact .rn-pc-num{font-weight:700;font-variant-numeric:tabular-nums;color:inherit}" +
    ".rn-posko-contact .rn-pc-hidden{color:var(--muted,#7c6458)}" +
    ".rn-posko-contact .rn-pc-btn{display:inline-flex;align-items:center;min-height:32px;padding:4px 12px;border-radius:999px;" +
    "border:1px solid var(--line,rgba(104,64,45,.2));text-decoration:none;font-weight:600;color:var(--text,#2d211b);background:#fff}" +
    ".rn-posko-contact .rn-pc-wa{background:#25d366;border-color:#25d366;color:#fff}" +
    ".rn-posko-contact a:focus-visible{outline:2px solid var(--blue,#3b82c4);outline-offset:2px}";

  function mount() {
    if (!document.getElementById("rn-posko-contact-css")) {
      var st = document.createElement("style");
      st.id = "rn-posko-contact-css";
      st.textContent = CSS;
      document.head.appendChild(st);
    }
    var bar = document.createElement("div");
    bar.className = "rn-posko-contact";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Kontak posko");
    var top = document.querySelector("main .topbar, .topbar");
    if (top && top.parentNode) top.parentNode.insertBefore(bar, top.nextSibling);
    else (document.querySelector("main") || document.body).prepend(bar);
    return bar;
  }

  function render(bar, res) {
    var label = '<span class="rn-pc-label">Kontak Posko</span>';
    if (!res || !res.logged_in) {
      var next = encodeURIComponent(location.pathname + location.search);
      bar.innerHTML = label +
        '<span class="rn-pc-hidden">Nomor HP / WhatsApp hanya terlihat setelah login.</span>' +
        '<a class="rn-pc-btn" href="auth.html?next=' + next + '">Login untuk melihat</a>';
      return;
    }
    var c = res.contact || {};
    var who = [c.name, c.role].filter(Boolean).map(esc).join(" · ");
    var parts = [label];
    if (who) parts.push('<span class="rn-pc-who">' + who + "</span>");
    if (c.phone) {
      parts.push('<a class="rn-pc-num" href="tel:' + esc(digits(c.phone)) + '">' + esc(c.phone) + "</a>");
    }
    if (c.whatsapp) {
      parts.push('<a class="rn-pc-btn rn-pc-wa" target="_blank" rel="noopener" href="https://wa.me/' +
        esc(waNumber(c.whatsapp)) + '">WhatsApp ' + (c.whatsapp !== c.phone ? esc(c.whatsapp) : "") + "</a>");
    }
    if (c.phone) {
      parts.push('<a class="rn-pc-btn" href="tel:' + esc(digits(c.phone)) + '">Telepon</a>');
    }
    if (c.emergency && c.emergency !== c.phone) {
      parts.push('<span class="rn-pc-who">Darurat: <a href="tel:' + esc(digits(c.emergency)) + '">' + esc(c.emergency) + "</a></span>");
    }
    if (!c.phone && !c.whatsapp && !c.emergency) {
      parts.push('<span class="rn-pc-hidden">Nomor kontak belum diisi pengelola posko.</span>');
    }
    bar.innerHTML = parts.join("");
  }

  function start() {
    var bar = mount();
    window.RN_FRAPPE.call("rescue_net.api_control_centre.posko_contact", { posko: posko })
      .then(function (res) { render(bar, res); })
      .catch(function () { bar.remove(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
