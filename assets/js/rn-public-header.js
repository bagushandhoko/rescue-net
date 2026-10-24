(function () {
  function isHome() { return document.body?.classList?.contains("home-page") || false; }
  const prefix = isHome() ? "" : "..";

  const LOGIN_LINK = { label: "Login/registrasi", href: `${prefix}pages/auth.html`, className: "rn-public-login" };

  const RN_EVENT_DEFAULT = "event-sim-001";
  const RN_EVENT_STORE_KEY = "rn_active_event";
  const RN_API = location.origin + "/rescue-net-frappe/api/method/";

  function stripEventPrefix(v) { return String(v || "").replace(/^disaster_events:/, ""); }

  function prettifyEventId(id) {
    return String(id || "").replace(/^event[-_]/i, "").replace(/[-_]+/g, " ").replace(/\b\w/g, c => c.toUpperCase()).trim() || id;
  }

  function readStoredEvent() { try { return localStorage.getItem(RN_EVENT_STORE_KEY) || ""; } catch (e) { return ""; } }
  function writeStoredEvent(v) { try { localStorage.setItem(RN_EVENT_STORE_KEY, v); } catch (e) {} }
  function currentEventId() {
    const url = new URL(location.href);
    const fromUrl = stripEventPrefix(url.searchParams.get("event") || url.searchParams.get("disaster_event_id") || "");
    if (fromUrl) return fromUrl;
    return stripEventPrefix(readStoredEvent()) || "event-sim-001";
  }
  function ensureEventInUrl(eventId) {
    const url = new URL(location.href);
    if (!url.searchParams.get("event")) { url.searchParams.set("event", eventId); try { history.replaceState(null, "", url.toString()); } catch (e) {} }
  }
  function goToEvent(eventId) { writeStoredEvent(eventId); const url = new URL(location.href); url.searchParams.set("event", eventId); url.searchParams.delete("disaster_event_id"); location.href = url.toString(); }

  window.rnActiveEvent = currentEventId();

  const links = [
    { label: "About Us", children: [ { label: "Fitur/Mock up", href: `${prefix}pages/mockup.html?screen=welcome` }, { label: "Manual Rescue Net", href: `${prefix}pages/manual.html` } ] },
    { label: "Home", href: `${prefix}index.html` }, { label: "Bencana Aktif", href: `${prefix}pages/bencana-aktif.html` },
    { label: "Control Centre", href: `${prefix}pages/war-room.html?event=${encodeURIComponent(window.rnActiveEvent)}` },
    { label: "Install App", href: `${prefix}pages/install.html` },
    { label: "Laporan Masyarakat", href: `${prefix}pages/laporan-masyarakat.html` },
    { label: "Kirim Bantuan", href: `${prefix}pages/kirim-bantuan.html` }
  ];

  function renderPublicLink(link) {
    if (link.children) {
      return `<div class="rn-menu-item rn-has-submenu" role="none"><a href="#" class="rn-menu-link" aria-haspopup="true" aria-expanded="false">${link.label}</a><ul class="rn-submenu" role="menu">${link.children.map(child => `<li role="none"><a href="${child.href}" class="rn-submenu-link" role="menuitem">${child.label}</a></li>`).join("")}</ul></div>`;
    }
    return `<a class="${link.className || ""}" href="${link.href}">${link.label}</a>`;
  }

  async function buildEventPicker(header) {
    const active = window.rnActiveEvent;
    const hadEventInUrl = !!new URL(location.href).searchParams.get("event");
    ensureEventInUrl(active);
    const wrap = document.createElement("div");
    wrap.className = "rn-event-picker";
    wrap.innerHTML = `<label><span>Bencana</span><select aria-label="Pilih bencana aktif"><option value="${active}">${prettifyEventId(active)}</option></select></label>`;
    const actions = header.querySelector(".rn-public-actions") || header; actions.appendChild(wrap);
    const select = wrap.querySelector("select");
    select.addEventListener("change", () => { if (select.value && select.value !== active) goToEvent(select.value); });
    try {
      const res = await fetch(RN_API + "rescue_net.api_ai.public_active_disasters", { credentials: "omit" });
      const payload = await res.json(); const rows = (payload && payload.message) || [];
      if (rows.length) {
        select.innerHTML = rows.map(row => { const id = stripEventPrefix(row.legacy_id || row.id || row.name || ""); const title = row.title || id; const sev = row.severity ? ` (${row.severity})` : ""; const sel = id === active ? " selected" : ""; return `<option value="${id}"${sel}>${title}${sev}</option>`; }).join("");
        if (![...select.options].some(o => o.value === active)) { const opt = document.createElement("option"); opt.value = active; opt.textContent = prettifyEventId(active); opt.selected = true; select.insertBefore(opt, select.firstChild); }
      }
    } catch (e) { }
    try {
      const res = await fetch(RN_API + "rescue_net.api_auth.my_landing", { credentials: "include" });
      const mine = res.ok ? (((await res.json()) || {}).message || {}) : {}; const evs = mine.events || [];
      if (evs.length) {
        const ids = evs.map(e => e.id); const pick = ids.includes(active) ? active : (hadEventInUrl ? active : mine.latest_event);
        select.innerHTML = evs.map(e => `<option value="${e.id}"${e.id === pick ? " selected" : ""}>${e.title || prettifyEventId(e.id)}</option>`).join("");
        if (!ids.includes(pick)) { const opt = document.createElement("option"); opt.value = pick; opt.textContent = prettifyEventId(pick) + " (dilihat)"; opt.selected = true; select.insertBefore(opt, select.firstChild); }
        if (pick !== active) goToEvent(pick);
      }
    } catch (e) { }
  }

  function stripEventPrefix(v) { return String(v || "").replace(/^disaster_events:/, ""); }
  function prettifyEventId(id) { return String(id || "").replace(/^event[-_]/i, "").replace(/[-_]+/g, " ").replace(/\b\w/g, c => c.toUpperCase()).trim() || id; }
  function readStoredEvent() { try { return localStorage.getItem(RN_EVENT_STORE_KEY) || ""; } catch (e) { return ""; } }
  function writeStoredEvent(v) { try { localStorage.setItem(RN_EVENT_STORE_KEY, v); } catch (e) {} }
  function currentEventId() { const url = new URL(location.href); const fromUrl = stripEventPrefix(url.searchParams.get("event") || url.searchParams.get("disaster_event_id") || ""); if (fromUrl) return fromUrl; return stripEventPrefix(readStoredEvent()) || "event-sim-001"; }
  function ensureEventInUrl(eventId) { const url = new URL(location.href); if (!url.searchParams.get("event")) { url.searchParams.set("event", eventId); try { history.replaceState(null, "", url.toString()); } catch (e) {} } }
  function goToEvent(eventId) { writeStoredEvent(eventId); const url = new URL(location.href); url.searchParams.set("event", eventId); url.searchParams.delete("disaster_event_id"); location.href = url.toString(); }
  window.rnActiveEvent = currentEventId();

  function closeMenu(header, button) { header.classList.remove("is-open"); button.setAttribute("aria-expanded", "false"); }
  function readCookie(name) { const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)")); try { return m ? decodeURIComponent(m[1]) : ""; } catch (e) { return m ? m[1] : ""; } }

  async function buildAuthArea(container, existingLoginEl) {
    const actions = existingLoginEl ? container : (container.querySelector(".rn-public-actions") || container);
    const loginEl = existingLoginEl || document.createElement("a");
    if (!existingLoginEl) { loginEl.className = LOGIN_LINK.className; loginEl.href = LOGIN_LINK.href; loginEl.textContent = LOGIN_LINK.label; actions.appendChild(loginEl); }
    let sess = null; try { const res = await fetch(RN_API + "rescue_net.api_auth.session_info", { credentials: "include" }); if (res.ok) sess = ((await res.json()) || {}).message || null; } catch (e) { }
    if (!sess || !sess.user || sess.user === "Guest") return;
    const name = sess.full_name || readCookie("full_name") || sess.user;
    const userEl = document.createElement("span"); userEl.className = "rn-public-user"; userEl.title = sess.user + (sess.role ? " · " + sess.role : ""); userEl.textContent = "👤 " + name;
    const logoutEl = document.createElement("a"); logoutEl.className = "rn-public-login rn-public-logout"; logoutEl.href = "#"; logoutEl.textContent = "Logout"; logoutEl.addEventListener("click", async (e) => { e.preventDefault(); logoutEl.textContent = "Keluar…"; try { await fetch(RN_API + "logout", { method: "POST", credentials: "include" }); } catch (err) {} try { localStorage.removeItem("RN_USER"); } catch (err) {} location.reload(); });
    loginEl.replaceWith(userEl); userEl.insertAdjacentElement("afterend", logoutEl);
  }
  function wireHomeAuthArea() { const nav = document.querySelector(".welcome-links"); const loginLink = document.querySelector(".welcome-login-link"); if (!nav || !loginLink) return; buildAuthArea(nav, loginLink); }

  function buildHeader() {
    if (document.body.classList.contains("home-page")) { wireHomeAuthArea(); return; }
    if (document.body.classList.contains("mockup-viewer") || document.querySelector(".rn-public-header")) return;
    const header = document.createElement("header"); header.className = "rn-public-header";
    header.innerHTML = `<a class="rn-public-brand" href="${prefix}index.html" aria-label="Rescue-Net Home"><img src="${prefix}assets/img/rn-logo-web.png" alt=""><span class="rn-public-brand-name">Rescue-Net</span></a><nav class="rn-public-links" aria-label="Rescue-Net public navigation">${links.map(l => l.children ? `<div class="rn-menu-item rn-has-submenu" role="none"><a href="#" class="rn-menu-link" aria-haspopup="true" aria-expanded="false">${l.label}</a><ul class="rn-submenu" role="menu">${l.children.map(c => `<li role="none"><a href="${c.href}" class="rn-submenu-link" role="menuitem">${c.label}</a></li>`).join("")}</ul></div>` : `<a class="${l.className || ""}" href="${l.href}">${l.label}</a>`).join("")}</nav><div class="rn-public-actions"></div><button class="rn-public-toggle" type="button" aria-label="Buka menu" aria-expanded="false"><span></span><span></span><span></span></button>`;
    document.body.insertBefore(header, document.body.firstChild);
    buildEventPicker(header); buildAuthArea(header);
    const button = header.querySelector(".rn-public-toggle");
    button.addEventListener("click", () => { const open = header.classList.toggle("is-open"); button.setAttribute("aria-expanded", open ? "true" : "false"); });
    header.querySelectorAll("a").forEach(link => { link.addEventListener("click", () => closeMenu(header, button)); });
  }
  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", buildHeader); } else { buildHeader(); }
})();
