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
    const isDesktopViewport = window.innerWidth > 900;

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

    // LIVE (desktop only):
    // Domain w=1366,dpr=1 dibuat seperti lokal w=1821,dpr=.75.
    // 1366 / 1821 ≈ 0.75. Di layar HP/mobile, biarkan CSS responsif
    // (@media max-width:900px) yang mengatur, jangan dipaksa zoom.
    //
    // 2026-09-05: briefly removed this, reasoning the mock-ups must be
    // designed at raw 1:1 CSS scale — that was WRONG. Owner confirmed
    // removing it made every page look visibly worse / more amateurish
    // (menu + text proportions), meaning the component CSS in this file
    // was actually tuned against the zoomed-down look this whole time.
    // Restored as-is. Do not remove again without a verified, approved
    // side-by-side comparison — a "should be 1:1" theory is not enough.
    if (!isMockup && !isLocal && isDesktopViewport && appShell) {
      // Use clientWidth/clientHeight (post-scrollbar) instead of vw/vh units.
      // vw includes the vertical scrollbar's own width in most browsers, so
      // "133.333vw" ends up a few px wider than the actually-visible area
      // once a page is tall enough to show a scrollbar — after the 0.75
      // zoom that residual sliver still overflows, producing a persistent
      // horizontal scrollbar. Pixel math against clientWidth is exact.
      const zoomedW = document.documentElement.clientWidth / 0.75;
      const zoomedH = document.documentElement.clientHeight / 0.75;

      document.body.style.overflowX = "hidden";
      appShell.style.zoom = "0.75";
      appShell.style.width = zoomedW + "px";
      appShell.style.minWidth = zoomedW + "px";
      appShell.style.minHeight = zoomedH + "px";

      const sidebar = document.querySelector(".sidebar");
      const main = document.querySelector(".main");

      if (sidebar) {
        sidebar.style.height = zoomedH + "px";
        sidebar.style.minHeight = zoomedH + "px";
        sidebar.style.maxHeight = zoomedH + "px";
        sidebar.style.overflowY = "auto";
      }

      if (main) {
        main.style.minHeight = zoomedH + "px";
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
