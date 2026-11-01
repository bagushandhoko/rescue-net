/* Relawan Saya → "Jadi node komunikasi" (owner 2026-11-01).
 * API: rescue_net.api_comms.my_comms_nodes / offer_comms_node / withdraw_comms_node. */
(function () {
  "use strict";
  var API = "rescue_net.api_comms.";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, ""); };
  var call = function (m, a, post) { return window.RN_FRAPPE.call(API + m, a || {}, post ? { method: "POST" } : undefined); };
  var NODES = [];

  function say(t, bad) { var m = $("cnMsg"); if (m) { m.textContent = t || ""; m.style.color = bad ? "#c0392b" : ""; } }

  function render() {
    var el = $("cnList");
    if (!NODES.length) { el.innerHTML = '<p class="rn-muted">Anda belum terdaftar sebagai node komunikasi.</p>'; return; }
    el.innerHTML = NODES.map(function (n) {
      var radio = [n.frequency, n.channel].filter(Boolean).join(" · ");
      var bits = [n.category_label, radio, n.coverage_km ? "±" + n.coverage_km + " km" : "", n.power ? "⚡ " + n.power : ""].filter(Boolean);
      return '<div class="rn-kom-net-card"><b>' + esc(n.scope) + "</b> · 📍 " + esc(n.location) +
        "<p>" + esc(bits.join(" · ")) + "</p>" +
        (n.call_sign || n.phone ? "<p><small>" + esc([n.call_sign, n.phone].filter(Boolean).join(" · ")) + "</small></p>" : "") +
        '<div class="form-actions"><button class="btn mini" type="button" data-cn-edit="' + esc(n.name) + '">Ubah</button>' +
        '<button class="btn mini" type="button" data-cn-off="' + esc(n.name) + '">Tarik</button></div></div>';
    }).join("");
  }

  function fill(n) {
    var f = $("cnForm");
    f.reset();
    if (!n) { f.comms_device.value = ""; $("cnSubmit").textContent = "Daftarkan node"; $("cnReset").hidden = true; return; }
    ["comms_device", "disaster_event", "category", "current_location", "frequency_mhz", "frequency_channel",
     "power_source", "notes"].forEach(function (k) {
      var v = k === "comms_device" ? n.name : k === "current_location" ? n.location : n[k];
      if (f[k]) f[k].value = v == null ? "" : v;
    });
    f.contact_id.value = n.call_sign || "";
    f.contact_phone.value = n.phone || "";
    f.coverage_km.value = n.coverage_km || "";
    f.power_endurance_hours.value = n.endurance_hours || "";
    $("cnSubmit").textContent = "Simpan perubahan";
    $("cnReset").hidden = false;
    f.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function load() {
    var r = await call("my_comms_nodes");
    NODES = r.nodes || [];
    render();
  }

  async function loadEvents() {
    try {
      var r = await window.RN_FRAPPE.call("rescue_net.api_volunteer_booking.my_volunteer");
      var sel = $("cnForm").disaster_event;
      (r.events || []).forEach(function (e) {
        var o = document.createElement("option"); o.value = e.id; o.textContent = e.title; sel.appendChild(o);
      });
    } catch (e) { /* standby option still works */ }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    var form = $("cnForm");
    if (!form || !window.RN_FRAPPE) return;
    var sess = null;
    try { sess = await window.RN_FRAPPE.call("rescue_net.api_auth.session_info"); } catch (e) {}
    if (!sess || !sess.user || sess.user === "Guest") return;  // panel sits inside #rsPanel, hidden for guests

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var args = {};
      Array.prototype.forEach.call(form.elements, function (el) { if (el.name) args[el.name] = el.value.trim(); });
      if (!args.comms_device) delete args.comms_device;
      say("Menyimpan…");
      try {
        await call("offer_comms_node", args, true);
        say("Tersimpan. Node Anda tampil di halaman Alat Komunikasi.");
        fill(null);
        await load();
      } catch (err) { say((err && err.message) || err, true); }
    });
    $("cnReset").addEventListener("click", function () { fill(null); say(""); });
    document.addEventListener("click", async function (e) {
      var ed = e.target.closest("[data-cn-edit]"), off = e.target.closest("[data-cn-off]");
      if (ed) { fill(NODES.filter(function (n) { return n.name === ed.dataset.cnEdit; })[0]); return; }
      if (!off) return;
      if (window.confirm && !window.confirm("Tarik node komunikasi ini?")) return;
      try { await call("withdraw_comms_node", { comms_device: off.dataset.cnOff }, true); say("Node ditarik."); await load(); }
      catch (err) { say((err && err.message) || err, true); }
    });
    await loadEvents();
    try { await load(); } catch (err) { say((err && err.message) || err, true); }
    if (location.hash === "#node") $("node").scrollIntoView();
  });
})();
