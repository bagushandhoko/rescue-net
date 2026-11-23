(() => {
  "use strict";

  const api = "/rescue-net-frappe/api/method/";
  const catalogUrl = new URL("../data/dms-menu.json?v=dms-20261122e", document.currentScript.src);
  const storageKey = "rn_dms_operation_template";
  const labels = Object.freeze({ umum: "Umum", bnpb: "BNPB-BPBD", tni: "TNI/POLRI", pmi: "PMI", kementerian: "Kementerian", bersama: "Bersama" });
  // Di RN (asal=rn) template HANYA dari organisasi pengguna (API); tanpa pilihan manual.
  const strict = new URLSearchParams(location.search).get("asal") === "rn" || window.RN_DMS_STRICT === true;
  // CT202 (owner 2026-11-22): hanya untuk instansi, tanpa "Umum". RN (strict) tetap punya "Umum".
  const templates = strict ? ["umum", "bnpb", "tni", "pmi", "kementerian"] : ["bnpb", "tni", "pmi", "kementerian"];
  const valid = (value) => templates.includes(value);
  let catalog;

  async function getJSON(url) {
    const response = await fetch(url, {
      credentials: "same-origin", headers: { Accept: "application/json" },
      cache: "no-store", signal: AbortSignal.timeout(8000)
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function load() {
    catalog ??= getJSON(catalogUrl).catch((error) => { catalog = undefined; throw error; });
    return catalog;
  }

  function localTemplate() {
    try {
      const value = localStorage.getItem(storageKey);
      if (valid(value)) return value;
    } catch (_) {}
    return templates[0];
  }

  function remember(value) {
    if (!valid(value)) return;
    try { localStorage.setItem(storageKey, value); } catch (_) {}
  }

  async function resolveTemplate() {
    try {
      const { message } = await getJSON(api + "rescue_net.api_org_profile.my_operation_template");
      if (valid(message?.template) && (strict || message.template !== "umum")) return { value: message.template, managed: true };
    } catch (_) {}
    return { value: strict ? "umum" : localTemplate(), managed: false };
  }

  function visible(menus, template) {
    return menus.filter((menu) => menu.instansi === "bersama" || menu.instansi === template
      || (menu.template_tambahan || []).includes(template));
  }

  // Simulasi DMS (owner 23 Nov 2026): TERPISAH dari simulasi RN. Pilihan disimpan di localStorage "dms_tampilan"
  // (bukan cookie rn_tampilan), data dari assets/data/dms-simulasi*.json. Modul RN di jendela tetap data RN.
  const VIEW_KEY = "dms_tampilan";
  const view = {
    get() {
      try { return localStorage.getItem(VIEW_KEY) === "simulasi" ? "simulasi" : "riil"; } catch (_) { return "riil"; }
    },
    set(value) {
      const v = value === "simulasi" ? "simulasi" : "riil";
      try { localStorage.setItem(VIEW_KEY, v); } catch (_) {}
      window.dispatchEvent(new CustomEvent("dms-view-change", { detail: { view: v } }));
      return v;
    },
    isSim() { return view.get() === "simulasi"; }
  };
  const simCache = {};
  function loadSim(name = "dms-simulasi.json") {
    simCache[name] ??= getJSON(new URL("../data/" + name + "?v=sim-20261123", catalogUrl).href)
      .catch((error) => { delete simCache[name]; throw error; });
    return simCache[name];
  }
  // Lintas jendela (same-origin iframe): perubahan dari halaman lain ikut terdengar.
  window.addEventListener("storage", (e) => {
    if (e.key === VIEW_KEY) window.dispatchEvent(new CustomEvent("dms-view-change", { detail: { view: view.get() } }));
  });

  window.RNDmsMenus = { strict, templates, labels, load, resolveTemplate, remember, visible, getJSON, api, view, loadSim };
})();
