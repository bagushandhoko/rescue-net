/* Guest-safe armada discovery for the selected disaster and receiving posko. */
(function () {
  "use strict";
  var host = document.getElementById("kbArmadaList");
  var picker = document.querySelector("[data-disaster-picker]");
  if (!host || !picker || !window.RN_FRAPPE) return;
  var q = new URLSearchParams(location.search), sequence = 0;
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function norm(v) { return String(v || "").normalize("NFKC").toLocaleLowerCase("id-ID").replace(/\s+/g, " ").trim(); }
  function related(a, id, name) {
    if (!id) return false;
    if ((a.posko || a.coordination_posko) === id) return true;
    var route = norm(a.route || a.route_destination);
    return [id, name].some(function (v) { v = norm(v); return v && route.includes(v); });
  }
  function card(a, event) {
    var capacity = [];
    if (a.left_kg != null) capacity.push(Number(a.left_kg).toLocaleString("id-ID") + " kg");
    if (a.left_m3 != null) capacity.push(Number(a.left_m3).toLocaleString("id-ID") + " m³");
    var url = new URL("posko-distribusi.html", location.href);
    url.search = new URLSearchParams({ id: a.posko || a.coordination_posko || "", event: event, armada: a.name });
    return '<article class="panel" style="min-width:0;overflow-wrap:anywhere"><h4>' + esc(a.title || a.name) + '</h4>' +
      '<p>' + esc(a.type_label || a.type || "—") + ' · ' + esc(a.status_label || "") + '</p>' +
      '<p>Rute / tujuan: ' + esc(a.route || a.route_destination || "Belum diisi") + '</p>' +
      '<p>Jadwal: ' + esc(a.departure || "Fleksibel") + (a.eta ? ' · Tiba: ' + esc(a.eta) : '') + '</p>' +
      '<p>Sisa kapasitas: ' + esc(capacity.join(" · ") || "Belum diisi") + '</p>' +
      '<p>Posko pengelola: ' + esc(a.posko_title || a.posko || "Belum diisi") + '</p>' +
      ((a.posko || a.coordination_posko) ? '<a class="btn primary" style="white-space:normal;max-width:100%;box-sizing:border-box" href="' + esc(url.pathname + url.search) + '">Booking ruang muat</a>' : '') + '</article>';
  }
  async function load(initial) {
    var request = ++sequence;
    var event = ((initial === true && q.get("event")) || picker.value || q.get("event") || "").replace(/^disaster_events:/, "");
    if (!event) { host.textContent = "Pilih bencana untuk melihat armada."; return; }
    host.textContent = "Memuat armada…";
    try {
      var result = await window.RN_FRAPPE.call("rescue_net.api_armada.armada_finder", { disaster_event: event }, { method: "GET" });
      var id = q.get("posko") || "";
      var name = q.get("target_node_name") || "";
      // Resolve the title for older links that only carry a posko ID.
      if (id && !name) {
        try {
          var points = await window.RN_FRAPPE.call("rescue_net.api_control_centre.event_poskos", { disaster_event: event }, { method: "GET" });
          var posko = (points.points || []).find(function (p) { return (p.posko_id || p.id) === id; });
          name = posko && (posko.name || posko.title) || "";
        } catch (e) { /* Exact coordination-posko matching remains available. */ }
      }
      if (request !== sequence) return;
      var rows = (result.rows || []).slice().sort(function (a, b) {
        return Number(related(b, id, name)) - Number(related(a, id, name));
      });
      host.innerHTML = rows.length ? rows.map(function (a) { return card(a, event); }).join("") : '<p>Belum ada armada untuk bencana ini.</p>';
    } catch (e) {
      if (request === sequence) host.textContent = "Daftar armada gagal dimuat. Silakan coba lagi.";
    }
  }
  picker.addEventListener("change", load);
  document.getElementById("kbArmadaRetry").addEventListener("click", load);
  load(true);
})();
