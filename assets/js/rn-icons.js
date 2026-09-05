/* ============================================================
 * rn-icons.js — tiny inline-SVG line-icon set (Lucide-style,
 * 24x24, stroke=currentColor). No dependency, no icon font.
 *
 *   window.RNIcon("truck")            -> "<svg …>…</svg>"
 *   <span data-icon="truck"></span>   -> auto-filled on DOMContentLoaded
 *   <a data-nav-icon="posko">…        -> nav links (rn-navigation-v2)
 *
 * Re-scans on the custom event "rn:icons-refresh" (dispatch after you
 * inject markup that contains [data-icon]).
 * ============================================================ */
(function () {
  "use strict";
  if (window.RNIcon) return;

  // each entry: inner markup of a 24x24 viewBox, stroke-based
  var P = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-6h5v6"/>',
    "alert-triangle": '<path d="M12 3.5 22 20H2Z"/><path d="M12 9v5"/><circle cx="12" cy="17.5" r=".6" fill="currentColor"/>',
    "alert-circle": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6"/><circle cx="12" cy="16.5" r=".6" fill="currentColor"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8" fill="currentColor"/>',
    "map-pin": '<path d="M12 21s7-5.7 7-11a7 7 0 1 0-14 0c0 5.3 7 11 7 11Z"/><circle cx="12" cy="10" r="2.6"/>',
    map: '<path d="m9 4-6 2.5v13.5L9 17.5m0-13.5 6 2.5m-6-2.5v13.5m6-11 6-2.5v13.5L15 20m0-13.5v13.5m0 0-6-2.5"/>',
    building: '<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M9 7h1.5M13.5 7H15M9 11h1.5M13.5 11H15M9 15h1.5M13.5 15H15M10 21v-3h4v3"/>',
    "clipboard-check": '<rect x="6" y="4" width="12" height="17" rx="1.5"/><path d="M9 4V3h6v1"/><path d="m9 13 2 2 4-4"/>',
    edit: '<path d="m16.5 3.5 4 4L8 20H4v-4Z"/><path d="m14.5 5.5 4 4"/>',
    package: '<path d="M12 3 3.5 7.5v9L12 21l8.5-4.5v-9Z"/><path d="M3.5 7.5 12 12l8.5-4.5M12 12v9"/>',
    box: '<rect x="4" y="6" width="16" height="14" rx="1.5"/><path d="M4 10h16M9.5 6V4h5v2"/>',
    truck: '<path d="M2 6.5h11v9H2Z"/><path d="M13 9.5h4l3 3v3h-7Z"/><circle cx="6.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/>',
    route: '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H14a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h1.5"/>',
    pot: '<path d="M4 9h16v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5Z"/><path d="M2.5 9h19"/><path d="M9 6c0-1.5-1.5-1.5-1.5-3M13 6c0-1.5-1.5-1.5-1.5-3"/>',
    utensils: '<path d="M6 3v8a2 2 0 0 0 4 0V3M8 11v10"/><path d="M16 3c-1.7 0-3 2-3 5s1.3 4 3 4v9"/>',
    cross: '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6Z"/>',
    pill: '<rect x="3" y="8" width="18" height="8" rx="4" transform="rotate(-45 12 12)"/><path d="m9 9 6 6"/>',
    tent: '<path d="M12 4 3 20h18ZM12 4v16"/>',
    bed: '<path d="M3 7v13M3 12h15a3 3 0 0 1 3 3v5M3 16h18"/><circle cx="7.5" cy="10.5" r="1.8"/>',
    users: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c0-3.3 2.6-5.5 5.5-5.5s5.5 2.2 5.5 5.5"/><path d="M16 5.2A3.2 3.2 0 0 1 16 11M17 14.8c2.3.6 3.9 2.6 3.9 5.2"/>',
    "hand-heart": '<path d="M11 8.5 9.7 7.2a2 2 0 0 0-2.8 2.8L11 14l4.1-4a2 2 0 0 0-2.8-2.8Z"/><path d="M3 15l3.5-1.5M3 20h6l3 1 8-3a1.6 1.6 0 0 0-1.4-2.8L14 17"/>',
    wrench: '<path d="M20 6.5a4 4 0 0 1-5.3 5.3L6 20.5 3.5 18l8.7-8.7A4 4 0 0 1 17.5 4l-2.8 2.8 1.5 1.5Z"/>',
    hammer: '<path d="M14 6 9 11l-1.5-1.5a2 2 0 0 0-3 0l4.5 4.5a2 2 0 0 0 0-3L14 6Z"/><path d="M14 6 18 2l4 4-4 4Z"/><path d="m10 14-6 6"/>',
    radio: '<circle cx="12" cy="12" r="2.2"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 16.2a6 6 0 0 0 0-8.4M5 5a9.5 9.5 0 0 0 0 14M19 19a9.5 9.5 0 0 0 0-14"/>',
    "wifi-off": '<path d="M2 8.8a15 15 0 0 1 5-3M20 8.8a15 15 0 0 0-4-2.7M8.5 12.5a8 8 0 0 1 3-1.4M12 16.5l.01 0M15.5 12.5a8 8 0 0 0-2-1.2"/><path d="m3 3 18 18"/>',
    "id-card": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.5-1.6 1.7-2.4 3-2.4s2.5.8 3 2.4M14.5 10H18M14.5 13H18"/>',
    camera: '<path d="M4 8h3l1.5-2h7L18 8h2a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13" r="3.2"/>',
    "shield-check": '<path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    cpu: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 2.5v3M14 2.5v3M10 18.5v3M14 18.5v3M2.5 10h3M2.5 14h3M18.5 10h3M18.5 14h3"/>',
    sparkles: '<path d="m12 3 1.8 4.7L18.5 9.5 13.8 11.3 12 16l-1.8-4.7L5.5 9.5l4.7-1.8Z"/><path d="M18 15l.8 2 2 .8-2 .8L18 21l-.8-2-2-.8 2-.8Z"/>',
    sliders: '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h13M20 17h0"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="18" cy="17" r="2"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14-4.5L3 9M4 13a8 8 0 0 0 14 4.5L21 15"/><path d="M3 4v5h5M21 20v-5h-5"/>',
    book: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v16H6.5A1.5 1.5 0 0 0 5 20.5Z"/><path d="M5 20.5A1.5 1.5 0 0 1 6.5 19H19v2H6.5A1.5 1.5 0 0 1 5 20.5Z"/>',
    heart: '<path d="M12 20S3.5 14.5 3.5 8.8A4.8 4.8 0 0 1 12 6a4.8 4.8 0 0 1 8.5 2.8C20.5 14.5 12 20 12 20Z"/>',
    gift: '<rect x="3.5" y="8" width="17" height="4"/><path d="M5 12v9h14v-9M12 8v13"/><path d="M12 8S10 3.5 7.5 4.8 9.5 8 12 8Zm0 0s2-4.5 4.5-3.2S14.5 8 12 8Z"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    user: '<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    droplet: '<path d="M12 3s6 6.6 6 11a6 6 0 0 1-12 0c0-4.4 6-11 6-11Z"/>',
    flame: '<path d="M12 22c4 0 6.5-2.6 6.5-6 0-3.7-3-5.5-3-9 0 0-2 1.5-2.5 4C11 8 12 4 8.5 2c0 4-3.5 5.8-3.5 12 0 3.4 3 8 7 8Z"/>',
    "battery-low": '<rect x="2.5" y="8" width="16" height="8" rx="1.5"/><path d="M21 11v2"/><rect x="4.5" y="10" width="3" height="4" fill="currentColor" stroke="none"/>',
    activity: '<path d="M3 12h4l2.5-7 5 14 2.5-7H21"/>',
    layers: '<path d="M12 3 3 7.5 12 12l9-4.5Z"/><path d="m3 12 9 4.5L21 12M3 16.5 12 21l9-4.5"/>',
    gauge: '<path d="M4 18a9 9 0 1 1 16 0"/><path d="m12 13 4-4"/><circle cx="12" cy="14" r="1.4" fill="currentColor"/>',
    scale: '<path d="M12 4v16M7 20h10M6 4h12"/><path d="M6 4 3 11h6ZM18 4l-3 7h6Z"/><path d="M3 11a3 3 0 0 0 6 0M15 11a3 3 0 0 0 6 0"/>',
    "trending-up": '<path d="m3 16 6-6 4 4 8-8"/><path d="M15 6h6v6"/>',
    "trending-down": '<path d="m3 8 6 6 4-4 8 8"/><path d="M15 18h6v-6"/>',
    "map-signal": '<path d="M12 21s7-5.7 7-11a7 7 0 1 0-14 0c0 5.3 7 11 7 11Z"/><path d="M9.5 10a2.5 2.5 0 0 1 5 0"/>',
    dot: '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
  };

  // convenient aliases
  var ALIAS = {
    beranda: "home", bencana: "alert-triangle", warroom: "target",
    "control-centre": "target", posko: "map-pin", organisasi: "building",
    "registrasi-posko": "clipboard-check", logistik: "package",
    distribusi: "truck", "posko-distribusi": "truck", dapur: "pot",
    medis: "cross", shelter: "tent", relawan: "users", "alat-kerja": "wrench",
    komunikasi: "radio", resource: "id-card", evidence: "camera",
    verification: "shield-check", ai: "sparkles", "ai-analyst": "sparkles",
    "ai-settings": "sliders", sync: "refresh", "contact-directory": "book",
    donor: "heart", donasi: "heart", program: "gift", recovery: "hammer",
    "search-found": "search", akun: "user", jiwa: "users", kapasitas: "gauge",
    stok: "box", kebutuhan: "alert-circle", baterai: "battery-low",
    internet: "wifi-off", operator: "radio", repeater: "radio",
    bbm: "flame", air: "droplet", terhambat: "alert-circle",
    matched: "check-circle", terpakai: "layers", waktu: "clock",
  };

  function resolve(name) {
    name = String(name || "").trim().toLowerCase();
    return P[name] || P[ALIAS[name] || ""] || P.dot;
  }

  function svg(name, cls) {
    return (
      '<svg class="rn-ic ' + (cls || "") + '" viewBox="0 0 24 24" width="1em" height="1em" ' +
      'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-hidden="true" focusable="false">' + resolve(name) + "</svg>"
    );
  }

  function fill(root) {
    (root || document).querySelectorAll("[data-icon]:not([data-icon-done])").forEach(function (el) {
      el.setAttribute("data-icon-done", "1");
      el.insertAdjacentHTML("afterbegin", svg(el.getAttribute("data-icon"), "rn-ic-inline"));
    });
  }

  window.RNIcon = svg;
  window.RNIconFill = fill;

  if (document.readyState !== "loading") fill();
  else document.addEventListener("DOMContentLoaded", function () { fill(); });
  document.addEventListener("rn:icons-refresh", function () { fill(); });
})();
