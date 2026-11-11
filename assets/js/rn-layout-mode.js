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
      appShell.style.removeProperty("grid-template-columns");
      const sb = document.querySelector(".sidebar");
      if (sb) { sb.style.zoom = ""; ["width", "min-width", "max-width"].forEach(function (k) { sb.style.removeProperty(k); }); sb.style.removeProperty("height"); sb.style.removeProperty("min-height"); sb.style.removeProperty("max-height"); }
      const mn = document.querySelector(".main");
      if (mn) mn.style.removeProperty("min-height");
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
      // Owner 2026-11-09 malam: "nggak bisa disamakan seperti Control Centre?" -> isi halaman 100%
      // (huruf sama besar dengan Control Centre); menu samping tetap .75 agar identik dengan menu sekarang
      // dan dengan sidebar Control Centre. Kembali ke skala lama: CONTENT_ZOOM = 0.75
      // (atau git checkout tag sebelum-zoom100-20261109 -- assets/js/rn-layout-mode.js).
      // Suri 2026-11-11 (owner: "font terlalu kecil jadi kelihatan nggak profesional"): 100% dipakai bila
      // layar cukup lebar. Layar desktop sempit (901-1279px) dikecilkan secukupnya supaya tata letak
      // selebar MIN_LAYOUT_W tetap muat (tanpa ini isi terpotong di kanan: uji Playwright 1024/1100px).
      const MIN_LAYOUT_W = 1280;
      const SIDEBAR_ZOOM = 0.75;
      const viewW = document.documentElement.clientWidth;
      const viewH = document.documentElement.clientHeight;
      const CONTENT_ZOOM = Math.min(1, viewW / MIN_LAYOUT_W);
      const zoomedW = viewW / CONTENT_ZOOM;
      const zoomedH = viewH / CONTENT_ZOOM;

      document.body.style.overflowX = "hidden";
      // style.css memberi body min-width 1180px; di layar <1180px itu membuat halaman bisa digeser ke samping.
      document.body.style.minWidth = "0";
      appShell.style.zoom = String(CONTENT_ZOOM);
      appShell.style.width = zoomedW + "px";
      appShell.style.minWidth = zoomedW + "px";
      appShell.style.minHeight = zoomedH + "px";

      const sidebar = document.querySelector(".sidebar");
      const main = document.querySelector(".main");

      if (sidebar) {
        const sbH = viewH / (CONTENT_ZOOM * SIDEBAR_ZOOM);
        const sbW = 300; // lebar CSS menu = Control Centre (.cc-sidebar 300px x .75 = 225px di layar)
        sidebar.style.zoom = String(SIDEBAR_ZOOM);
        sidebar.style.setProperty("width", sbW + "px", "important");
        sidebar.style.setProperty("min-width", sbW + "px", "important");
        sidebar.style.setProperty("max-width", sbW + "px", "important");
        appShell.style.setProperty("grid-template-columns", (sbW * SIDEBAR_ZOOM) + "px minmax(0, 1fr)", "important");
        sidebar.style.setProperty("height", sbH + "px", "important");
        sidebar.style.setProperty("min-height", sbH + "px", "important");
        sidebar.style.setProperty("max-height", sbH + "px", "important");
        sidebar.style.overflowY = "auto";
      }

      if (main) {
        main.style.setProperty("min-height", zoomedH + "px", "important");
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
