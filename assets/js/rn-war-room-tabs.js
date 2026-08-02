(function () {
  "use strict";

  const TAB_CONFIG = [
    {
      id: "dashboard",
      label: "Dashboard"
    },
    {
      id: "live-map",
      label: "Live Map"
    }
  ];

  function selectedTab() {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("tab");

    return TAB_CONFIG.some(tab => tab.id === requested)
      ? requested
      : "dashboard";
  }

  function currentEventId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("event") || "event-sim-001";
  }

  function updateUrl(tabId) {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tabId);

    window.history.replaceState(
      { tab: tabId },
      "",
      url.pathname + url.search + url.hash
    );
  }

  function buildMapUrl() {
    const eventId = currentEventId();

    return (
      "map.html?event=" +
      encodeURIComponent(eventId) +
      "&embedded=war-room"
    );
  }

  function activateTab(root, tabId, updateHistory = true) {
    root.querySelectorAll("[data-rn-war-tab]").forEach(button => {
      const active = button.dataset.rnWarTab === tabId;

      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
      button.setAttribute("tabindex", active ? "0" : "-1");
    });

    root.querySelectorAll("[data-rn-war-panel]").forEach(panel => {
      const active = panel.dataset.rnWarPanel === tabId;

      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });

    if (tabId === "live-map") {
      const frame = root.querySelector("[data-rn-live-map-frame]");

      if (frame && !frame.src) {
        frame.src = frame.dataset.src;
      }
    }

    if (updateHistory) {
      updateUrl(tabId);
    }
  }

  function createTabs() {
    const main = document.querySelector("main");

    if (!main) {
      console.warn("[RN War Room Tabs] main element not found");
      return;
    }

    if (document.querySelector("[data-rn-war-room-tabs]")) {
      return;
    }

    const existingNodes = Array.from(main.childNodes);

    const root = document.createElement("section");
    root.className = "rn-war-room-workspace";
    root.dataset.rnWarRoomTabs = "1";

    const tabs = document.createElement("div");
    tabs.className = "rn-war-room-tabs";
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", "War Room workspace");

    tabs.innerHTML = TAB_CONFIG.map((tab, index) => `
      <button
        type="button"
        class="rn-war-room-tab"
        role="tab"
        data-rn-war-tab="${tab.id}"
        aria-controls="rn-war-panel-${tab.id}"
        aria-selected="false"
        tabindex="${index === 0 ? "0" : "-1"}"
      >
        ${tab.label}
      </button>
    `).join("");

    const dashboardPanel = document.createElement("div");
    dashboardPanel.id = "rn-war-panel-dashboard";
    dashboardPanel.className = "rn-war-room-panel";
    dashboardPanel.dataset.rnWarPanel = "dashboard";
    dashboardPanel.setAttribute("role", "tabpanel");

    existingNodes.forEach(node => dashboardPanel.appendChild(node));

    const mapPanel = document.createElement("div");
    mapPanel.id = "rn-war-panel-live-map";
    mapPanel.className = "rn-war-room-panel rn-war-room-map-panel";
    mapPanel.dataset.rnWarPanel = "live-map";
    mapPanel.setAttribute("role", "tabpanel");
    mapPanel.hidden = true;

    mapPanel.innerHTML = `
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

    root.appendChild(tabs);
    root.appendChild(dashboardPanel);
    root.appendChild(mapPanel);
    main.appendChild(root);

    tabs.addEventListener("click", event => {
      const button = event.target.closest("[data-rn-war-tab]");

      if (!button) return;

      activateTab(root, button.dataset.rnWarTab);
    });

    window.addEventListener("popstate", () => {
      activateTab(root, selectedTab(), false);
    });

    activateTab(root, selectedTab(), false);

    console.info(
      "[RN War Room Tabs] initialized:",
      selectedTab()
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createTabs);
  } else {
    createTabs();
  }
})();
