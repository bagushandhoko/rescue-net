(() => {
  "use strict";
  const embeddedStyles = new URL("../css/rn-edisi-embedded.css?v=terang-20261122", document.currentScript.src).href;
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
  const empty = workspace.querySelector("[data-window-empty]");
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
        backendStatus.textContent = "BACKEND RN TERHUBUNG · modul memakai API dan hak akses RN; ringkasan dashboard serta federasi masih tahap integrasi";
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
  async function refreshActiveEventCount() {
    const node = document.querySelector("[data-rn-active-events]");
    if (!node) return;
    try {
      const response = await fetch("/rescue-net-frappe/api/method/rescue_net.api_ai.public_active_disasters", {
        credentials: "include", headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error("summary unavailable");
      const payload = await response.json();
      const events = (payload && payload.message) || [];
      node.textContent = Array.isArray(events) ? String(events.length) : "—";
    } catch (_) {
      node.textContent = "—";
    }
  }

  refreshRnSession();
  const count = document.querySelector("[data-window-count]");
  const windows = new Map();
  let zIndex = 2;
  let serial = 0;

  function updateStatus() {
    const open = windows.size;
    if (count) count.textContent = `${open} jendela terbuka`;
    if (empty) empty.hidden = open > 0;
  }

  function focusWindow(win) {
    win.style.zIndex = String(++zIndex);
    windows.forEach((item) => item.taskButton.classList.toggle("is-active", item.element === win));
  }

  function setMinimized(item, minimized) {
    item.element.classList.toggle("is-minimized", minimized);
    item.taskButton.setAttribute("aria-pressed", String(!minimized));
    if (!minimized) focusWindow(item.element);
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
    const win = document.createElement("section");
    const id = `rn-window-${++serial}`;
    win.className = "rn-edisi-window";
    win.dataset.windowId = id;
    win.setAttribute("aria-label", title);
    const offset = (serial - 1) % 8;
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
      if (dmsMenu || !embedded?.head || embedded.URL === "about:blank") return;
      embedded.documentElement.classList.add("rn-window-mode");
      const stylesheet = embedded.createElement("link");
      stylesheet.rel = "stylesheet";
      stylesheet.href = embeddedStyles;
      embedded.head.append(stylesheet);
    });

    const foot = document.createElement("footer");
    foot.className = "rn-edisi-window-foot";
    const note = document.createElement("span");
    note.textContent = dmsMenu ? "Modul DMS" : "Modul RN asli · akses mengikuti sesi dan izin RN";
    const fullLink = document.createElement("a");
    fullLink.href = url;
    fullLink.target = "_blank";
    fullLink.rel = "noopener";
    fullLink.textContent = "Buka penuh ↗";
    foot.append(note, fullLink);
    win.append(bar, frame, foot);
    workspace.append(win);

    const taskButton = document.createElement("button");
    taskButton.type = "button";
    taskButton.textContent = title;
    taskButton.title = `Tampilkan ${title}`;
    taskbar.append(taskButton);
    const item = { element: win, taskButton, restore: null, dmsMenu };
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
      if (event.button !== 0 || event.target.closest("button") || win.classList.contains("is-maximized") || window.matchMedia("(max-width: 820px)").matches) return;
      const bounds = workspace.getBoundingClientRect();
      const rect = win.getBoundingClientRect();
      drag = { x: event.clientX, y: event.clientY, left: rect.left - bounds.left + workspace.scrollLeft, top: rect.top - bounds.top + workspace.scrollTop };
      handle.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    handle.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const maxLeft = Math.max(0, workspace.clientWidth - 80);
      const maxTop = Math.max(0, workspace.clientHeight - 45);
      win.style.left = `${Math.min(maxLeft, Math.max(0, drag.left + event.clientX - drag.x))}px`;
      win.style.top = `${Math.min(maxTop, Math.max(0, drag.top + event.clientY - drag.y))}px`;
    });
    const finish = () => { drag = null; };
    handle.addEventListener("pointerup", finish);
    handle.addEventListener("pointercancel", finish);
  }

  window.rnEdisiOpenWindow = createWindow;
  const moduleDialog = document.querySelector("[data-module-dialog]");
  const moduleForm = document.querySelector("[data-module-form]");
  const moduleSelect = document.querySelector("[data-module-select]");
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
    moduleSelect.querySelectorAll("[data-dms-group]").forEach((group) => group.remove());
    for (const agency of [template, "bersama"]) {
      const entries = available.filter((menu) => (agency === "bersama") === (menu.instansi === "bersama"));
      if (!entries.length) continue;
      const group = document.createElement("optgroup");
      group.label = labels[agency];
      group.dataset.dmsGroup = agency;
      entries.forEach((menu) => group.append(new Option(menu.judul, "dms:" + menu.id)));
      moduleSelect.append(group);
    }
  }

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
  }

  templateSelect.addEventListener("change", () => {
    remember(templateSelect.value);
    applyTemplate(templateSelect.value);
  });
  window.addEventListener("rn-dms-session", () => {
    for (const item of windows.values()) {
      if (item.dmsMenu) item.element.querySelector("[data-close]").click();
    }
    refreshTemplate();
  });
  document.querySelector("[data-add-module]")?.addEventListener("click", () => moduleDialog?.showModal());
  moduleForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const route = moduleSelect.value;
    const menu = visible(menus, operationTemplate).find(({ id }) => route === "dms:" + id);
    if (menu) {
      moduleDialog.close();
      window.rnEdisiOpenWindow(menu.judul, "dms-modul.html?menu=" + encodeURIComponent(menu.id), menu.id);
    } else if (moduleRoutes.has(route)) {
      moduleDialog.close();
      createWindow(moduleRoutes.get(route), route);
    }
  });

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
})();
