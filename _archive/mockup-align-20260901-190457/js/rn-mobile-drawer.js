(function () {
  "use strict";

  const MOBILE_QUERY = "(max-width: 1023px)";

  function focusableEls(container) {
    return Array.from(
      container.querySelectorAll(
        'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'
      )
    ).filter(el => el.offsetParent !== null);
  }

  function init() {
    if (document.body.classList.contains("home-page")) return;

    const sidebar = document.querySelector(".sidebar");
    if (!sidebar) return;

    if (!sidebar.id) sidebar.id = "rn-mobile-drawer-sidebar";

    const backdrop = document.createElement("div");
    backdrop.className = "rn-drawer-backdrop";
    backdrop.setAttribute("aria-hidden", "true");
    document.body.appendChild(backdrop);

    const topbar = document.createElement("div");
    topbar.className = "rn-drawer-topbar";

    const hamburger = document.createElement("button");
    hamburger.type = "button";
    hamburger.className = "rn-drawer-hamburger";
    hamburger.setAttribute("aria-label", "Buka menu navigasi");
    hamburger.setAttribute("aria-expanded", "false");
    hamburger.setAttribute("aria-controls", sidebar.id);
    hamburger.innerHTML = "<span></span><span></span><span></span>";

    const title = document.createElement("div");
    title.className = "rn-drawer-title";
    const sourceTitle =
      document.querySelector(".topbar .rn-page-mobile-title") ||
      document.querySelector(".topbar h2") ||
      document.querySelector(".topbar h1");
    title.textContent = sourceTitle ? sourceTitle.textContent.trim() : "Rescue-Net";

    const logoSrc =
      sidebar.querySelector(".brand-logo")?.getAttribute("src") ||
      sidebar.querySelector(".brand-mark img")?.getAttribute("src") ||
      "";

    topbar.appendChild(hamburger);
    topbar.appendChild(title);

    if (logoSrc) {
      const logo = document.createElement("img");
      logo.className = "rn-drawer-logo";
      logo.alt = "Rescue-Net";
      logo.src = logoSrc;
      topbar.appendChild(logo);
    }

    document.body.insertBefore(topbar, document.body.firstChild);

    let lastFocused = null;

    function onKeydown(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeDrawer();
        return;
      }
      if (e.key === "Tab") {
        const items = focusableEls(sidebar);
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    function openDrawer() {
      if (!window.matchMedia(MOBILE_QUERY).matches) return;
      lastFocused = document.activeElement;
      document.body.classList.add("rn-drawer-open");
      hamburger.setAttribute("aria-expanded", "true");
      document.addEventListener("keydown", onKeydown);
      const first = focusableEls(sidebar)[0];
      if (first) first.focus();
    }

    function closeDrawer() {
      if (!document.body.classList.contains("rn-drawer-open")) return;
      document.body.classList.remove("rn-drawer-open");
      hamburger.setAttribute("aria-expanded", "false");
      document.removeEventListener("keydown", onKeydown);
      if (lastFocused && typeof lastFocused.focus === "function") {
        lastFocused.focus();
      } else {
        hamburger.focus();
      }
    }

    hamburger.addEventListener("click", () => {
      if (document.body.classList.contains("rn-drawer-open")) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });

    backdrop.addEventListener("click", closeDrawer);

    sidebar.addEventListener("click", e => {
      if (e.target.closest("a[href]")) closeDrawer();
    });

    window.matchMedia(MOBILE_QUERY).addEventListener("change", e => {
      if (!e.matches) closeDrawer();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
