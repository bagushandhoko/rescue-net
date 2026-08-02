(function () {
  "use strict";

  const TABS = [
    {
      id: "dashboard",
      label: "Dashboard"
    },
    {
      id: "live-map",
      label: "Live Map"
    },
    {
      id: "operational-truth",
      label: "Operational Truth",
      targetIds: [
        "warScenarioRollup",
        "warScenarioRules"
      ]
    },
    {
      id: "command-center",
      label: "Command Center",
      targetIds: [
        "commandCorrectionForm",
        "commandCorrectionTrace"
      ]
    },
    {
      id: "resources",
      label: "Resources",
      targetIds: [
        "quickBookingForm",
        "warRoomResourceProfiles",
        "warRoomRecoveryProjects"
      ]
    },
    {
      id: "reports",
      label: "Reports",
      targetIds: [
        "warTrustedVerifierList",
        "warTrustedVerifierSummary",
        "communityReportsList",
        "communityReportSummary",
        "specialProgramsList",
        "specialProgramUpdatesList"
      ]
    }
  ];

  function getEventId() {
    const params = new URLSearchParams(window.location.search);

    return (
      params.get("event") ||
      params.get("disaster_event_id") ||
      "event-sim-001"
    );
  }

  function getSelectedTab() {
    const requested =
      new URLSearchParams(window.location.search).get("tab");

    return TABS.some(tab => tab.id === requested)
      ? requested
      : "dashboard";
  }

  function updateUrl(tabId) {
    const url = new URL(window.location.href);

    url.searchParams.set("tab", tabId);

    history.replaceState(
      { tab: tabId },
      "",
      url.pathname + url.search + url.hash
    );
  }

  function getSectionByTargetId(id) {
    const element = document.getElementById(id);

    return element ? element.closest("section") : null;
  }

  function collectCategorizedSections(main) {
    const categories = new Map();
    const assigned = new Set();

    for (const tab of TABS) {
      if (!tab.targetIds) {
        continue;
      }

      const sections = [];

      for (const id of tab.targetIds) {
        const section = getSectionByTargetId(id);

        if (!section || !main.contains(section)) {
          console.debug(
            `[RN War Room v3] target tidak ditemukan: ${id}`
          );
          continue;
        }

        if (!sections.includes(section)) {
          sections.push(section);
        }

        assigned.add(section);
      }

      categories.set(tab.id, sections);
    }

    /*
     * Semua section yang tidak dipetakan ke tab khusus
     * menjadi bagian Dashboard:
     * hero, KPI, alerts, AI recommendations,
     * stock watch, dan module summary.
     */
    const dashboardSections = Array.from(
      main.querySelectorAll(":scope > section")
    ).filter(section => !assigned.has(section));

    categories.set("dashboard", dashboardSections);

    return categories;
  }

  function buildMapUrl() {
    return (
      "map.html?event=" +
      encodeURIComponent(getEventId()) +
      "&embedded=war-room"
    );
  }

  function createMapPanel(main, tabsBar) {
    let panel = document.getElementById(
      "rn-war-room-live-map-panel"
    );

    if (panel) {
      return panel;
    }

    panel = document.createElement("section");
    panel.id = "rn-war-room-live-map-panel";
    panel.className =
      "rn-war-room-panel rn-war-room-map-panel";
    panel.dataset.rnWarSpecialPanel = "live-map";
    panel.hidden = true;

    panel.innerHTML = `
      <div class="rn-war-room-map-toolbar">
        <div>
          <h2>Live Map</h2>
          <p>
            Titik posko, lokasi operasional, alat kerja,
            pencarian korban, dan data lokasi Rescue-Net.
          </p>
        </div>

        <a
          class="btn"
          href="${buildMapUrl()}"
          target="_blank"
          rel="noopener"
        >
          Buka Peta Penuh
        </a>
      </div>

      <iframe
        class="rn-war-room-map-frame"
        data-rn-live-map-frame
        data-src="${buildMapUrl()}"
        title="Rescue-Net Live Map"
        loading="lazy"
      ></iframe>
    `;

    tabsBar.insertAdjacentElement("afterend", panel);

    return panel;
  }

  function createTabsBar(main) {
    const existing = document.querySelector(
      "[data-rn-war-tabs-v3]"
    );

    if (existing) {
      return existing;
    }

    const tabs = document.createElement("div");

    tabs.className = "rn-war-room-tabs";
    tabs.dataset.rnWarTabsV3 = "1";
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute(
      "aria-label",
      "War Room workspace"
    );

    tabs.innerHTML = TABS.map(tab => `
      <button
        id="rn-war-tab-${tab.id}"
        type="button"
        class="rn-war-room-tab"
        data-rn-war-tab="${tab.id}"
        role="tab"
        aria-selected="false"
        tabindex="-1"
      >
        ${tab.label}
      </button>
    `).join("");

    main.insertBefore(tabs, main.firstChild);

    return tabs;
  }

  function setSectionVisibility(
    categories,
    selectedTab,
    mapPanel
  ) {
    const allSections = new Set();

    for (const sections of categories.values()) {
      sections.forEach(section => allSections.add(section));
    }

    allSections.forEach(section => {
      section.hidden = true;
      section.classList.remove("rn-war-section-active");
    });

    const visibleSections =
      categories.get(selectedTab) || [];

    visibleSections.forEach(section => {
      section.hidden = false;
      section.classList.add("rn-war-section-active");
    });

    mapPanel.hidden = selectedTab !== "live-map";

    if (selectedTab === "live-map") {
      const frame = mapPanel.querySelector(
        "[data-rn-live-map-frame]"
      );

      if (frame && !frame.getAttribute("src")) {
        frame.setAttribute("src", frame.dataset.src);
      }
    }
  }

  function activateTab(
    tabsBar,
    categories,
    mapPanel,
    tabId,
    updateHistory = true
  ) {
    tabsBar
      .querySelectorAll("[data-rn-war-tab]")
      .forEach(button => {
        const active =
          button.dataset.rnWarTab === tabId;

        button.classList.toggle("active", active);
        button.setAttribute(
          "aria-selected",
          active ? "true" : "false"
        );
        button.setAttribute(
          "tabindex",
          active ? "0" : "-1"
        );
      });

    setSectionVisibility(
      categories,
      tabId,
      mapPanel
    );

    if (updateHistory) {
      updateUrl(tabId);
    }
  }

  function setupKeyboard(
    tabsBar,
    categories,
    mapPanel
  ) {
    const buttons = Array.from(
      tabsBar.querySelectorAll("[data-rn-war-tab]")
    );

    buttons.forEach((button, index) => {
      button.addEventListener("keydown", event => {
        if (
          event.key !== "ArrowLeft" &&
          event.key !== "ArrowRight"
        ) {
          return;
        }

        event.preventDefault();

        const direction =
          event.key === "ArrowRight" ? 1 : -1;

        const nextIndex =
          (index + direction + buttons.length) %
          buttons.length;

        const nextButton = buttons[nextIndex];

        nextButton.focus();

        activateTab(
          tabsBar,
          categories,
          mapPanel,
          nextButton.dataset.rnWarTab
        );
      });
    });
  }

  function initialize() {
    const main = document.querySelector("main");

    if (!main) {
      console.warn(
        "[RN War Room v3] elemen main tidak ditemukan"
      );
      return;
    }

    const tabsBar = createTabsBar(main);
    const categories =
      collectCategorizedSections(main);
    const mapPanel =
      createMapPanel(main, tabsBar);

    tabsBar.addEventListener("click", event => {
      const button = event.target.closest(
        "[data-rn-war-tab]"
      );

      if (!button) {
        return;
      }

      activateTab(
        tabsBar,
        categories,
        mapPanel,
        button.dataset.rnWarTab
      );
    });

    setupKeyboard(
      tabsBar,
      categories,
      mapPanel
    );

    window.addEventListener("popstate", () => {
      activateTab(
        tabsBar,
        categories,
        mapPanel,
        getSelectedTab(),
        false
      );
    });

    activateTab(
      tabsBar,
      categories,
      mapPanel,
      getSelectedTab(),
      false
    );

    console.info(
      "[RN War Room v3] visibility tabs initialized",
      getSelectedTab()
    );
  }

  /*
   * Jalankan setelah seluruh handler DOMContentLoaded
   * lain mendapat kesempatan bekerja.
   * Tidak memindahkan atau menghapus elemen target.
   */
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      () => window.setTimeout(initialize, 0)
    );
  } else {
    window.setTimeout(initialize, 0);
  }
})();
