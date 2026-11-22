(() => {
  "use strict";

  if (!["disastermanagement.online", "www.disastermanagement.online"].includes(location.hostname)) return;
  const script = document.currentScript;
  const page = location.pathname.split("/").pop();
  if (window !== window.top) {
    document.documentElement.classList.add("rn-window-mode");
    if (!document.querySelector('link[href*="rn-edisi-tertutup.css"]')) {
      const theme = document.createElement("link");
      theme.rel = "stylesheet";
      theme.href = new URL("../css/rn-edisi-tertutup.css?v=layout-20261122", script.src).href;
      document.head.append(theme);
    }
    const embedded = document.createElement("link");
    embedded.rel = "stylesheet";
    embedded.href = new URL("../css/rn-edisi-embedded.css?v=layout-20261122", script.src).href;
    document.head.append(embedded);
    return;
  }
  if (page === "auth.html") return;
  const home = new URL("edisi-tertutup.html", location.href);
  home.searchParams.set("buka", page + location.search + location.hash);
  location.replace(home.href);
})();
