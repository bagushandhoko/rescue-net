(function () {
  function isHome() { return document.body?.classList?.contains("home-page") || false; }
  const prefix = isHome() ? "" : "../";

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
    { label: "About Us", children: [ { label: "Fitur/Mock up", href: `${prefix}pages/mockup.html?screen=welcome` }, { label: "Manual Rescue Net", href: `${prefix}pages/manual.html` }, { label: "Manual Teknis", href: `${prefix}pages/manual-teknis.html` } ] },
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
    const doLogout = async (el) => { el.textContent = "Keluar…"; try { await fetch(RN_API + "logout", { method: "POST", credentials: "include", headers: sess.csrf_token ? { "X-Frappe-CSRF-Token": sess.csrf_token } : {} }); } catch (err) {} try { localStorage.removeItem("RN_USER"); } catch (err) {} location.reload(); };
    // owner 2026-10-26: clicking the name opens the account's own settings
    if (!document.getElementById("rnUserMenuCss")) {
      const st = document.createElement("style"); st.id = "rnUserMenuCss";
      st.textContent = "/* account menu on the user name (2026-10-26) */ .rn-user-wrap { position: relative; display: inline-flex; } .rn-user-btn { font: inherit; color: inherit; background: none; border: 0; padding: 4px 6px; cursor: pointer; border-radius: 8px; } .rn-user-btn:hover, .rn-user-btn:focus-visible { background: rgba(232, 117, 90, .12); outline: none; } .rn-user-menu { position: absolute; right: 0; top: calc(100% + 6px); z-index: 1000; min-width: 240px; max-width: min(320px, 92vw);   background: #fff; color: #2d211b; border: 1px solid rgba(104, 64, 45, .18); border-radius: 12px; box-shadow: 0 10px 30px rgba(0, 0, 0, .14);   padding: 6px; display: grid; } .rn-user-menu[hidden] { display: none; } .rn-user-menu-head { display: grid; gap: 2px; padding: 8px 10px 10px; border-bottom: 1px solid rgba(104, 64, 45, .12); margin-bottom: 4px; } .rn-user-menu-head small { color: #7c6458; font-size: 12px; overflow-wrap: anywhere; } .rn-user-menu a { display: block; padding: 9px 10px; border-radius: 8px; color: inherit; text-decoration: none; font-size: 14px; } .rn-user-menu a:hover, .rn-user-menu a:focus-visible { background: #fff4ef; outline: none; } .rn-user-menu .rn-user-logout { color: #c0392b; border-top: 1px solid rgba(104, 64, 45, .12); margin-top: 4px; } .rn-drawer-public .rn-user-wrap { display: grid; } .rn-drawer-public .rn-user-menu { position: static; box-shadow: none; margin-top: 6px; min-width: 0; max-width: none; }";
      document.head.appendChild(st);
    }
    const userEl = document.createElement("span"); userEl.className = "rn-public-user rn-user-wrap";
    const btn = document.createElement("button"); btn.type = "button"; btn.className = "rn-user-btn"; btn.title = sess.user + (sess.role ? " · " + sess.role : "");
    btn.setAttribute("aria-haspopup", "true"); btn.setAttribute("aria-expanded", "false"); btn.textContent = "👤 " + name + " ▾";
    userEl.appendChild(btn);
    const pfx = location.pathname.indexOf("/pages/") !== -1 ? "" : "pages/";
    const items = [
      ["Setting akun", "ai-settings.html", true],
      ["Ganti kata sandi", "ai-settings.html#changePasswordForm", sess.login_provider !== "google"],
      ["Verifikasi dua langkah (2FA)", "ai-settings.html#twofaSection", true],
      ["Bencana yang ditangani posko", "ai-settings.html#poskoEventsPanel", !!sess.posko_id],
      ["Persetujuan anggota", "koordinasi-organisasi.html#koMemberSection", !!(sess.manages_org || sess.is_system_manager)],
      ["Komando Pusat", "komando-pusat.html", !!(sess.manages_org || sess.is_system_manager)],
      ["Jejak Audit", "jejak-audit.html", !!(sess.is_system_manager || sess.role === "command_center")],
      ["Notifikasi WhatsApp", "notifikasi-settings.html", !!sess.is_system_manager],
    ].filter(x => x[2]);
    const menu = document.createElement("div"); menu.className = "rn-user-menu"; menu.hidden = true; menu.setAttribute("role", "menu");
    const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";");
    menu.innerHTML = '<div class="rn-user-menu-head"><b>' + esc(name) + "</b><small>" + esc(sess.user) + "</small><small>" +
      esc(sess.login_provider === "google" ? "Masuk dengan Google" : "Masuk dengan kata sandi") + (sess.role ? " · " + esc(sess.role) : "") + "</small></div>" +
      items.map(x => '<a role="menuitem" href="' + pfx + x[1] + '">' + esc(x[0]) + "</a>").join("") +
      '<a role="menuitem" href="#" class="rn-user-logout">Logout</a>';
    userEl.appendChild(menu);
    const setOpen = (on) => { menu.hidden = !on; btn.setAttribute("aria-expanded", on ? "true" : "false"); };
    btn.addEventListener("click", (e) => { e.stopPropagation(); setOpen(menu.hidden); });
    document.addEventListener("click", (e) => { if (!userEl.contains(e.target)) setOpen(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });
    menu.querySelector(".rn-user-logout").addEventListener("click", (e) => { e.preventDefault(); doLogout(e.target); });
    const logoutEl = document.createElement("a"); logoutEl.className = "rn-public-login rn-public-logout"; logoutEl.href = "#"; logoutEl.textContent = "Logout"; logoutEl.addEventListener("click", (e) => { e.preventDefault(); doLogout(logoutEl); });
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
