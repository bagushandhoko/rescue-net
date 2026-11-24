/* rn-doc-viewer.js (owner 2026-11-24: "tambahkan viewer thumbnail rab dan pdf spt foto")
 * - Thumbnail PDF: <span data-pdf-thumb="URL"> diisi gambar halaman 1 (pdf.js, dimuat saat dibutuhkan).
 * - Penampil layar penuh: klik elemen [data-doc-view] (href = berkas) membuka overlay; grup = [data-doc-group]
 *   yang sama, geser ‹ ›. Gambar: ketuk untuk perbesar 100%. PDF: semua halaman dirender berurutan (gulir).
 * pdf.js 3.11.174 dari cdnjs; bila gagal dimuat, PDF dibuka di tab baru. */
(function () {
  "use strict";
  if (window.RNDocViewer) return;
  var PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/";
  var libP = null, docCache = {};
  function lib() {
    if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
    if (!libP) libP = new Promise(function (ok, bad) {
      var s = document.createElement("script"); s.src = PDFJS + "pdf.min.js";
      s.onload = function () { window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS + "pdf.worker.min.js"; ok(window.pdfjsLib); };
      s.onerror = function () { libP = null; bad(new Error("pdf.js gagal dimuat")); };
      document.head.appendChild(s);
    });
    return libP;
  }
  function real(u) { return window.RN_FRAPPE && window.RN_FRAPPE.fileUrl ? window.RN_FRAPPE.fileUrl(u) : u; }
  function pdf(u) {
    u = real(u);
    if (!docCache[u]) docCache[u] = lib().then(function (L) { return L.getDocument({ url: u, withCredentials: true }).promise; });
    return docCache[u];
  }
  function renderPage(doc, n, width) {
    return doc.getPage(n).then(function (pg) {
      var v1 = pg.getViewport({ scale: 1 }), ratio = window.devicePixelRatio || 1;
      var vp = pg.getViewport({ scale: (width / v1.width) * ratio });
      var c = document.createElement("canvas"); c.width = vp.width; c.height = vp.height;
      c.style.width = width + "px"; c.style.height = (vp.height / ratio) + "px";
      return pg.render({ canvasContext: c.getContext("2d"), viewport: vp }).promise.then(function () { return c; });
    });
  }
  function thumbs(root) {
    (root || document).querySelectorAll("[data-pdf-thumb]:not([data-done])").forEach(function (el) {
      el.setAttribute("data-done", "1");
      pdf(el.getAttribute("data-pdf-thumb")).then(function (doc) {
        return renderPage(doc, 1, Math.max(160, el.clientWidth || 200)).then(function (c) {
          el.innerHTML = ""; c.className = "rn-dv-thumbcanvas"; el.appendChild(c);
          if (doc.numPages > 1) { var b = document.createElement("i"); b.className = "rn-dv-pages"; b.textContent = doc.numPages + " hal."; el.appendChild(b); }
        });
      }).catch(function () { /* biarkan ikon 📄 */ });
    });
  }

  var ov, stage, cap, openA, group = [], idx = 0, zoom = false;
  function build() {
    ov = document.createElement("div"); ov.className = "rn-dv"; ov.hidden = true;
    ov.innerHTML = '<div class="rn-dv-top"><span class="rn-dv-cap"></span><a class="rn-dv-open" target="_blank" rel="noopener">Buka di tab baru ↗</a>' +
      '<button type="button" class="rn-dv-x" aria-label="Tutup">×</button></div>' +
      '<button type="button" class="rn-dv-nav rn-dv-prev" aria-label="Sebelumnya">‹</button><button type="button" class="rn-dv-nav rn-dv-next" aria-label="Berikutnya">›</button>' +
      '<div class="rn-dv-stage"></div>';
    document.body.appendChild(ov);
    stage = ov.querySelector(".rn-dv-stage"); cap = ov.querySelector(".rn-dv-cap"); openA = ov.querySelector(".rn-dv-open");
    ov.querySelector(".rn-dv-x").onclick = close;
    ov.querySelector(".rn-dv-prev").onclick = function () { step(-1); };
    ov.querySelector(".rn-dv-next").onclick = function () { step(1); };
    document.addEventListener("keydown", function (e) {
      if (ov.hidden) return;
      if (e.key === "Escape") close(); else if (e.key === "ArrowLeft") step(-1); else if (e.key === "ArrowRight") step(1);
    });
  }
  function show() {
    var it = group[idx]; zoom = false;
    cap.textContent = (group.length > 1 ? (idx + 1) + "/" + group.length + " · " : "") + (it.caption || "");
    openA.href = real(it.url);
    ov.querySelector(".rn-dv-prev").hidden = ov.querySelector(".rn-dv-next").hidden = group.length < 2;
    stage.scrollTop = 0;
    if (!it.pdf) {
      stage.innerHTML = '<img class="rn-dv-img" alt="">';
      var img = stage.firstChild; img.src = real(it.url); img.alt = it.caption || "";
      img.onclick = function () { zoom = !zoom; img.classList.toggle("is-zoom", zoom); };
      return;
    }
    stage.innerHTML = '<p class="rn-dv-wait">Memuat PDF…</p>';
    var my = it;
    pdf(it.url).then(function (doc) {
      if (group[idx] !== my) return;
      stage.innerHTML = "";
      var w = Math.min(stage.clientWidth - 16, 1000), chain = Promise.resolve();
      for (var n = 1; n <= doc.numPages; n++) (function (n) {
        chain = chain.then(function () {
          if (group[idx] !== my) return;
          return renderPage(doc, n, w).then(function (c) { c.className = "rn-dv-page"; stage.appendChild(c); });
        });
      })(n);
    }).catch(function () { stage.innerHTML = '<p class="rn-dv-wait">PDF tidak bisa ditampilkan di sini. <a target="_blank" rel="noopener" href="' + real(it.url) + '">Buka di tab baru ↗</a></p>'; });
  }
  function step(d) { if (group.length > 1) { idx = (idx + d + group.length) % group.length; show(); } }
  function open(items, start) {
    if (!ov) build();
    group = items; idx = start || 0; ov.hidden = false; document.body.style.overflow = "hidden"; show();
  }
  function close() { ov.hidden = true; stage.innerHTML = ""; document.body.style.overflow = ""; }

  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-doc-view]");
    if (!el || e.target.closest("button")) return;
    e.preventDefault();
    var g = el.getAttribute("data-doc-group") || "";
    var els = [].slice.call(document.querySelectorAll('[data-doc-view][data-doc-group="' + g + '"]'));
    var items = els.map(function (n) {
      return { url: n.getAttribute("data-doc-view"), pdf: n.getAttribute("data-doc-pdf") === "1", caption: n.getAttribute("data-caption") || "" };
    });
    open(items, Math.max(0, els.indexOf(el)));
  });
  window.RNDocViewer = { open: open, thumbs: thumbs };
})();
