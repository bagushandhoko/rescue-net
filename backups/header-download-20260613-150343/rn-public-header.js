(function () {
  const isHome = document.body.classList.contains("home-page");
  const prefix = isHome ? "" : "../";

  const links = [
    { label: "About Us", href: `${prefix}index.html#tentang` },
    { label: "Fitur/Mock up", href: `${prefix}pages/mockup.html?screen=welcome` },
    { label: "Home", href: `${prefix}index.html` },
    { label: "War Room", href: `${prefix}pages/war-room.html?event=event-sim-001` },
    { label: "Data Konsolidasi", href: `${prefix}pages/data-consolidation.html?event=event-sim-001` },
    { label: "Aplikasi", href: `${prefix}../rescue-net-app/` },
    { label: "Download", href: `${prefix}../rescue-net-app/#download` },
    { label: "Laporan Masyarakat", href: `${prefix}pages/laporan-masyarakat.html` },
    { label: "Login/registrasi", href: `${prefix}pages/auth.html`, className: "rn-public-login" }
  ];

  function closeMenu(header, button) {
    header.classList.remove("is-open");
    button.setAttribute("aria-expanded", "false");
  }

  function buildHeader() {
    if (isHome || document.querySelector(".rn-public-header")) return;

    const header = document.createElement("header");
    header.className = "rn-public-header";
    header.innerHTML = `
      <a class="rn-public-brand" href="${prefix}index.html" aria-label="Rescue-Net Home">
        <img src="${prefix}assets/img/rn-logo-web.png" alt="">
      </a>
      <nav class="rn-public-links" aria-label="Rescue-Net public navigation">
        ${links.map(link => `<a class="${link.className || ""}" href="${link.href}">${link.label}</a>`).join("")}
      </nav>
      <button class="rn-public-toggle" type="button" aria-label="Buka menu" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    `;

    document.body.insertBefore(header, document.body.firstChild);

    const button = header.querySelector(".rn-public-toggle");
    button.addEventListener("click", () => {
      const open = header.classList.toggle("is-open");
      button.setAttribute("aria-expanded", open ? "true" : "false");
    });

    header.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => closeMenu(header, button));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildHeader);
  } else {
    buildHeader();
  }
})();

