(function () {
  "use strict";

  const VALID_TABS = ["konsolidasi", "duplikasi", "sync"];

  function tabFromHash() {
    const hash = (window.location.hash || "").replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const tab = params.get("tab");
    return VALID_TABS.includes(tab) ? tab : null;
  }

  function showTab(tabs, panels, name) {
    tabs.forEach(btn => {
      const active = btn.getAttribute("data-tab") === name;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    panels.forEach(panel => {
      panel.hidden = panel.getAttribute("data-tab-panel") !== name;
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const nav = document.getElementById("syncKonsolTabs");
    if (!nav) return;

    const tabs = Array.from(nav.querySelectorAll("[data-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
    if (!tabs.length || !panels.length) return;

    tabs.forEach(btn => {
      btn.addEventListener("click", () => {
        const name = btn.getAttribute("data-tab");
        showTab(tabs, panels, name);
        const url = new URL(window.location.href);
        url.hash = `tab=${name}`;
        history.replaceState(null, "", url.toString());
      });
    });

    showTab(tabs, panels, tabFromHash() || "konsolidasi");
  });
})();
