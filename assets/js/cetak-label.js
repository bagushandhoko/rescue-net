/* Cetak label kiriman (owner 2026-10-25): pages/cetak-label.html?flow=<id>[&flow=<id>…]
 * Satu label per koli: QR (tautan Lacak Logistik + kode trace) dan barcode
 * Code128 berisi kode trace RN-XXXXXXXX, supaya terbaca kamera HP biasa
 * (Pindai Barcode / QR) maupun alat scan barcode. Data dari
 * rescue_net.api_control_centre.flow_trace (aman untuk tamu). */
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return window.RNUI ? window.RNUI.esc(s) : String(s == null ? "" : s); };
  var FLOWS = [];

  function lacakUrl(trace) {
    return location.origin + "/rescue-net/pages/lacak-logistik.html?trace=" + encodeURIComponent(trace);
  }

  function render() {
    var koli = Math.max(1, Math.min(200, parseInt($("#clKoli").value, 10) || 1));
    var sheet = $("#clSheet");
    if (!FLOWS.length) { sheet.innerHTML = "<p>Tidak ada kiriman untuk dicetak.</p>"; return; }
    var html = [];
    FLOWS.forEach(function (f, fi) {
      for (var k = 1; k <= koli; k++) {
        html.push(
          '<div class="cl-label">' +
            '<div class="cl-top"><span>RESCUE-NET · KIRIMAN BANTUAN</span><span>Koli ' + k + "/" + koli + "</span></div>" +
            '<div class="cl-body"><div class="cl-qr" id="clQr' + fi + "_" + k + '"></div>' +
              "<div><div class=\"cl-item\">" + esc(f.item) + '</div><div class="cl-qty">' + esc(f.quantity_text) + "</div>" +
              '<div class="cl-route"><b>Dari:</b> ' + esc(f.source_posko || "-") + "<br><b>Ke:</b> " + esc(f.destination_posko || "-") + "</div></div></div>" +
            '<div class="cl-bar"><svg id="clBar' + fi + "_" + k + '"></svg></div>' +
            '<div class="cl-trace">' + esc(f.trace) + "</div>" +
            '<div class="cl-foot"><span>Pindai untuk serah-terima &amp; lacak</span><span>' + esc(f.transport && f.transport !== "-" ? f.transport : "") + "</span></div>" +
          "</div>");
      }
    });
    sheet.innerHTML = html.join("");
    FLOWS.forEach(function (f, fi) {
      for (var k = 1; k <= koli; k++) {
        if (typeof QRCode === "function") {
          new QRCode(document.getElementById("clQr" + fi + "_" + k),
            { text: lacakUrl(f.trace), width: 112, height: 112, correctLevel: QRCode.CorrectLevel.M });
        }
        if (typeof JsBarcode === "function") {
          JsBarcode("#clBar" + fi + "_" + k, f.trace, { format: "CODE128", displayValue: false, margin: 0, height: 54, width: 2 });
        }
      }
    });
  }

  async function boot() {
    var qs = new URLSearchParams(location.search);
    var ids = qs.getAll("flow").filter(Boolean);
    var traces = qs.getAll("trace").filter(Boolean);
    if (qs.get("koli")) $("#clKoli").value = qs.get("koli");
    if (!ids.length && !traces.length) { $("#clSheet").innerHTML = "<p>Buka halaman ini dari tombol <b>Cetak label</b> di daftar Barang Keluar.</p>"; return; }
    var calls = ids.map(function (id) { return { flow: id }; }).concat(traces.map(function (t) { return { trace: t }; }));
    for (var i = 0; i < calls.length; i++) {
      try {
        var r = await window.RN_FRAPPE.call("rescue_net.api_control_centre.flow_trace", calls[i]);
        if (r && r.trace) FLOWS.push(r);
      } catch (e) {
        $("#clMsg").textContent = "Sebagian kiriman tidak ditemukan: " + ((e && e.message) || e);
      }
    }
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("#clKoli").addEventListener("input", render);
    $("#clPrint").addEventListener("click", function () { window.print(); });
    boot();
  });
})();
