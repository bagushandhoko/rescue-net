(async () => {
  "use strict";

  const find = (selector) => document.querySelector(selector);
  const id = new URLSearchParams(location.search).get("menu");
  const status = find("[data-dms-status]");
  const { load, resolveTemplate, visible } = window.RNDmsMenus;
  const form = find("[data-dms-form]");
  const back = find("[data-dms-back]");

  if (window.RNDmsMenus.strict) {
    back.href = "menu-instansi.html";
    back.target = "_self";
    back.textContent = "← Kembali ke Menu Instansi";
  }

  if (parent !== window) {
    back.addEventListener("click", (event) => {
      const frame = window.frameElement;
      if (!frame?.closest(".rn-edisi-window")) return;
      event.preventDefault();
      frame.closest(".rn-edisi-window").querySelector("[data-close]").click();
    });
  }

  function inputFor(field) {
    if (field.jenis === "teks_panjang") return document.createElement("textarea");
    if (field.jenis === "pilihan" || field.jenis === "ya_tidak") {
      const select = document.createElement("select");
      const choices = field.jenis === "ya_tidak" ? ["Ya", "Tidak"] : field.pilihan;
      select.add(new Option("Pilih…", ""));
      for (const choice of choices) select.add(new Option(choice, choice));
      return select;
    }
    const input = document.createElement("input");
    const types = { angka: "number", tanggal: "date", waktu: "time" };
    input.type = types[field.jenis] || "text";
    if (field.jenis === "angka") input.step = "any";
    return input;
  }

  function appendField(field, index) {
    const label = document.createElement("label");
    const control = inputFor(field);
    control.name = field.id;
    control.id = "dms-field-" + index;
    control.required = field.wajib;
    control.autocomplete = "off";
    label.htmlFor = control.id;
    label.textContent = field.label + (field.wajib ? " *" : "");
    label.append(control);
    find("[data-dms-fields]").append(label);
  }

  function renderRows(columns, rows) {
    const header = find("thead tr");
    const body = find("tbody");
    for (const column of columns) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = column.label;
      header.append(cell);
    }
    for (const record of rows) {
      const row = body.insertRow();
      for (const column of columns) row.insertCell().textContent = record[column.id] ?? "—";
    }
  }

  try {
    const template = parent !== window && window.frameElement?.dataset.dmsTemplate;
    const [menus, selection] = await Promise.all([load(), template ? { value: template } : resolveTemplate()]);
    const menu = visible(menus, selection.value).find((entry) => entry.id === id);
    if (!menu) {
      status.textContent = "Modul tidak ditemukan atau berada di luar template operasi ini.";
      return;
    }
    document.title = menu.judul + " · DMS";
    find("[data-dms-title]").textContent = menu.judul;
    find("[data-dms-summary]").textContent = menu.ringkas;
    const badge = find("[data-dms-classification]");
    badge.textContent = menu.klasifikasi;
    badge.dataset.level = menu.klasifikasi;
    badge.hidden = false;
    menu.isian.forEach(appendField);
    const recordFields = menu.isian.slice(0, 6);
    function renderRecords(records, notice) {
      const head = find("[data-dms-records] thead tr");
      const body = find("[data-dms-records] tbody");
      head.replaceChildren(); body.replaceChildren();
      for (const field of recordFields) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = field.label; head.append(cell);
      }
      for (const record of records) {
        const row = body.insertRow();
        for (const field of recordFields) row.insertCell().textContent = record.data?.[field.id] ?? "—";
      }
      find("[data-dms-records-note]").textContent = notice || (records.length ? records.length + " catatan tersimpan." : "Belum ada catatan tersimpan.");
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      const record = Object.fromEntries([...new FormData(form)].filter(([, value]) => String(value).trim() !== ""));
      const result = await window.RNEdisiData.save(menu.id, record);
      find("[data-dms-save]").textContent = result.notice;
      button.disabled = false;
      if (result.saved) {
        form.reset();
        const fresh = await window.RNEdisiData.list(menu.id);
        renderRecords(fresh.records || [], fresh.recordNotice);
      }
    });
    status.hidden = true;
    find("[data-dms-content]").hidden = false;
    const result = await window.RNEdisiData.list(menu.id);
    renderRows(menu.kolom, result.rows);
    find("[data-dms-source]").textContent = result.notice;
    renderRecords(result.records || [], result.recordNotice);
  } catch (_) {
    status.hidden = false;
    status.textContent = "Modul belum dapat dimuat. Coba muat ulang halaman.";
  }
})();
