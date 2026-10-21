/* ============================================================
 * rn-kpi-go.js — make static KPI cards clickable.
 *   <div class="kpi-card rn-kpi-clickable" data-go="#someId" role="button" tabindex="0">
 * Click / Enter / Space scrolls to the panel holding #someId (opening a
 * closed <details> around it). For pages that have no own KPI handler
 * (posko-detail and posko-medis-detail wire their own).
 * ============================================================ */
(function () {
  "use strict";
  function go(card) {
    var el = document.querySelector(card.getAttribute("data-go"));
    if (!el) return;
    var d = el.closest("details");
    if (d && !d.open) d.open = true;
    (el.closest(".panel") || el).scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function wire() {
    document.querySelectorAll(".kpi-card[data-go]:not([data-go-wired])").forEach(function (card) {
      card.setAttribute("data-go-wired", "1");
      card.addEventListener("click", function () { go(card); });
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(card); }
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
