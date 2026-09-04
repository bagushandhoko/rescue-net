(function () {
  "use strict";

  const CONFIG = {
    version: "2.1.0",

    posko: [
      {
        label: "Dashboard Posko",
        href: "organisasi-posko.html"
      },
      {
        label: "Koordinasi Organisasi",
        href: "koordinasi-organisasi.html?event=event-sim-001"
      },
      {
        label: "Registrasi & Verifikasi Posko",
        href: "registrasi-posko.html?event=event-sim-001"
      },
      {
        label: "Posko Detail",
        href: "posko-detail.html?id=posko-sim-logistik"
      },
      {
        label: "Posko Logistik",
        href: "posko-logistik.html"
      },
      {
        label: "Posko Distribusi",
        href: "posko-distribusi.html?event=event-sim-001"
      },
      {
        label: "Posko Relawan",
        href: "management-relawan.html"
      },
      {
        label: "Posko Alat Kerja",
        href: "alat-kerja.html?event=event-sim-001"
      },
      {
        label: "Posko Alat Komunikasi",
        href: "alat-komunikasi.html?event=event-sim-001"
      },
      {
        label: "Posko Medis",
        href: "posko-medis-detail.html?id=posko-sim-medis"
      },
      {
        label: "Posko Shelter",
        href: "shelter-detail.html?id=posko-sim-shelter"
      },
      {
        label: "Posko Dapur Umum",
        href: "dapur-umum.html?id=posko-sim-dapur"
      },
      {
        label: "Posko Resource",
        href: "resource-profile.html?event=event-sim-001"
      },
      {
        label: "Posko Evidence",
        href: "evidence.html?event=event-sim-001"
      },
      {
        label: "Posko Recovery",
        href: "recovery-reconstruction.html?event=event-sim-001"
      },
      {
        label: "Perencanaan Pengungsi",
        href: "perencanaan-pengungsi.html?event=event-sim-001"
      }
    ],

    modules: [
      {
        label: "Manajemen Distribusi",
        href: "management-distribusi.html"
      },
      {
        label: "Map",
        href: "map.html?event=event-sim-001"
      },
      {
        label: "Peta Nasional",
        href: "peta-nasional.html"
      },
      {
        label: "Organisasi",
        href: "organisasi-posko.html"
      },
      {
        label: "Search & Found",
        href: "search-found.html"
      },
      {
        label: "Program Khusus",
        href: "program-khusus.html"
      },
      {
        label: "Donor Program",
        href: "donor-program.html"
      },
      {
        label: "Pengadaan & Tender",
        href: "pengadaan-tender.html?event=event-sim-001"
      },
      {
        label: "Verification",
        href: "verification-approval.html"
      },
      {
        label: "Jaringan Verifikator",
        href: "verifikator.html"
      },
      {
        label: "Masukan Masyarakat",
        href: "masukan-masyarakat.html?event=event-sim-001"
      },
      {
        label: "AI Analyst",
        href: "ai-analyst.html?event=event-sim-001"
      },
      {
        label: "AI Settings",
        href: "ai-settings.html"
      },
      {
        label: "Sync Console",
        href: "sync-console.html"
      },
      {
        label: "Contact Directory",
        href: "contact-directory.html"
      }
    ]
  };

  const OPERATIONAL_LINKS = [
    "posko-detail.html",
    "posko-logistik.html",
    "management-distribusi.html",
    "management-relawan.html",
    "dapur-umum.html",
    "posko-medis-detail.html",
    "shelter-detail.html",
    "alat-kerja.html",
    "resource-profile.html",
    "evidence.html"
  ];

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function currentFile() {
    const pathname = window.location.pathname;
    return pathname.substring(pathname.lastIndexOf("/") + 1) || "index.html";
  }

  function hrefFile(href) {
    return String(href || "")
      .split("?")[0]
      .split("#")[0]
      .split("/")
      .pop();
  }

  function isActive(href) {
    return hrefFile(href) === currentFile();
  }

  function linkHtml(item, child) {
    const active = isActive(item.href);
    const classes = [
      "rn-nav-v2-link",
      child ? "rn-nav-v2-child" : "",
      active ? "active" : ""
    ].filter(Boolean).join(" ");

    return `
      <a
        class="${classes}"
        href="${escapeHtml(item.href)}"
        ${active ? 'aria-current="page"' : ""}
      >${escapeHtml(item.label)}</a>
    `;
  }

  function findOperationalNavigation() {
    const navs = Array.from(document.querySelectorAll("nav"));

    const excluded = nav =>
      nav.classList.contains("rn-public-links") ||
      nav.classList.contains("welcome-links") ||
      nav.closest(".rn-public-header") ||
      nav.closest(".welcome-nav");

    let best = null;
    let bestScore = 0;

    for (const nav of navs) {
      if (excluded(nav)) continue;

      const hrefs = Array.from(nav.querySelectorAll("a[href]"))
        .map(anchor => anchor.getAttribute("href") || "");

      const score = OPERATIONAL_LINKS.reduce((total, fragment) => {
        return total + (hrefs.some(href => href.includes(fragment)) ? 1 : 0);
      }, 0);

      if (score > bestScore) {
        best = nav;
        bestScore = score;
      }
    }

    return bestScore >= 3 ? best : null;
  }

  function groupHtml(label, items, groupId, forceOpen) {
    const active = forceOpen || items.some(item => isActive(item.href));

    return `
      <details class="rn-nav-v2-group" data-rn-group="${groupId}" ${active ? "open" : ""}>
        <summary class="rn-nav-v2-summary">
          <span>${escapeHtml(label)}</span>
          <span class="rn-nav-v2-chevron" aria-hidden="true">⌄</span>
        </summary>

        <div class="rn-nav-v2-children">
          ${items.map(item => linkHtml(item, true)).join("")}
        </div>
      </details>
    `;
  }

  // Accordion: only one group open at a time. Idempotent per group.
  function wireAccordion(nav) {
    const groups = Array.from(nav.querySelectorAll(".rn-nav-v2-group"));
    groups.forEach(group => {
      if (group.dataset.rnAccordionWired) return;
      group.dataset.rnAccordionWired = "1";
      group.addEventListener("toggle", () => {
        if (!group.open) return;
        groups.forEach(other => {
          if (other !== group) other.open = false;
        });
      });
    });
  }

  function renderNavigation(nav) {
    nav.classList.add("rn-nav-v2");
    nav.setAttribute("data-rn-navigation-version", CONFIG.version);
    nav.setAttribute("aria-label", "Navigasi operasional Rescue-Net");

    nav.innerHTML =
      groupHtml("Posko", CONFIG.posko, "posko") +
      groupHtml("Modul", CONFIG.modules, "modul");

    wireAccordion(nav);
  }

  /* ---- Top group: function switcher for a merged posko ---- */

  const FN_PAGES = {
    logistics: { label: "Logistik", href: "posko-logistik.html" },
    shelter: { label: "Shelter", href: "shelter-detail.html" },
    kitchen: { label: "Dapur Umum", href: "dapur-umum.html" }
  };

  function urlParam(names) {
    const params = new URLSearchParams(window.location.search);
    for (const n of names) {
      const v = params.get(n);
      if (v) return v;
    }
    return "";
  }

  function removePoskoFunctionGroup(nav) {
    const g = nav.querySelector('[data-rn-group="posko-fn"]');
    if (g) g.remove();
  }

  // The merged-posko switcher is an operator tool: a merged posko is run by
  // ONE logged-in user handling all 3 functions. Hide it for guests.
  function isLoggedIn() {
    try {
      const u = window.RN_SESSION && window.RN_SESSION.getUser();
      return !!(u && (u.user_id || u.username || u.user || u.email));
    } catch (e) {
      return false;
    }
  }

  async function mountPoskoFunctionGroup(nav) {
    if (!window.RN_FRAPPE) return;

    const poskoId = urlParam(["id", "posko"]);
    if (!poskoId) { removePoskoFunctionGroup(nav); return; }

    if (!isLoggedIn()) { removePoskoFunctionGroup(nav); return; }

    let info = null;
    try {
      info = await window.RN_FRAPPE.call(
        "rescue_net.api_control_centre.posko_functions",
        { posko: poskoId }
      );
    } catch (e) {
      return;
    }

    const fns = (info && info.functions || []).filter(f => FN_PAGES[f]);
    if (fns.length < 2) { // not a merged posko — nothing to switch
      removePoskoFunctionGroup(nav);
      return;
    }

    const event = urlParam(["event", "disaster_event_id"]);
    const q = id =>
      "?id=" + encodeURIComponent(id) +
      (event ? "&event=" + encodeURIComponent(event) : "");

    const items = fns.map(f => ({
      label: FN_PAGES[f].label,
      href: FN_PAGES[f].href + q(poskoId)
    }));

    let title = (info.title || poskoId).replace(/^\[SIMULASI\]\s*/i, "");
    if (title.length > 34) title = title.slice(0, 33) + "…";

    // Remove a stale copy (e.g. re-init) then prepend as the top group.
    removePoskoFunctionGroup(nav);
    nav.insertAdjacentHTML(
      "afterbegin",
      groupHtml("Posko: " + title, items, "posko-fn", true)
    );
    wireAccordion(nav);

    // The active function's page is current — keep only this group open.
    Array.from(nav.querySelectorAll(".rn-nav-v2-group")).forEach(g => {
      g.open = g.getAttribute("data-rn-group") === "posko-fn";
    });
  }

  function preserveEventContext(nav) {
    const params = new URLSearchParams(window.location.search);
    const eventId = params.get("event");

    if (!eventId) return;

    nav.querySelectorAll('a[href*="event=event-sim-001"]').forEach(anchor => {
      const url = new URL(anchor.href, window.location.href);
      url.searchParams.set("event", eventId);

      anchor.href =
        url.pathname.substring(url.pathname.lastIndexOf("/") + 1) +
        url.search +
        url.hash;
    });
  }

  function initialize() {
    if (document.body.classList.contains("home-page")) return;

    const nav = findOperationalNavigation();

    if (!nav) {
      console.debug("[RN Navigation v2] operational navigation not found");
      return;
    }

    renderNavigation(nav);
    preserveEventContext(nav);
    mountPoskoFunctionGroup(nav).catch(() => {});

    // Re-evaluate once session-role.js confirms/denies the login (async).
    window.addEventListener("rn:frappe-session", () => {
      mountPoskoFunctionGroup(nav).catch(() => {});
    });

    document.documentElement.classList.add("rn-navigation-v2-ready");

    console.info(
      `[RN Navigation v${CONFIG.version}] initialized`,
      currentFile()
    );
  }

  // Let a page (e.g. posko-logistik.html's posko dropdown) refresh the top
  // function group after it changes the active posko / URL.
  window.rnRefreshPoskoFunctionGroup = function () {
    const nav = findOperationalNavigation();
    if (nav) mountPoskoFunctionGroup(nav).catch(() => {});
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
