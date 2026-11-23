/* Pengaturan Posko > Bencana dilayani (owner 2026-10-19): per posko yang
 * dikelola user, kartu pilihan bencana (RNEventChecklist) + Simpan ->
 * rescue_net.api_community_cluster.set_posko_served_events. Posko logistik /
 * distribusi / collection hub: beberapa bencana; jenis lain: satu. */
(function () {
  "use strict";

  var MULTI_TYPES = ["logistics", "transport", "collection_hub", "communication", "equipment", "volunteer"];
  var TYPE_LABEL = { logistics: "Posko Logistik", transport: "Posko Distribusi", collection_hub: "Collection Hub",
    shelter: "Shelter", kitchen: "Dapur Umum", medical: "Posko Medis", field_assessment: "Field Assessment",
    communication: "Posko Komunikasi", equipment: "Posko Alat Kerja / Support", volunteer: "Posko Relawan", sar: "Posko SAR" };

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  async function mount(panel, posko, onSaved) {
    let settings;
    try {
      settings = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.posko_served_events", { posko: posko });
    } catch (e) {
      panel.textContent = "Daftar bencana gagal dimuat.";
      return;
    }
    if (!settings?.can_manage) {
      panel.textContent = "Pengaturan bencana belum tersedia untuk posko ini.";
      return;
    }
    var p = settings;
    var type = String(p.posko_type || "").toLowerCase();
    var multi = MULTI_TYPES.includes(type);
    panel.innerHTML = '<div class="rn-pse-posko">' +
      '<div class="rn-pse-head"><h3>' + esc(p.title || p.posko) + '</h3><span class="rn-muted">' +
      esc(TYPE_LABEL[type] || p.posko_type || "Posko") +
      (multi ? " · bisa beberapa bencana" : " · satu bencana") + "</span></div>" +
      '<div class="rn-pse-picker"></div>' +
      '<div class="rn-pse-actions"><button class="btn primary" type="button" data-save>Simpan Bencana</button>' +
      '<span class="rn-muted" role="status" data-msg></span></div></div>';

    var picker = window.RNEventChecklist.mount(panel.querySelector(".rn-pse-picker"),
      { selected: p.events || [], multiple: multi });
    var msg = panel.querySelector("[data-msg]");
    panel.querySelector("[data-save]").addEventListener("click", async function () {
      var events = picker.getSelected();
      if (!events.length) { msg.textContent = "Pilih minimal satu bencana."; return; }
      this.disabled = true;
      msg.textContent = "Menyimpan…";
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_community_cluster.set_posko_served_events",
          { posko: p.posko, disaster_events: JSON.stringify(events) }, { method: "POST" });
        picker.setSelected(r.events || events);
        onSaved();
        msg.textContent = "Tersimpan · " + (r.events || events).length + " bencana ditangani.";
      } catch (e) {
        msg.textContent = "Gagal: " + ((e && e.message) || e);
      }
      this.disabled = false;
    });
  }

  window.RNPoskoEventsSettings = { mount: mount };
})();
