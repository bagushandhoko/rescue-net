(() => {
  "use strict";
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

  function createWindow(title, url) {
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
    frame.src = url;
    frame.addEventListener("load", () => {
      try { frame.contentDocument.documentElement.classList.add("rn-window-mode"); } catch (_) { /* Keep module usable if embedding is restricted. */ }
    });

    const foot = document.createElement("footer");
    foot.className = "rn-edisi-window-foot";
    const note = document.createElement("span");
    note.textContent = "Modul RN asli · akses mengikuti sesi dan izin RN";
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
    const item = { element: win, taskButton, restore: null };
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

  const moduleDialog = document.querySelector("[data-module-dialog]");
  const moduleForm = document.querySelector("[data-module-form]");
  const moduleSelect = document.querySelector("[data-module-select]");
  document.querySelector("[data-add-module]")?.addEventListener("click", () => moduleDialog?.showModal());
  moduleForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const route = moduleSelect?.value;
    if (!moduleRoutes.has(route)) return;
    moduleDialog.close();
    createWindow(moduleRoutes.get(route), route);
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
  const shell = document.querySelector(".rn-dms-shell");
  const agencyLabels = { bnpb: "Profil BNPB · contoh struktur", tni: "Profil TNI · contoh struktur", pmi: "Profil PMI · contoh struktur", combined: "Profil multi-instansi · tampilan terpisah" };
  const agencyNames = { bnpb: "BNPB", tni: "TNI PRCPB", pmi: "PMI Kemanusiaan", combined: "Kombinasi" };
  function setAgency(agency) {
    if (!shell || !agencyLabels[agency]) return;
    shell.dataset.agency = agency;
    document.querySelectorAll("[data-agency-choice]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.agencyChoice === agency));
    });
    document.querySelectorAll("[data-agency-label]").forEach((node) => { node.textContent = agencyLabels[agency]; });
    document.querySelectorAll("[data-agency-footer]").forEach((node) => { node.textContent = agencyNames[agency]; });
  }
  document.querySelectorAll("[data-agency-choice]").forEach((button) => {
    button.addEventListener("click", () => setAgency(button.dataset.agencyChoice));
  });
  document.querySelector("[data-return-map]")?.addEventListener("click", () => setAgency("bnpb"));
  updateStatus();
})();
