/* ============================================================
 * lacak-logistik.js — public shipment tracker for Rescue-Net.
 * Opened from a printed QR (management-distribusi.html). No login.
 * Reads ?flow=<name> or ?trace=RN-XXXXXXXX, calls
 * rescue_net.api_control_centre.flow_trace (allow_guest).
 * ============================================================ */
(function () {
  "use strict";

  function $(sel) { return document.querySelector(sel); }

  function esc(s) { return window.RNUI.esc(s); }

  function fmtDateTime(v) {
    if (!v) return "";
    var d = new Date(String(v).replace(" ", "T"));
    if (isNaN(d.getTime())) return String(v);
    return d.toLocaleString("id-ID", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  function statusClass(p) {
    if (p.cancelled) return "cancel";
    if (p.status === "received" || p.status === "received_verified" || p.status === "stock_transferred") return "done";
    return "transit";
  }

  function row(label, value) {
    if (!value) return "";
    return '<div class="ll-row"><span>' + esc(label) + "</span><b>" + esc(value) + "</b></div>";
  }

  function render(p) {
    var steps = (p.steps || []).map(function (s) {
      var cls = (s.done ? " done" : "") + (s.current ? " current" : "");
      return '<li class="ll-step' + cls + '"><h4>' + esc(s.label) + "</h4>" +
        (s.at ? "<time>" + esc(fmtDateTime(s.at)) + "</time>" : "") + "</li>";
    }).join("");

    var html =
      '<div class="ll-card">' +
        '<div class="ll-trace">' + esc(p.trace || "") + "</div>" +
        '<span class="ll-status ' + statusClass(p) + '">' + esc(p.status_label || "-") + "</span>" +
        (p.cancelled && p.cancelled_at
          ? '<p class="ll-muted" style="margin:8px 0 0">Dibatalkan ' + esc(fmtDateTime(p.cancelled_at)) + "</p>"
          : "") +
      "</div>" +
      '<div class="ll-card">' +
        row("Barang", p.item) +
        row("Jumlah", p.quantity_text) +
        row("Rute", p.route) +
        row("Transportasi", p.transport) +
        row("Perkiraan tiba", p.eta_final) +
        row("Diterima", p.received_text) +
        row("Catatan terima", p.receipt_note) +
        (p.updated_at ? row("Diperbarui", fmtDateTime(p.updated_at)) : "") +
      "</div>" +
      packageCard(p) +
      legsCard(p) +
      '<div class="ll-card"><ul class="ll-timeline">' + steps + "</ul></div>";

    $("#llBody").innerHTML = html;
    $("#llFindCard").hidden = false;
  }

  // owner 2026-11-09: estafet — urutan armada yang membawa kiriman + serah-terima tercatat (mutasi pergerakan)
  function legsCard(p) {
    var legs = p.legs || [], hs = p.handovers || [];
    if (legs.length < 2 && !hs.length) return "";
    var st = { requested: "menunggu konfirmasi", confirmed: "terkonfirmasi", completed: "selesai" };
    return '<div class="ll-card"><b>Perjalanan kiriman' + (legs.length > 1 ? " (" + legs.length + " kaki" + (legs.some(function (l) { return l.leg === "relay"; }) ? ", estafet" : "") + ")" : "") + "</b>" +
      legs.map(function (l) {
        return row(l.no + ". " + l.leg_label, l.armada + " — " + l.posko + " · " + l.from + " → " + l.to +
          (l.berangkat ? " · berangkat " + fmtDateTime(l.berangkat) : "") + " · " + (st[l.booking_status] || l.booking_status));
      }).join("") +
      (hs.length ? '<p class="ll-muted" style="margin:10px 0 4px">Serah-terima tercatat</p>' +
        hs.map(function (h) { return row(fmtDateTime(h.waktu), h.jenis + " · " + h.posko); }).join("") : "") +
      "</div>";
  }

  // paket (owner 2026-10-26): every item travelling under this resi
  function packageCard(p) {
    var k = p.package;
    if (!k || !k.items || k.items.length < 2) return "";
    return '<div class="ll-card"><b>Isi paket (' + k.items.length + " barang)</b>" +
      (k.is_main ? "" : '<p class="ll-muted" style="margin:4px 0 0">Barang ini bagian dari paket resi ' + esc(k.trace) + ".</p>") +
      k.items.map(function (i) { return row(i.item, i.quantity_text + " · " + i.status_label); }).join("") + "</div>";
  }

  function showError(text) {
    $("#llBody").innerHTML = '<div class="ll-card"><p class="ll-err">' + esc(text) + "</p>" +
      '<p class="ll-muted">Periksa kembali kode trace atau hubungi posko pengirim.</p></div>';
    $("#llFindCard").hidden = false;
  }

  async function load(params) {
    if (!window.RN_FRAPPE) { showError("Klien API belum siap."); return; }
    try {
      var res = await window.RN_FRAPPE.call(
        "rescue_net.api_control_centre.flow_trace", params
      );
      if (!res || !res.trace) { showError("Kiriman tidak ditemukan."); return; }
      render(res);
    } catch (err) {
      var m = String((err && err.message) || err || "");
      showError(/tidak ditemukan|not found|DoesNotExist/i.test(m)
        ? "Kiriman tidak ditemukan." : ("Gagal memuat: " + m));
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var q = new URLSearchParams(location.search);
    var flow = (q.get("flow") || "").trim();
    var trace = (q.get("trace") || q.get("t") || "").trim();

    if (flow) load({ flow: flow });
    else if (trace) load({ trace: trace });
    else {
      $("#llBody").innerHTML = '<p class="ll-muted">Masukkan kode trace kiriman untuk memantau statusnya.</p>';
      $("#llFindCard").hidden = false;
    }

    var btn = $("#llFindBtn"), input = $("#llFindInput");
    function go() {
      var v = (input.value || "").trim();
      if (v) location.search = "?trace=" + encodeURIComponent(v);
    }
    if (btn) btn.addEventListener("click", go);
    if (input) input.addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
  });
})();
