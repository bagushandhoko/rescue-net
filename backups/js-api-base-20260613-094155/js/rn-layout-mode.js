(function () {
  function isLocalHost() {
    const host = window.location.hostname || "";
    return (
      host.startsWith("192.") ||
      host.startsWith("10.") ||
      host.startsWith("172.") ||
      host === "localhost" ||
      host === "127.0.0.1"
    );
  }

  function applyLayoutMode() {
    const isLocal = isLocalHost();
    const isMockup = window.location.pathname.includes("/mockup.html");

    document.documentElement.classList.toggle("rn-local-access", isLocal);
    document.documentElement.classList.toggle("rn-external-access", !isLocal);
    document.body.classList.toggle("rn-local-access", isLocal);
    document.body.classList.toggle("rn-external-access", !isLocal);
    document.body.classList.toggle("mockup-viewer", isMockup);

    // Reset
    document.body.style.zoom = "";
    document.body.style.width = "";
    document.body.style.minWidth = "";
    document.body.style.overflowX = "";

    const appShell = document.querySelector(".app-shell");
    const mockShell = document.querySelector(".mock-shell");

    if (appShell) {
      appShell.style.zoom = "";
      appShell.style.width = "";
      appShell.style.minWidth = "";
      appShell.style.height = "";
      appShell.style.minHeight = "";
      appShell.style.transform = "";
    }

    if (mockShell) {
      mockShell.style.zoom = "";
      mockShell.style.width = "";
      mockShell.style.minWidth = "";
      mockShell.style.height = "";
      mockShell.style.minHeight = "";
      mockShell.style.transform = "";
    }

    // LIVE:
    // Domain w=1366,dpr=1 dibuat seperti lokal w=1821,dpr=.75.
    // 1366 / 1821 ≈ 0.75.
    if (!isMockup && !isLocal && appShell) {
      document.body.style.overflowX = "auto";
      appShell.style.zoom = "0.75";
      appShell.style.width = "133.333vw";
      appShell.style.minWidth = "133.333vw";
      appShell.style.minHeight = "133.333vh";

      const sidebar = document.querySelector(".sidebar");
      const main = document.querySelector(".main");

      if (sidebar) {
        sidebar.style.height = "133.333vh";
        sidebar.style.minHeight = "133.333vh";
        sidebar.style.maxHeight = "133.333vh";
        sidebar.style.overflowY = "auto";
      }

      if (main) {
        main.style.minHeight = "133.333vh";
      }
    }

    // MOCK-UP:
    // Domain sudah pas. Lokal dpr=.75 terlihat kecil, jadi diperbesar 1 / .75 = 1.333.
    if (isMockup && isLocal && mockShell) {
      document.body.style.overflowX = "auto";
      mockShell.style.zoom = "1.333";
      mockShell.style.width = "75vw";
      mockShell.style.minWidth = "75vw";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyLayoutMode);
  } else {
    applyLayoutMode();
  }

  window.addEventListener("load", applyLayoutMode);
})();
