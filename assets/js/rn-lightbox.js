/* ============================================================
 * rn-lightbox.js — shared click-to-enlarge for evidence photos.
 * Same behaviour as the Control Centre "Bukti Lapangan" modal:
 * click a thumbnail → overlay with the enlarged image + caption +
 * "buka di tab baru". Works by click delegation on common evidence
 * thumbnail selectors, and programmatically via window.RNLightbox.open().
 * Zero dependencies. Load on any page that renders evidence thumbnails.
 * ============================================================ */
(function () {
  "use strict";
  if (window.RNLightbox) return;

  var SELECTORS = [
    "a.rn-bukti-thumb",
    "a.rn-ev-cell",
    ".rn-dp-evidence-strip a",
    ".rn-evidence-strip a",
    "[data-rn-lightbox]",
    "img[data-zoomable]",
  ].join(",");

  var overlay, imgEl, capEl, metaEl, openEl, group = [], idx = 0;

  function build() {
    overlay = document.createElement("div");
    overlay.className = "rn-lb";
    overlay.hidden = true;
    overlay.innerHTML =
      '<div class="rn-lb-backdrop" data-lb-close></div>' +
      '<div class="rn-lb-card" role="dialog" aria-modal="true" aria-label="Pratinjau bukti">' +
      '<button type="button" class="rn-lb-close" data-lb-close aria-label="Tutup">×</button>' +
      '<button type="button" class="rn-lb-nav rn-lb-prev" data-lb-prev aria-label="Sebelumnya">‹</button>' +
      '<button type="button" class="rn-lb-nav rn-lb-next" data-lb-next aria-label="Berikutnya">›</button>' +
      '<div class="rn-lb-stage"><img class="rn-lb-img" alt=""></div>' +
      '<div class="rn-lb-bar"><div class="rn-lb-cap"></div>' +
      '<div class="rn-lb-meta"></div>' +
      '<a class="rn-lb-open" target="_blank" rel="noopener">Buka di tab baru ↗</a></div>' +
      "</div>";
    document.body.appendChild(overlay);
    imgEl = overlay.querySelector(".rn-lb-img");
    capEl = overlay.querySelector(".rn-lb-cap");
    metaEl = overlay.querySelector(".rn-lb-meta");
    openEl = overlay.querySelector(".rn-lb-open");

    overlay.addEventListener("click", function (e) {
      if (e.target.closest("[data-lb-close]")) close();
      else if (e.target.closest("[data-lb-prev]")) step(-1);
      else if (e.target.closest("[data-lb-next]")) step(1);
    });
    document.addEventListener("keydown", function (e) {
      if (overlay.hidden) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "ArrowRight") step(1);
    });
  }

  var IMG_RE = /\.(png|jpe?g|gif|webp|avif|bmp|svg)(\?|#|$)/i;

  function itemFrom(el) {
    // el: an <a> or <img> or [data-rn-lightbox]
    if (el.hasAttribute && el.hasAttribute("data-no-lightbox")) return null;
    var a = el.tagName === "A" ? el : el.closest("a");
    if (a && a.hasAttribute("data-no-lightbox")) return null;
    var img = el.tagName === "IMG" ? el : (a ? a.querySelector("img") : null);
    var explicit = el.getAttribute("data-rn-lightbox");
    var src =
      explicit ||
      (a && a.getAttribute("href")) ||
      (img && img.getAttribute("src")) ||
      "";
    if (!src || src === "#" || /^javascript:/i.test(src)) return null;
    // prefer an actual image source
    if (!IMG_RE.test(src)) {
      var imgSrc = (img && (img.getAttribute("src") || img.src)) || "";
      if (IMG_RE.test(imgSrc)) src = imgSrc;
      else if (!explicit) return null; // no plausible image here — skip
    }
    var host = el.closest("tr, .rn-bukti-thumb, .rn-ev-thumb, li, article, .rn-dp-evidence-strip > *") || el;
    var cap =
      el.getAttribute("data-caption") ||
      (a && a.getAttribute("data-caption")) ||
      (img && (img.getAttribute("alt") || img.getAttribute("title"))) ||
      (host.querySelector && (host.querySelector("[data-ev-caption], .rn-ev-cap, b, strong, h4") || {}).textContent) ||
      "Bukti lapangan";
    var meta =
      el.getAttribute("data-meta") ||
      (host.querySelector && (host.querySelector("[data-ev-meta], .rn-ev-geo, small, .rn-muted") || {}).textContent) ||
      "";
    return { src: src, caption: String(cap).trim().replace(/\s+/g, " "), meta: String(meta).trim().replace(/\s+/g, " "), href: (a && a.getAttribute("href")) || src };
  }

  function render() {
    var it = group[idx] || {};
    imgEl.src = it.src || "";
    imgEl.alt = it.caption || "";
    capEl.textContent = it.caption || "";
    metaEl.textContent = it.meta || "";
    openEl.href = it.href || it.src || "#";
    var many = group.length > 1;
    overlay.querySelector(".rn-lb-prev").hidden = !many;
    overlay.querySelector(".rn-lb-next").hidden = !many;
  }

  function step(d) {
    if (group.length < 2) return;
    idx = (idx + d + group.length) % group.length;
    render();
  }

  function openList(items, start) {
    if (!items || !items.length) return;
    if (!overlay) build();
    group = items;
    idx = Math.max(0, Math.min(start || 0, items.length - 1));
    render();
    overlay.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function close() {
    if (!overlay) return;
    overlay.hidden = true;
    imgEl.src = "";
    document.body.style.overflow = "";
  }

  function onClick(e) {
    var el = e.target.closest(SELECTORS);
    if (!el) return;
    // ignore explicit opt-outs
    if (el.hasAttribute("data-no-lightbox")) return;
    var it = itemFrom(el);
    if (!it) return;
    e.preventDefault();
    // build the sibling group so ←/→ works within one evidence strip/table
    var scope = el.closest("tbody, .rn-bukti-grid, .rn-dp-evidence-strip, .rn-ev-table, .rn-evidence-strip, ul, .content-grid, .panel") || document;
    var sibs = [].slice.call(scope.querySelectorAll(SELECTORS)).filter(function (n) {
      return !n.hasAttribute("data-no-lightbox");
    });
    var items = [], start = 0;
    sibs.forEach(function (n) {
      var x = itemFrom(n);
      if (!x) return;
      if (n === el || (a2(n) === a2(el))) start = items.length;
      items.push(x);
    });
    if (!items.length) items = [it];
    openList(items, start);
  }
  function a2(n) { return n.tagName === "A" ? n : n.closest("a") || n; }

  window.RNLightbox = {
    open: function (opt) {
      if (typeof opt === "string") opt = { src: opt };
      openList([{ src: opt.src, caption: opt.caption || "", meta: opt.meta || "", href: opt.href || opt.src }], 0);
    },
    openList: openList,
    close: close,
  };

  document.addEventListener("click", onClick, true);
})();
