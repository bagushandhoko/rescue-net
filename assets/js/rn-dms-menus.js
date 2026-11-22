(() => {
  "use strict";

  const api = "/rescue-net-frappe/api/method/";
  const catalogUrl = new URL("../data/dms-menu.json?v=dms-20261122", document.currentScript.src);
  const storageKey = "rn_dms_operation_template";
  const labels = Object.freeze({ umum: "Umum", bnpb: "BNPB-BPBD", tni: "TNI", pmi: "PMI", bersama: "Bersama" });
  const valid = (value) => value !== "bersama" && Object.hasOwn(labels, value);
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
    return "umum";
  }

  function remember(value) {
    if (!valid(value)) return;
    try { localStorage.setItem(storageKey, value); } catch (_) {}
  }

  async function resolveTemplate() {
    try {
      const { message } = await getJSON(api + "rescue_net.api_org_profile.my_operation_template");
      if (valid(message?.template)) return { value: message.template, managed: true };
    } catch (_) {}
    return { value: localTemplate(), managed: false };
  }

  function visible(menus, template) {
    return menus.filter((menu) => menu.instansi === "bersama" || menu.instansi === template);
  }

  window.RNDmsMenus = { labels, load, resolveTemplate, remember, visible, getJSON, api };
})();
