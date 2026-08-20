(function () {
  "use strict";

  const CONFIG = {
    version: "2.0.2",

    posko: [
      {
        label: "Dashboard Posko",
        href: "organisasi-posko.html"
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
        href: "management-distribusi.html"
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
      }
    ],

    modules: [
      {
        label: "Map",
        href: "map.html?event=event-sim-001"
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
        label: "Verification",
        href: "verification-approval.html"
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

  function groupHtml(label, items, groupId) {
    const active = items.some(item => isActive(item.href));

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

  function renderNavigation(nav) {
    nav.classList.add("rn-nav-v2");
    nav.setAttribute("data-rn-navigation-version", CONFIG.version);
    nav.setAttribute("aria-label", "Navigasi operasional Rescue-Net");

    nav.innerHTML =
      groupHtml("Posko", CONFIG.posko, "posko") +
      groupHtml("Modul", CONFIG.modules, "modul");

    // Accordion: only one group open at a time.
    const groups = Array.from(nav.querySelectorAll(".rn-nav-v2-group"));
    groups.forEach(group => {
      group.addEventListener("toggle", () => {
        if (!group.open) return;
        groups.forEach(other => {
          if (other !== group) other.open = false;
        });
      });
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

    document.documentElement.classList.add("rn-navigation-v2-ready");

    console.info(
      `[RN Navigation v${CONFIG.version}] initialized`,
      currentFile()
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
