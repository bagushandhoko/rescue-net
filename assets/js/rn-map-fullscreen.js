// Tombol "Layar penuh" + "Tutup" otomatis untuk SEMUA peta Leaflet di situs.
// Peta dibuat oleh skrip halaman masing-masing; di sini hanya mengamati
// .leaflet-container baru lalu memasang tombol (tanpa mengubah kodenya).
(function () {
  "use strict";
  var CLS = "rn-mapfs";
  var openMap = null;

  function relayout() {
    // Leaflet menghitung ulang ukuran saat window di-resize
    [50, 250].forEach(function (ms) { setTimeout(function () { window.dispatchEvent(new Event("resize")); }, ms); });
  }

  function close() {
    if (!openMap) return;
    openMap.classList.remove(CLS);
    document.documentElement.classList.remove("rn-mapfs-lock");
    var b = openMap.querySelector(".rn-mapfs-btn"); if (b) { b.textContent = "⛶ Layar penuh"; b.setAttribute("aria-label", "Layar penuh"); }
    var x = openMap.querySelector(".rn-mapfs-close"); if (x) x.remove();
    openMap = null;
    relayout();
  }

  function open(el) {
    if (openMap) close();
    openMap = el;
    el.classList.add(CLS);
    document.documentElement.classList.add("rn-mapfs-lock");
    var x = document.createElement("button");
    x.type = "button"; x.className = "rn-mapfs-close"; x.textContent = "← Kembali / Tutup";
    x.setAttribute("aria-label", "Tutup peta layar penuh");
    x.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); close(); });
    el.appendChild(x);
    var b = el.querySelector(".rn-mapfs-btn"); if (b) b.textContent = "✕ Tutup";
    relayout();
  }

  function attach(el) {
    if (el.__rnFs) return;
    el.__rnFs = true;
    var b = document.createElement("button");
    b.type = "button"; b.className = "rn-mapfs-btn"; b.textContent = "⛶ Layar penuh";
    b.setAttribute("aria-label", "Layar penuh");
    ["click", "dblclick", "mousedown", "touchstart"].forEach(function (t) {
      b.addEventListener(t, function (e) { e.stopPropagation(); });
    });
    b.addEventListener("click", function (e) {
      e.preventDefault();
      if (el.classList.contains(CLS)) close(); else open(el);
    });
    el.appendChild(b);
  }

  function scan() { document.querySelectorAll(".leaflet-container").forEach(attach); }

  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
  scan();
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("load", scan);
})();
