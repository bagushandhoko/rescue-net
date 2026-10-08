/* Daftar saran AI (ADR-0002): saran berstatus draft untuk laporan warga dan kebutuhan logistik.
   Posko/Control Centre menerima atau menolak; tidak ada yang diubah AI sendiri.
   Panel hanya muncul bila ada saran yang boleh diputuskan pengguna. */
(function () {
  "use strict";
  if (!window.RN_FRAPPE || document.querySelector("[data-ai-suggestions]")) return;

  var LABEL = {
    title: "Judul", report_type: "Jenis", priority: "Prioritas", affected_people_count: "Jiwa terdampak",
    urgent_needs: "Kebutuhan mendesak", location_text: "Lokasi", damage_scale_value: "Skala kerusakan",
    damage_scale_unit: "Satuan kerusakan", canonical_category: "Kategori", canonical_group: "Kelompok",
    canonical_item: "Barang baku"
  };
  var KIND = { "RN Community Report": "Laporan warga", "RN Logistic Need": "Kebutuhan logistik" };
  var esc = (window.RNUI && RNUI.esc) || function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  function card(s) {
    var p = s.payload || {}, proposed = p.proposed || {}, current = p.current || {};
    var rows = Object.keys(proposed).map(function (k) {
      var was = current[k];
      return "<li><b>" + esc(LABEL[k] || k) + ":</b> " + esc(proposed[k]) +
        (was != null && was !== "" ? " <small>(sekarang: " + esc(was) + ")</small>" : "") + "</li>";
    }).join("") || "<li>Tidak ada perubahan yang diusulkan.</li>";
    return '<article class="event-card" data-ai-sug="' + esc(s.name) + '">' +
      "<header><b>" + esc(KIND[s.ref_doctype] || s.ref_doctype) + "</b> · " + esc(s.ref_name) +
      " <small>— saran AI (" + esc(s.provider || "") + (p.confidence != null ? ", yakin " + esc(p.confidence) + "%" : "") + ")</small></header>" +
      (p.raw_text ? "<p><i>" + esc(p.raw_text) + "</i></p>" : "") +
      "<ul>" + rows + "</ul>" +
      '<div class="form-actions"><button type="button" class="btn primary" data-ai-decide="accepted">Terima</button> ' +
      '<button type="button" class="btn" data-ai-decide="rejected">Tolak</button> ' +
      '<span class="form-message" data-ai-msg></span></div></article>';
  }

  function load(panel) {
    var list = panel.querySelector("[data-ai-list]");
    var kinds = Object.keys(KIND);
    Promise.all(kinds.map(function (k) {
      return RN_FRAPPE.call("rescue_net.api_ai.list_ai_suggestions", { ref_doctype: k }).catch(function () { return []; });
    })).then(function (parts) {
      var all = [].concat.apply([], parts);
      panel.hidden = !all.length;
      list.innerHTML = all.map(card).join("");
    });
  }

  function mount() {
    var anchor = document.querySelector(".community-operator-panel") || document.querySelector("main") || document.body;
    var panel = document.createElement("section");
    panel.className = "public-report-panel";
    panel.setAttribute("data-ai-suggestions", "");
    panel.hidden = true;
    panel.innerHTML = '<div class="panel-header"><div><h3>Saran AI menunggu keputusan</h3>' +
      "<p>AI hanya mengusulkan. Data berubah setelah Anda menerima; menolak tidak mengubah apa pun.</p></div></div>" +
      '<div class="event-list" data-ai-list></div>';
    if (anchor.matches("main")) anchor.insertBefore(panel, anchor.firstChild);
    else anchor.parentNode.insertBefore(panel, anchor);
    panel.addEventListener("click", function (e) {
      var b = e.target.closest("[data-ai-decide]");
      if (!b) return;
      var cardEl = b.closest("[data-ai-sug]"), msg = cardEl.querySelector("[data-ai-msg]");
      b.disabled = true;
      RN_FRAPPE.call("rescue_net.api_ai.decide_ai_suggestion",
        { suggestion: cardEl.getAttribute("data-ai-sug"), decision: b.getAttribute("data-ai-decide") },
        { method: "POST" })
        .then(function () { load(panel); document.dispatchEvent(new CustomEvent("rn:ai-decided")); })
        .catch(function (err) { b.disabled = false; msg.textContent = err.message || "Gagal."; });
    });
    load(panel);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
})();
