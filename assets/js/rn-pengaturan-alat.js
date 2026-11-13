/* Recovery Program & Alat Kerja (owner 2026-11-13): Posko Alat Kerja + Tawarkan Alat digabung ke alat-kerja.html.
 * Tombol "+ Tambah Alat Kerja" (tamu -> login dulu) dan "Pengaturan Alat Kerja" (aktif untuk pemilik alat /
 * pengelola posko alat kerja). Panel #pengaturan berisi form & "Alat Saya" (tawarkan-alat.js) + posko alat saya.
 * Pemilik alat yang login didaratkan ke alat-kerja.html#pengaturan (api_auth.my_landing). */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var qs = new URLSearchParams(location.search);
  var ev = qs.get("event") || "";
  var state = { loggedIn: null, tools: 0, poskos: 0 };

  function openPanel(scroll) {
    var box = $("pengaturan");
    if (!box) return;
    box.hidden = false;
    try { if (location.hash !== "#pengaturan") history.replaceState(null, "", location.pathname + location.search + "#pengaturan"); } catch (e) {}
    if (scroll) box.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function refreshSelf() {
    var b = $("akSelfBtn");
    if (!b) return;
    var owner = state.tools > 0 || state.poskos > 0;
    b.disabled = !owner;
    b.classList.toggle("primary", owner);
    b.title = owner ? "Alat saya, posko alat kerja saya, ubah data & ketersediaan" : "Aktif bila Anda pemilik alat atau pengelola posko alat kerja";
  }
  async function loadMyPoskos() {
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_equipment.equipment_poskos", ev ? { disaster_event: ev } : {});
      var mine = (r.poskos || []).filter(function (p) { return p.can_manage && p.is_equipment_posko; });
      state.poskos = mine.length;
      if ($("akMyPoskosPanel")) $("akMyPoskosPanel").hidden = !mine.length;
      if ($("akMyPoskos")) $("akMyPoskos").innerHTML = mine.map(function (p) {
        return '<div class="rs-opt" style="display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid rgba(104,64,45,.12)"><div><b>' +
          esc(p.title) + "</b><br><small>" + esc(p.address || "") + " · " + (p.items || 0) + " jenis alat</small></div>" +
          '<a class="btn mini" href="posko-alat.html?id=' + encodeURIComponent(p.name) + (ev ? "&event=" + encodeURIComponent(ev) : "") + '">Kelola inventaris</a></div>';
      }).join("");
    } catch (e) { state.poskos = 0; }
    refreshSelf();
  }
  document.addEventListener("rn-mytools", function (e) { state.tools = (e.detail || []).length; refreshSelf(); });

  async function init() {
    if (!$("pengaturan") || !window.RN_FRAPPE) return;
    var st = {};
    try { st = await window.RN_FRAPPE.call("rescue_net.api_auth.account_status", {}); } catch (e) {}
    state.loggedIn = !!(st && st.logged_in && st.registered);
    var add = $("akAddBtn");
    if (add) add.addEventListener("click", function () {
      if (!state.loggedIn) { location.href = "auth.html?next=" + encodeURIComponent("alat-kerja.html" + location.search + "#pengaturan"); return; }
      openPanel(true);
      var f = $("taForm"); if (f) { var first = f.querySelector("input[name=resource_name], input:not([type=hidden])"); if (first) setTimeout(function () { first.focus(); }, 400); }
    });
    var self = $("akSelfBtn");
    if (self) self.addEventListener("click", function () { var box = $("pengaturan"); if (box && !box.hidden) box.hidden = true; else openPanel(true); });
    if (state.loggedIn) await loadMyPoskos();
    refreshSelf();
    if (location.hash === "#pengaturan") openPanel(true);
  }
  window.addEventListener("hashchange", function () { if (location.hash === "#pengaturan") { if (state.loggedIn === false) { location.href = "auth.html?next=" + encodeURIComponent("alat-kerja.html" + location.search + "#pengaturan"); } else openPanel(true); } });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
