(function () {
  "use strict";

  const MOBILE_QUERY = "(max-width: 1023px)";

  function focusableEls(container) {
    return Array.from(
      container.querySelectorAll(
        'a[href], button:not([disabled]), summary, select, [tabindex]:not([tabindex="-1"])'
      )
    ).filter(el => el.offsetParent !== null);
  }

  const isHome = document.body.classList.contains("home-page");
  const prefix = isHome ? "" : "../";

  // Fallback links for pages that carry neither the operational sidebar nor
  // the public header (field pages opened from a QR / link: Scan, Kartu
  // Keluarga, Lacak Logistik, ...). Mirrors rn-public-header.js's list.
  function fallbackLinks() {
    let ev = "event-sim-001";
    try { ev = localStorage.getItem("rn_active_event") || ev; } catch (e) {}
    ev = String(ev).replace(/^disaster_events:/, "");
    const items = [
      ["Home", "index.html"],
      ["Bencana Aktif", "pages/bencana-aktif.html"],
      ["Control Centre", "pages/war-room.html?event=" + encodeURIComponent(ev)],
      ["Laporan Masyarakat", "pages/laporan-masyarakat.html"],
      ["Kirim Bantuan", "pages/kirim-bantuan.html"],
      ["Install App", "pages/install.html"],
      ["About Us", "index.html#tentang"],
      ["Login/registrasi", "pages/auth.html"]
    ];
    const nav = document.createElement("nav");
    nav.className = "rn-public-links";
    nav.setAttribute("aria-label", "Menu umum");
    items.forEach(([label, href]) => {
      const a = document.createElement("a");
      a.href = prefix + href;
      a.textContent = label;
      nav.appendChild(a);
    });
    return nav;
  }

  // Pages without the operational .sidebar get a standalone overlay panel
  // (hidden on desktop by CSS), so every page has the same mobile menu.
  function makeStandalonePanel() {
    const panel = document.createElement("aside");
    panel.className = "sidebar rn-drawer-panel";
    panel.setAttribute("aria-label", "Menu");
    const brand = document.createElement("div");
    brand.className = "brand";
    const img = document.createElement("img");
    img.className = "brand-logo";
    img.alt = "Rescue-Net";
    img.src = prefix + "assets/img/rn-logo-web.png";
    brand.appendChild(img);
    panel.appendChild(brand);
    document.body.appendChild(panel);
    document.body.classList.add("rn-drawer-standalone");
    return panel;
  }

  // "Bencana Aktif" section of the phone menu: each active disaster links to
  // war-room.html?event=<id> and becomes the remembered active event.
  function disasterSection() {
    // a closed group like "Posko": opens only when tapped
    const sec = document.createElement("details");
    sec.className = "rn-nav-v2-group rn-drawer-group rn-drawer-disasters";
    // the operational CSS gives the last group a bottom line; the Posko group
    // below already draws a top line -> no double line
    sec.style.setProperty("border-bottom", "0", "important");
    sec.setAttribute("data-rn-group", "bencana");
    const summary = document.createElement("summary");
    summary.className = "rn-nav-v2-summary";
    summary.innerHTML = '<span>Bencana Aktif</span><span class="rn-nav-v2-chevron" aria-hidden="true">⌄</span>';
    const list = document.createElement("nav");
    list.className = "rn-nav-v2-children rn-drawer-disaster-list";
    list.setAttribute("aria-label", "Control Centre per bencana aktif");
    sec.appendChild(summary);
    sec.appendChild(list);
    let current = "";
    try { current = String(localStorage.getItem("rn_active_event") || "").replace(/^disaster_events:/, ""); } catch (e) {}
    const CACHE = "rn_active_disasters_menu_v1";

    function fill(rows) {
      list.innerHTML = "";
      const all = document.createElement("a");
      all.href = prefix + "pages/bencana-aktif.html";
      all.className = "rn-nav-v2-link rn-drawer-disaster rn-drawer-all";
      all.textContent = "Semua bencana aktif (peta & daftar)";
      list.appendChild(all);
      rows.forEach(row => {
        const id = String(row.legacy_id || row.id || row.name || "").replace(/^disaster_events:/, "");
        if (!id) return;
        const a = document.createElement("a");
        a.href = prefix + "pages/war-room.html?event=" + encodeURIComponent(id);
        const sev = String(row.severity || "").toLowerCase();
        a.className = "rn-nav-v2-link rn-drawer-disaster" + (id === current ? " is-current" : "");
        const dot = document.createElement("i");
        dot.className = "rn-sev-dot " + (/(critical|kritis)/.test(sev) ? "crit" : /(high|tinggi|urgent)/.test(sev) ? "high" : "mid");
        dot.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.textContent = row.title || id;
        a.appendChild(dot);
        a.appendChild(label);
        a.addEventListener("click", () => { try { localStorage.setItem("rn_active_event", id); } catch (e) {} });
        list.appendChild(a);
      });
    }

    fill([]);                                   // "Semua bencana aktif" even before the list arrives
    // filled at once from the last list this phone saw (also offline) ...
    try { const cached = JSON.parse(localStorage.getItem(CACHE) || "[]"); if (cached.length) fill(cached); } catch (e) {}
    // ... and refreshed from the server
    fetch(location.origin + "/rescue-net-frappe/api/method/rescue_net.api_ai.public_active_disasters", { credentials: "omit" })
      .then(r => r.json())
      .then(payload => {
        const rows = ((payload && payload.message) || []).map(r => ({
          legacy_id: r.legacy_id, id: r.id, name: r.name, title: r.title, severity: r.severity
        }));
        if (!rows.length) return;
        try { localStorage.setItem(CACHE, JSON.stringify(rows)); } catch (e) {}
        fill(rows);
      })
      .catch(() => { /* offline: keep the cached list */ });
    return sec;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = src; el.onload = resolve; el.onerror = reject;
      document.head.appendChild(el);
    });
  }

  async function mountOperationalGroups(container) {
    if (container.querySelector(".rn-drawer-ops")) return;
    try {
      if (!window.RNIcon) await loadScript(prefix + "assets/js/rn-icons.js?v=kpiicon-20260904").catch(() => {});
      if (!window.RNNav) await loadScript(prefix + "assets/js/rn-navigation-v2.js?v=opsgroups-20261019");
    } catch (e) { return; }
    if (!window.RNNav || container.querySelector(".rn-drawer-ops")) return;
    const wrap = document.createElement("div");
    wrap.className = "rn-drawer-ops";
    // CONFIG hrefs are relative to pages/: Home (root) needs the folder
    wrap.innerHTML = window.RNNav.groupsHtml(isHome ? "pages/" : "");
    container.appendChild(wrap);
    if (window.RNIconFill) window.RNIconFill(wrap);
    const sidebar = container.closest(".sidebar") || document;
    sidebar.querySelectorAll("details.rn-nav-v2-group").forEach(g => {
      g.open = false;
      if (g.dataset.rnDrawerAccordion) return;
      g.dataset.rnDrawerAccordion = "1";
      g.addEventListener("toggle", () => {
        if (!g.open) return;
        sidebar.querySelectorAll("details.rn-nav-v2-group").forEach(o => { if (o !== g) o.open = false; });
      });
    });
  }

  function init() {
    if (document.body.classList.contains("mockup-viewer")) return;

    const sidebar = document.querySelector(".sidebar") || makeStandalonePanel();

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
    const sourceTitle = isHome ? null :
      document.querySelector("[data-rn-mobile-title]") ||
      document.querySelector(".topbar .rn-page-mobile-title") ||
      document.querySelector(".topbar h2") ||
      document.querySelector(".topbar h1") ||
      document.querySelector("main h1, h1");
    const readTitle = () => {
      const src = sourceTitle && (sourceTitle.getAttribute("data-rn-mobile-title") || sourceTitle.textContent);
      return src ? src.replace(/\s+/g, " ").trim() : "Rescue-Net";
    };
    title.textContent = readTitle();
    // pages fill their title after loading data ("Memuat…" -> real name)
    if (sourceTitle && window.MutationObserver) {
      new MutationObserver(() => { title.textContent = readTitle(); })
        .observe(sourceTitle, { childList: true, subtree: true, characterData: true });
    }

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

    /* ---------------------------------------------------------------
       Single-menu fold: on mobile the public header (brand bar +
       public links + event picker + login) used to render as a SECOND
       sticky bar with its OWN hamburger, on top of this drawer's bar —
       two stacked bars, two menus. Instead fold the public header's
       links + account/event controls into THIS one drawer, and hide the
       public bar (CSS). Reversible so a resize back to desktop restores
       the original top bar untouched.
       --------------------------------------------------------------- */
    // Home keeps its own hand-built .welcome-nav; other pages use the
    // .rn-public-header built by rn-public-header.js.
    const publicHeader =
      document.querySelector(".rn-public-header") ||
      document.querySelector(".welcome-nav");
    let folded = false;
    let foldWrap = null;
    let movedLinks = null;
    let movedActions = null;
    let toggleAnchor = null;
    let hiddenLinks = [];

    function foldPublicIntoDrawer() {
      if (folded) return;

      const links = publicHeader
        ? publicHeader.querySelector(".rn-public-links, .welcome-links")
        : (movedLinks || fallbackLinks());
      const actions = publicHeader && publicHeader.querySelector(".rn-public-actions");
      toggleAnchor = publicHeader && publicHeader.querySelector(".rn-public-toggle, .welcome-menu-toggle");

      foldWrap = document.createElement("div");
      foldWrap.className = "rn-drawer-public";

      // Account first (login / who am I). The event picker is hidden in the
      // phone menu by CSS: the "Bencana Aktif" group below replaces it.
      if (actions) {
        movedActions = actions;
        foldWrap.appendChild(actions);
      }

      // Public links as a labelled section, matching the operational groups.
      if (links) {
        movedLinks = links;
        const sec = document.createElement("div");
        sec.className = "rn-drawer-public-links";
        sec.appendChild(links);
        foldWrap.appendChild(sec);
      }

      // "Bencana Aktif" becomes the group below -> hide the plain link (inline
      // !important: an operational rule forces every drawer link visible)
      hiddenLinks = Array.from(foldWrap.querySelectorAll('a[href$="bencana-aktif.html"]'))
        .filter(a => !a.closest(".rn-drawer-disasters"));
      hiddenLinks.forEach(a => a.style.setProperty("display", "none", "important"));

      // Groups with sub-menus, all closed until tapped (owner 2026-10-19):
      // Bencana Aktif (each disaster -> its Control Centre), then the
      // operational groups (Posko, Donasi, Modul, Pengaturan) below.
      foldWrap.appendChild(disasterSection());

      // pages without the operational sidebar get the same groups (Posko,
      // Donasi, Modul, Pengaturan) in the phone menu (owner 2026-10-19)
      if (!sidebar.querySelector("nav.rn-nav-v2")) mountOperationalGroups(foldWrap);

      // Place just under the drawer brand, above the operational nav.
      const brand = sidebar.querySelector(".brand");
      if (brand && brand.nextSibling) {
        sidebar.insertBefore(foldWrap, brand.nextSibling);
      } else if (brand) {
        sidebar.appendChild(foldWrap);
      } else {
        sidebar.insertBefore(foldWrap, sidebar.firstChild);
      }

      document.body.classList.add("rn-drawer-folded");
      folded = true;
      collapseGroups();
    }

    // phone menu: every group closed, and only one open at a time
    function collapseGroups() {
      const groups = Array.from(sidebar.querySelectorAll("details.rn-nav-v2-group"));
      groups.forEach(g => {
        g.open = false;
        if (g.dataset.rnDrawerAccordion) return;
        g.dataset.rnDrawerAccordion = "1";
        g.addEventListener("toggle", () => {
          if (!g.open) return;
          sidebar.querySelectorAll("details.rn-nav-v2-group").forEach(o => { if (o !== g) o.open = false; });
        });
      });
    }

    function unfoldPublicFromDrawer() {
      if (!folded) return;
      hiddenLinks.forEach(a => a.style.removeProperty("display"));
      hiddenLinks = [];
      if (!publicHeader) {
        // Fallback links only live in the drawer; keep them for re-folding.
        if (foldWrap && foldWrap.parentNode) foldWrap.parentNode.removeChild(foldWrap);
        foldWrap = null;
        document.body.classList.remove("rn-drawer-folded");
        folded = false;
        return;
      }

      // Restore original order: links, then actions, then the toggle.
      if (movedLinks) {
        publicHeader.insertBefore(movedLinks, toggleAnchor || null);
      }
      if (movedActions) {
        publicHeader.insertBefore(movedActions, toggleAnchor || null);
      }
      if (foldWrap && foldWrap.parentNode) foldWrap.parentNode.removeChild(foldWrap);

      foldWrap = null;
      document.body.classList.remove("rn-drawer-folded");
      folded = false;
    }

    function applyMode() {
      if (window.matchMedia(MOBILE_QUERY).matches) {
        foldPublicIntoDrawer();
      } else {
        unfoldPublicFromDrawer();
      }
    }

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
      // A link closes the drawer; the event <select> and the group
      // accordions (<summary>) must not.
      if (e.target.closest("a[href]")) closeDrawer();
    });

    window.matchMedia(MOBILE_QUERY).addEventListener("change", e => {
      if (!e.matches) closeDrawer();
      applyMode();
    });

    // Fold now for the initial viewport.
    applyMode();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
