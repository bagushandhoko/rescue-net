(function () {
  const isHome = document.body.classList.contains("home-page");
  const prefix = isHome ? "" : "../";

  const links = [
    { label: "About Us", href: `${prefix}index.html#tentang` },
    { label: "Fitur/Mock up", href: `${prefix}pages/mockup.html?screen=welcome` },
    { label: "Home", href: `${prefix}index.html` },
    { label: "Bencana Aktif", href: `${prefix}pages/bencana-aktif.html` },
    { label: "Control Centre", href: `${prefix}pages/war-room.html?event=event-sim-001` },
    { label: "Data Konsolidasi", href: `${prefix}pages/data-consolidation.html?event=event-sim-001` },
    { label: "Download", href: `${prefix}../rescue-net-app/download.html` },
    { label: "Laporan Masyarakat", href: `${prefix}pages/laporan-masyarakat.html` },
    { label: "Kirim Bantuan", href: `${prefix}pages/kirim-bantuan.html` }
  ];

  const LOGIN_LINK = { label: "Login/registrasi", href: `${prefix}pages/auth.html`, className: "rn-public-login" };

  // ---- Shared disaster-event picker -----------------------------------------
  const RN_EVENT_DEFAULT = "event-sim-001";
  const RN_EVENT_STORE_KEY = "rn_active_event";
  const RN_API =
    location.origin + "/rescue-net-frappe/api/method/";

  function stripEventPrefix(v) {
    return String(v || "").replace(/^disaster_events:/, "");
  }

  function readStoredEvent() {
    try {
      return localStorage.getItem(RN_EVENT_STORE_KEY) || "";
    } catch (e) {
      return "";
    }
  }

  function writeStoredEvent(v) {
    try {
      localStorage.setItem(RN_EVENT_STORE_KEY, v);
    } catch (e) {}
  }

  function currentEventId() {
    const url = new URL(location.href);
    const fromUrl = stripEventPrefix(
      url.searchParams.get("event") ||
      url.searchParams.get("disaster_event_id") ||
      ""
    );

    if (fromUrl) return fromUrl;

    return stripEventPrefix(readStoredEvent()) || RN_EVENT_DEFAULT;
  }

  // Make sure ?event= is present so every page's own JS can read it.
  function ensureEventInUrl(eventId) {
    const url = new URL(location.href);

    if (!url.searchParams.get("event")) {
      url.searchParams.set("event", eventId);

      try {
        history.replaceState(null, "", url.toString());
      } catch (e) {}
    }
  }

  function goToEvent(eventId) {
    writeStoredEvent(eventId);

    const url = new URL(location.href);
    url.searchParams.set("event", eventId);
    url.searchParams.delete("disaster_event_id");

    location.href = url.toString();
  }

  window.rnActiveEvent = currentEventId();

  async function buildEventPicker(header) {
    const active = window.rnActiveEvent;
    ensureEventInUrl(active);

    const wrap = document.createElement("div");
    wrap.className = "rn-event-picker";
    wrap.innerHTML = `
      <label>
        <span>Bencana</span>
        <select aria-label="Pilih bencana aktif">
          <option value="${active}">${active}</option>
        </select>
      </label>
    `;

    const toggle = header.querySelector(".rn-public-toggle");
    header.insertBefore(wrap, toggle);

    const select = wrap.querySelector("select");

    select.addEventListener("change", () => {
      if (select.value && select.value !== active) {
        goToEvent(select.value);
      }
    });

    try {
      const res = await fetch(
        RN_API + "rescue_net.api_ai.public_active_disasters",
        { credentials: "omit" }
      );
      const payload = await res.json();
      const rows = (payload && payload.message) || [];

      if (rows.length) {
        select.innerHTML = rows
          .map(row => {
            const id = stripEventPrefix(
              row.legacy_id || row.id || row.name || ""
            );
            const title = row.title || id;
            const sev = row.severity ? ` (${row.severity})` : "";
            const sel = id === active ? " selected" : "";
            return `<option value="${id}"${sel}>${title}${sev}</option>`;
          })
          .join("");

        // active event not in the active list -> keep it as an extra option
        if (![...select.options].some(o => o.value === active)) {
          const opt = document.createElement("option");
          opt.value = active;
          opt.textContent = active;
          opt.selected = true;
          select.insertBefore(opt, select.firstChild);
        }
      }
    } catch (e) {
      /* offline / not reachable -> leave the single current option */
    }
  }

  function closeMenu(header, button) {
    header.classList.remove("is-open");
    button.setAttribute("aria-expanded", "false");
  }

  function buildHeader() {
    if (
      isHome ||
      document.body.classList.contains("mockup-viewer") ||
      document.querySelector(".rn-public-header")
    ) return;

    const header = document.createElement("header");
    header.className = "rn-public-header";
    header.innerHTML = `
      <a class="rn-public-brand" href="${prefix}index.html" aria-label="Rescue-Net Home">
        <img src="${prefix}assets/img/rn-logo-web.png" alt="">
        <span class="rn-public-brand-name">Rescue-Net</span>
      </a>
      <nav class="rn-public-links" aria-label="Rescue-Net public navigation">
        ${links.map(link => `<a class="${link.className || ""}" href="${link.href}">${link.label}</a>`).join("")}
      </nav>
      <button class="rn-public-toggle" type="button" aria-label="Buka menu" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    `;

    document.body.insertBefore(header, document.body.firstChild);

    buildEventPicker(header);

    const loginEl = document.createElement("a");
    loginEl.className = LOGIN_LINK.className;
    loginEl.href = LOGIN_LINK.href;
    loginEl.textContent = LOGIN_LINK.label;
    header.insertBefore(loginEl, header.querySelector(".rn-public-toggle"));

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
