(() => {
  "use strict";
  const embeddedStyles = new URL("../css/rn-edisi-embedded.css?v=layout-20261122", document.currentScript.src).href;
  const workspace = document.querySelector("[data-window-workspace]");
  const taskbar = document.querySelector("[data-window-taskbar]");
  if (!workspace || !taskbar) return;

  const moduleRoutes = new Map([
    ["bencana-aktif.html", "Bencana Aktif"], ["war-room.html", "Control Centre"],
    ["peta-nasional.html", "Peta Nasional"], ["sitrep.html", "SITREP RN"],
    ["management-distribusi.html", "Manajemen Distribusi"], ["posko-logistik.html", "Posko Logistik"],
    ["posko-distribusi.html", "Posko Distribusi"], ["posko-medis-detail.html", "Posko Medis"],
    ["shelter-detail.html", "Shelter"], ["dapur-umum.html", "Dapur Umum"],
    ["management-relawan.html", "Relawan"], ["laporan-masyarakat.html", "Laporan Masyarakat"],
    ["search-found.html", "Search & Found"], ["verification-approval.html", "Sistem Verifikasi"],
    ["jejak-audit.html", "Jejak Audit"]
  ]);
  const showMap = document.querySelector("[data-show-map]");
  const nav = document.querySelector(".rn-dms-module-nav");
  const catalogList = nav.querySelector("[data-dms-catalog]");
  const menuToggle = document.querySelector('[aria-controls="dms-menu"]');
  const sessionBadge = document.querySelector("[data-rn-session]");
  const backendStatus = document.querySelector("[data-rn-backend-status]");
  const authButton = document.querySelector("[data-rn-auth]");
  const loginDialog = document.querySelector("[data-rn-login-dialog]");
  const loginForm = document.querySelector("[data-rn-login-form]");
  const loginMessage = document.querySelector("[data-rn-login-message]");
  let rnSession = {};

  async function requestSession() {
    const response = await fetch("/rescue-net-frappe/api/method/rescue_net.api_auth.session_info", {
      credentials: "include",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error("API unavailable");
    const payload = await response.json();
    return (payload && payload.message) || {};
  }

  async function refreshRnSession() {
    try {
      rnSession = await requestSession();
      const loggedIn = !!rnSession.user && rnSession.user !== "Guest";
      if (sessionBadge) sessionBadge.textContent = loggedIn ? "SESI AKTIF" : "TAMU";
      if (authButton) authButton.textContent = loggedIn ? "Logout" : "Login";
      if (backendStatus) {
        backendStatus.classList.add("is-connected");
        backendStatus.textContent = "API Rescue-Net terhubung";
      }
    } catch (_) {
      rnSession = {};
      if (sessionBadge) sessionBadge.textContent = "STATUS API TIDAK TERSEDIA";
      if (authButton) authButton.textContent = "Login";
      if (backendStatus) {
        backendStatus.classList.remove("is-connected");
        backendStatus.textContent = "BACKEND RN BELUM TERJANGKAU · modul memerlukan koneksi ke API RN.";
      }
    }
    window.dispatchEvent(new Event("rn-dms-session"));
  }

  authButton?.addEventListener("click", async () => {
    if (rnSession.user && rnSession.user !== "Guest") {
      authButton.disabled = true;
      try {
        const headers = { Accept: "application/json" };
        if (rnSession.csrf_token) headers["X-Frappe-CSRF-Token"] = rnSession.csrf_token;
        const response = await fetch("/rescue-net-frappe/api/method/logout", {
          method: "POST", credentials: "include", headers
        });
        if (!response.ok) throw new Error("logout failed");
        await refreshRnSession();
      } catch (_) {
        if (loginMessage) loginMessage.textContent = "Belum berhasil keluar. Coba muat ulang halaman.";
      } finally {
        authButton.disabled = false;
      }
      return;
    }
    if (loginMessage) loginMessage.textContent = "Gunakan akun RN. Login diproses oleh backend RN yang sama.";
    loginDialog?.showModal();
    window.setTimeout(() => loginForm?.elements.usr?.focus(), 0);
  });

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = String(loginForm.elements.usr.value || "").trim();
    const password = String(loginForm.elements.pwd.value || "");
    if (!email || !password) {
      if (loginMessage) loginMessage.textContent = "Isi email dan password akun RN.";
      return;
    }
    const submit = loginForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    if (loginMessage) loginMessage.textContent = "Memeriksa akun RN…";
    try {
      const response = await fetch("/rescue-net-frappe/api/method/login", {
        method: "POST", credentials: "include",
        headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ usr: email, pwd: password }).toString()
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.exc_type) throw new Error("login failed");
      await refreshRnSession();
      if (!rnSession.user || rnSession.user === "Guest") throw new Error("session missing");
      loginForm.elements.pwd.value = "";
      loginDialog?.close();
    } catch (_) {
      if (loginMessage) loginMessage.textContent = "Login gagal. Periksa email, password, atau kewajiban kode verifikasi.";
    } finally {
      submit.disabled = false;
    }
  });
  document.querySelector("[data-rn-login-cancel]")?.addEventListener("click", () => loginDialog?.close());
  const windows = new Map();
  let zIndex = 2;
  let serial = 0;

  function updateStatus() {
    showMap.hidden = ![...windows.values()].some(({ element }) => !element.classList.contains("is-minimized"));
  }

  function focusWindow(win) {
    win.style.zIndex = String(++zIndex);
    windows.forEach((item) => item.taskButton.classList.toggle("is-active", item.element === win));
  }

  function setMinimized(item, minimized) {
    item.element.classList.toggle("is-minimized", minimized);
    item.taskButton.setAttribute("aria-pressed", String(!minimized));
    if (minimized) item.taskButton.classList.remove("is-active");
    else focusWindow(item.element);
    updateStatus();
  }

  function setMaximized(item) {
    const win = item.element;
    const button = win.querySelector("[data-maximize]");
    if (!win.classList.contains("is-maximized")) {
      item.restore = { left: win.style.left, top: win.style.top, width: win.style.width, height: win.style.height };
      win.classList.add("is-maximized");
      if (button) { button.textContent = "❐"; button.setAttribute("aria-label", "Pulihkan ukuran"); }
    } else {
      win.classList.remove("is-maximized");
      if (item.restore) Object.assign(win.style, item.restore);
      if (button) { button.textContent = "□"; button.setAttribute("aria-label", "Maksimalkan"); }
    }
    focusWindow(win);
  }

  function createWindow(title, url, dmsMenu) {
    const existing = [...windows.values()].find((item) => item.url === url);
    if (existing) {
      setMinimized(existing, false);
      return;
    }
    const win = document.createElement("section");
    const id = `rn-window-${++serial}`;
    win.className = "rn-edisi-window";
    win.dataset.windowId = id;
    win.setAttribute("aria-label", title);
    const offset = (serial - 1) % 3;
    win.style.left = `${16 + offset * 24}px`;
    win.style.top = `${16 + offset * 20}px`;
    win.style.zIndex = String(++zIndex);

    const bar = document.createElement("header");
    bar.className = "rn-edisi-window-bar";
    const heading = document.createElement("strong");
    heading.className = "rn-edisi-window-title";
    heading.textContent = title;
    const controls = document.createElement("div");
    controls.className = "rn-edisi-window-controls";
    const minimize = controlButton("−", "Minimalkan", "data-minimize");
    const maximize = controlButton("□", "Maksimalkan", "data-maximize");
    const close = controlButton("×", "Tutup", "data-close");
    controls.append(minimize, maximize, close);
    bar.append(heading, controls);

    const frame = document.createElement("iframe");
    frame.className = "rn-edisi-window-frame";
    frame.title = title;
    frame.loading = "lazy";
    frame.referrerPolicy = "same-origin";
    if (dmsMenu) frame.dataset.dmsTemplate = operationTemplate;
    frame.src = url;
    frame.addEventListener("load", () => {
      const embedded = frame.contentDocument;
      if (dmsMenu || !embedded?.head || embedded.URL === "about:blank" || embedded.documentElement.classList.contains("rn-window-mode")) return;
      embedded.documentElement.classList.add("rn-window-mode");
      const stylesheet = embedded.createElement("link");
      stylesheet.rel = "stylesheet";
      stylesheet.href = embeddedStyles;
      embedded.head.append(stylesheet);
    });

    win.append(bar, frame);
    workspace.append(win);

    const taskButton = document.createElement("button");
    taskButton.type = "button";
    taskButton.textContent = title;
    taskButton.title = `Tampilkan ${title}`;
    taskButton.setAttribute("aria-pressed", "true");
    taskbar.append(taskButton);
    const item = { element: win, taskButton, restore: null, dmsMenu, url };
    windows.set(id, item);

    minimize.addEventListener("click", () => setMinimized(item, true));
    maximize.addEventListener("click", () => setMaximized(item));
    close.addEventListener("click", () => {
      windows.delete(id);
      win.remove();
      taskButton.remove();
      updateStatus();
    });
    taskButton.addEventListener("click", () => {
      if (win.classList.contains("is-minimized")) setMinimized(item, false);
      else if (win.style.zIndex === String(zIndex)) setMinimized(item, true);
      else focusWindow(win);
    });
    win.addEventListener("pointerdown", () => focusWindow(win));
    dragWindow(bar, win);
    updateStatus();
    focusWindow(win);
  }

  function controlButton(label, accessibleName, attribute) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-label", accessibleName);
    button.setAttribute(attribute, "");
    return button;
  }

  function dragWindow(handle, win) {
    let drag = null;
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("button") || win.classList.contains("is-maximized") || window.matchMedia("(max-width: 850px)").matches) return;
      const bounds = workspace.getBoundingClientRect();
      const rect = win.getBoundingClientRect();
      drag = { x: event.clientX, y: event.clientY, left: rect.left - bounds.left + workspace.scrollLeft, top: rect.top - bounds.top + workspace.scrollTop };
      handle.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    handle.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const maxLeft = Math.max(0, workspace.clientWidth - win.offsetWidth);
      const maxTop = Math.max(0, workspace.clientHeight - win.offsetHeight);
      win.style.left = `${Math.min(maxLeft, Math.max(0, drag.left + event.clientX - drag.x))}px`;
      win.style.top = `${Math.min(maxTop, Math.max(0, drag.top + event.clientY - drag.y))}px`;
    });
    const finish = () => { drag = null; };
    handle.addEventListener("pointerup", finish);
    handle.addEventListener("pointercancel", finish);
  }

  window.rnEdisiOpenWindow = createWindow;
  const moduleStatus = document.querySelector("[data-module-status]");
  const templateSelect = document.querySelector("[data-dms-template]");
  const { labels, load, resolveTemplate, remember, visible } = window.RNDmsMenus;
  const shell = document.querySelector(".rn-dms-shell");
  let operationTemplate = "bnpb";
  let menus = [];
  let catalogRequest = 0;

  function applyTemplate(template) {
    operationTemplate = template;
    templateSelect.value = template;
    if (shell) shell.dataset.agency = template;
    document.querySelectorAll("[data-agency-label], [data-agency-footer]").forEach((node) => {
      node.textContent = labels[template];
    });
    const available = visible(menus, template);
    for (const item of windows.values()) {
      if (item.dmsMenu && !available.some((menu) => menu.id === item.dmsMenu)) {
        item.element.querySelector("[data-close]").click();
      }
    }
    catalogList.replaceChildren();
    for (const agency of [template, "bersama"]) {
      const entries = available.filter((menu) => (agency === "bersama") === (menu.instansi === "bersama"));
      if (!entries.length) continue;
      const group = document.createElement("section");
      group.dataset.dmsGroup = agency;
      const title = document.createElement("h2");
      title.textContent = labels[agency];
      const list = document.createElement("ul");
      for (const menu of entries) {
        addMenuLink(list, menu.judul, "dms-modul.html?menu=" + encodeURIComponent(menu.id), menu.id);
      }
      group.append(title, list);
      catalogList.append(group);
    }
  }

  function addMenuLink(list, title, url, menuId) {
    const row = document.createElement("li");
    const anchor = document.createElement("a");
    anchor.textContent = title;
    anchor.href = url;
    if (menuId) anchor.dataset.dmsMenu = menuId;
    anchor.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      createWindow(title, url, menuId);
      if (window.matchMedia("(max-width: 850px)").matches) {
        menuToggle.setAttribute("aria-expanded", "false");
        showMap.scrollIntoView({ block: "nearest" });
      }
      showMap.focus({ preventScroll: true });
    });
    row.append(anchor);
    list.append(row);
  }

  const rnList = nav.querySelector("[data-rn-modules]");
  for (const [route, title] of moduleRoutes) addMenuLink(rnList, title, route);

  document.querySelectorAll("[data-panel-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      button.setAttribute("aria-expanded", String(button.getAttribute("aria-expanded") === "false"));
    });
  });
  showMap.addEventListener("click", () => {
    for (const item of windows.values()) setMinimized(item, true);
    workspace.querySelector("[data-live-map]").focus();
  });

  async function refreshTemplate() {
    const request = ++catalogRequest;
    templateSelect.disabled = true;
    const [selection, catalog] = await Promise.all([resolveTemplate(), load().catch(() => null)]);
    if (request !== catalogRequest) return;
    menus = catalog || [];
    applyTemplate(selection.value);
    templateSelect.disabled = selection.managed;
    templateSelect.title = selection.managed ? "Template ditetapkan organisasi RN" : "";
    moduleStatus.textContent = catalog ? "" : "Daftar modul DMS belum dapat dimuat.";
    moduleStatus.hidden = !!catalog;
  }

  templateSelect.addEventListener("change", () => {
    remember(templateSelect.value);
    applyTemplate(templateSelect.value);
  });
  let previousUser;
  window.addEventListener("rn-dms-session", () => {
    if (previousUser !== undefined && previousUser !== rnSession.user) {
      for (const item of windows.values()) {
        if (!rnSession.user || rnSession.user === "Guest" || item.dmsMenu) {
          item.element.querySelector("[data-close]").click();
        } else {
          item.element.querySelector("iframe").src = item.url;
        }
      }
    }
    previousUser = rnSession.user;
    refreshTemplate();
  });
  const requested = new URLSearchParams(location.search).get("buka");
  const page = requested?.match(/^([a-z0-9][a-z0-9-]*\.html)(?:[?#].*)?$/i)?.[1];
  if (page && !["edisi-tertutup.html", "auth.html", "dms-modul.html"].includes(page.toLowerCase())) {
    createWindow(moduleRoutes.get(page) || page.replace(/\.html$/i, "").replaceAll("-", " "), requested);
  }

  const poskoDialog = document.querySelector("[data-posko-dialog]");
  const poskoForm = document.querySelector("[data-posko-form]");
  const poskoInput = document.querySelector("[data-posko-id]");
  document.querySelector("[data-add-posko]")?.addEventListener("click", () => {
    poskoDialog?.showModal();
    window.setTimeout(() => poskoInput?.focus(), 0);
  });
  poskoForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const poskoId = poskoInput?.value.trim();
    if (!poskoId || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,139}$/.test(poskoId)) return;
    poskoDialog.close();
    createWindow(`Posko · ${poskoId}`, `posko-detail.html?id=${encodeURIComponent(poskoId)}`);
    poskoForm.reset();
  });
  document.querySelectorAll("[data-dialog-cancel]").forEach((button) => button.addEventListener("click", () => button.closest("dialog")?.close()));
  updateStatus();
  refreshRnSession();
})();
