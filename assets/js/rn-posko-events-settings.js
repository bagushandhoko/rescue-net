/* Setting > Bencana yang Ditangani Posko (owner 2026-10-19): per posko yang
 * dikelola user, kartu pilihan bencana (RNEventChecklist) + Simpan ->
 * rescue_net.api_community_cluster.set_posko_served_events. Posko logistik /
 * distribusi / collection hub: beberapa bencana; jenis lain: satu. */
(function () {
  "use strict";

  var MULTI_TYPES = ["logistics", "transport", "collection_hub"];
  var TYPE_LABEL = { logistics: "Posko Logistik", transport: "Posko Distribusi", collection_hub: "Collection Hub",
    shelter: "Shelter", kitchen: "Dapur Umum", medical: "Posko Medis", field_assessment: "Field Assessment" };

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  async function boot() {
    var group = document.getElementById("poskoEventsGroup");
    var panel = document.getElementById("poskoEventsPanel");
    if (!group || !panel || !window.RN_FRAPPE || !window.RNEventChecklist) return;
    var list;
    try {
      list = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.my_poskos_served_events");
    } catch (e) {
      return;                                   // guest / no account: section stays hidden
    }
    list = Array.isArray(list) ? list : [];
    group.hidden = false;
    if (!list.length) {
      panel.innerHTML = '<p class="rn-muted">Anda belum menjadi pengelola posko. Daftarkan posko di ' +
        '<a href="registrasi-posko.html">Registrasi Posko</a>, atau minta pengelola posko menambahkan Anda.</p>';
      return;
    }
    panel.innerHTML = list.map(function (p, i) {
      var multi = MULTI_TYPES.indexOf(String(p.posko_type || "").toLowerCase()) !== -1;
      return '<div class="rn-pse-posko" data-i="' + i + '">' +
        '<div class="rn-pse-head"><h3>' + esc(p.title || p.posko) + '</h3><span class="rn-muted">' +
          esc(TYPE_LABEL[String(p.posko_type || "").toLowerCase()] || p.posko_type || "Posko") +
          (multi ? " · bisa beberapa bencana" : " · satu bencana") + "</span></div>" +
        '<div class="rn-pse-picker"></div>' +
        '<div class="rn-pse-actions"><button class="btn primary" type="button" data-save>Simpan Bencana</button>' +
        '<span class="rn-muted" data-msg></span></div></div>';
    }).join("");

    list.forEach(function (p, i) {
      var box = panel.querySelector('.rn-pse-posko[data-i="' + i + '"]');
      var multi = MULTI_TYPES.indexOf(String(p.posko_type || "").toLowerCase()) !== -1;
      var picker = window.RNEventChecklist.mount(box.querySelector(".rn-pse-picker"),
        { selected: p.events || [], multiple: multi });
      var msg = box.querySelector("[data-msg]");
      box.querySelector("[data-save]").addEventListener("click", async function () {
        var events = picker.getSelected();
        if (!events.length) { msg.textContent = "Pilih minimal satu bencana."; return; }
        this.disabled = true;
        msg.textContent = "Menyimpan…";
        try {
          var r = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.set_posko_served_events",
            { posko: p.posko, disaster_events: JSON.stringify(events) }, { method: "POST" });
          picker.setSelected(r.events || events);
          msg.textContent = "Tersimpan · " + (r.events || events).length + " bencana ditangani.";
        } catch (e) {
          msg.textContent = "Gagal: " + ((e && e.message) || e);
        }
        this.disabled = false;
      });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
