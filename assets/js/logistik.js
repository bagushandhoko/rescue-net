/* Posko Logistik dashboard — matches the DMS mock-up.
   Data from rescue_net.api_control_centre.logistik_board (guest, visibility-gated).
   The two create forms (collapsed drawer) still hit the login-scoped
   api_logistics.* endpoints for operators. */

let LOGISTIK_BOARD = null;
let MOV_TAB = "masuk";

function safe(v) {
  return (v === null || v === undefined || v === "") ? "-" : v;
}

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmt(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return safe(v);
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(n);
}

function priorityChip(priority) {
  const p = String(priority || "").toLowerCase();
  let cls = "neutral";
  let label = priority || "normal";
  if (p === "critical") { cls = "danger"; label = "Sangat Tinggi"; }
  else if (p === "urgent" || p === "high") { cls = "warning"; label = "Tinggi"; }
  else if (p === "normal") { label = "Sedang"; }
  return `<span class="chip ${cls}">${safe(label)}</span>`;
}

function statusChip(status) {
  const s = String(status || "").toLowerCase();
  let cls = "neutral";
  if (/(received|completed|diterima|closed|arrived)/.test(s)) cls = "good";
  else if (/(transit|dispatch|jalan|pickup)/.test(s)) cls = "warning";
  return `<span class="chip ${cls}">${safe(status)}</span>`;
}

function eventParam() {
  const p = new URLSearchParams(location.search);
  let ev = p.get("event") || p.get("disaster_event_id");
  if (!ev) {
    try { ev = localStorage.getItem("rn_active_event"); } catch (e) {}
  }
  return String(ev || "event-sim-001").replace(/^disaster_events:/, "");
}

function poskoParam() {
  const p = new URLSearchParams(location.search);
  const sel = document.getElementById("logistikPoskoSelect");
  return (
    p.get("id") ||
    p.get("posko") ||
    (sel && sel.value) ||
    ""
  );
}

function setStatus(msg) {
  const el = document.querySelector("[data-rn-logistik-status]");
  if (el) el.textContent = msg || "";
}


/* ---------- posko selector ---------- */

async function loadPoskoOptions() {
  const sel = document.getElementById("logistikPoskoSelect");
  if (!sel) return;

  let points = [];
  try {
    const res = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.event_poskos",
      { disaster_event: eventParam() }
    );
    points = Array.isArray(res) ? res : (res.points || []);
  } catch (e) {
    points = [];
  }

  if (!points.length) {
    sel.innerHTML = `<option value="${poskoParam() || ""}">${poskoParam() || "posko"}</option>`;
    return;
  }

  // logistics-type poskos first
  points.sort((a, b) => {
    const la = /logist|gudang|warehouse/i.test(a.posko_type || "") ? 0 : 1;
    const lb = /logist|gudang|warehouse/i.test(b.posko_type || "") ? 0 : 1;
    return la - lb;
  });

  const want = poskoParam();
  sel.innerHTML = points
    .map(pt => {
      const id = pt.posko_id || pt.id || pt.name;
      const selAttr = id === want ? " selected" : "";
      return `<option value="${id}"${selAttr}>${safe(pt.name)}</option>`;
    })
    .join("");

  if (!want && sel.options.length) sel.selectedIndex = 0;

  sel.addEventListener("change", () => loadBoard());
}


/* ---------- render ---------- */

function renderShareBanner(b) {
  const el = document.getElementById("logistikShareBanner");
  if (!el) return;
  const org = (b.organization && b.organization.title) || "organisasi ini";
  if (b.detail_allowed) {
    el.className = "rn-share-banner is-full";
    el.innerHTML = `<b>Detail penuh</b> — ${safe(org)} membuka koordinasi logistik penuh.`;
  } else {
    el.className = "rn-share-banner is-summary";
    el.innerHTML =
      `<b>Ringkasan saja</b> — ${safe(org)} menutup koordinasi detail. ` +
      `KPI &amp; sebagian kebutuhan ditampilkan; login sebagai operator ${safe(org)} untuk data penuh.`;
  }
  el.hidden = false;
}

function renderKpi(b) {
  const k = b.kpi || {};
  const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  set("kpiJiwa", fmt(k.jiwa_dilayani || 0));
  set("kpiStok", fmt(k.stok_menipis || 0));
  set("kpiKritis", fmt(k.kebutuhan_kritis || 0));
  set("kpiMenuju", fmt(k.bantuan_menuju || 0));
  const h = document.getElementById("kpiKritisHint");
  if (h) h.textContent = `${fmt(k.kebutuhan_terbuka || 0)} kebutuhan terbuka`;
  const hs = document.getElementById("kpiStokHint");
  if (hs) hs.textContent = `${fmt(k.stok_item || 0)} item stok tercatat`;
}

function renderUrgentNeeds(b) {
  const body = document.getElementById("urgentNeedsBody");
  const rows = b.urgent_needs || [];
  const total = b.urgent_needs_total || rows.length;

  const cnt = document.getElementById("urgentNeedsCount");
  if (cnt) cnt.textContent = `${total} item`;

  const shown = document.getElementById("urgentNeedsShown");
  if (shown) shown.textContent = `Menampilkan ${rows.length} dari ${total} item`;

  const more = document.getElementById("urgentNeedsMore");
  if (more) more.href = `posko-detail.html?id=${encodeURIComponent(poskoParam())}&event=${encodeURIComponent(eventParam())}`;

  if (!body) return;
  body.innerHTML = rows.length
    ? rows.map(n => `
        <tr>
          <td>${safe(n.item_name)} <small>${safe(n.unit)}</small></td>
          <td>${fmt(n.stok_tersedia)} ${safe(n.unit)}</td>
          <td class="rn-gap">${fmt(n.gap)}</td>
          <td>${safe(n.estimasi_habis)}</td>
          <td>${safe(n.waktu_harus_tiba)}</td>
          <td>${priorityChip(n.priority)}</td>
        </tr>
      `).join("")
    : `<tr><td colspan="6">Belum ada kebutuhan mendesak.</td></tr>`;
}

function renderMovements(b) {
  const body = document.getElementById("movBody");
  const head = document.getElementById("movWhoHead");
  const rows = MOV_TAB === "masuk" ? (b.movements_in || []) : (b.movements_out || []);
  const whoKey = MOV_TAB === "masuk" ? "dari" : "tujuan";
  if (head) head.textContent = MOV_TAB === "masuk" ? "Dari" : "Tujuan";

  if (!body) return;
  body.innerHTML = rows.length
    ? rows.map(m => `
        <tr>
          <td>${safe(m[whoKey])}</td>
          <td>${safe(m.item_name)}</td>
          <td>${fmt(m.quantity)} ${safe(m.unit)}</td>
          <td>${statusChip(m.status)}</td>
        </tr>
      `).join("")
    : `<tr><td colspan="4">Belum ada pergerakan ${MOV_TAB}.</td></tr>`;
}

function renderTrace(b) {
  const el = document.getElementById("traceCard");
  if (!el) return;
  const t = b.trace;
  if (!t) {
    el.innerHTML = `<p class="rn-muted">Belum ada pengiriman menuju posko.</p>`;
    return;
  }
  const steps = ["Gudang", "Sortir", "Perjalanan", "Tiba"];
  const dots = steps
    .map((s, i) => `<span class="rn-trace-dot${(i + 1) <= t.step ? " is-done" : ""}">${s}</span>`)
    .join("<i></i>");
  el.innerHTML = `
    <div class="rn-trace-line">
      <span>Dari</span><b>${safe(t.dari)}</b>
    </div>
    <div class="rn-trace-line">
      <span>Item</span><b>${safe(t.item_name)} — ${fmt(t.quantity)} ${safe(t.unit)}</b>
    </div>
    <div class="rn-trace-line">
      <span>No. Resi</span><b>${safe(t.resi)}</b>
    </div>
    <div class="rn-trace-line">
      <span>Status</span>${statusChip(t.status)}
    </div>
    <div class="rn-trace-steps">${dots}</div>
  `;
}

function renderConversions(b) {
  const el = document.getElementById("conversionBody");
  if (!el) return;
  const rows = b.conversions || [];
  el.innerHTML = rows.length
    ? rows.map(c => `
        <div class="rn-conv-row">
          <b>${safe(c.item)}</b>
          <span>1 ${safe(c.base_unit)} = ${fmt(c.factor)} ${safe(c.target_unit)}</span>
        </div>
      `).join("")
    : `<p class="rn-muted">Tidak ada referensi konversi.</p>`;
}

function wireUploadLinks() {
  const ev = encodeURIComponent(eventParam());
  const pk = encodeURIComponent(poskoParam());
  const href = `evidence.html?event=${ev}&posko=${pk}`;
  ["uploadStok", "uploadPosko"].forEach(id => {
    const a = document.getElementById(id);
    if (a) a.href = href;
  });
}


/* ---------- load ---------- */

async function loadBoard() {
  const posko = poskoParam();
  if (!posko) { setStatus("Pilih posko."); return; }

  setStatus("Memuat data logistik…");
  try {
    const b = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.logistik_board",
      { posko, disaster_event: eventParam() }
    );
    LOGISTIK_BOARD = b;

    renderShareBanner(b);
    renderKpi(b);
    renderUrgentNeeds(b);
    renderMovements(b);
    renderTrace(b);
    renderConversions(b);
    wireUploadLinks();

    const upd = document.getElementById("logistikUpdated");
    if (upd) {
      upd.textContent =
        "Terakhir diperbarui " +
        new Date().toLocaleString("id-ID", { hour12: false });
    }

    // prefill the drawer forms
    document.querySelectorAll(
      "[data-rn-create-logistic-need] [name='disaster_event_id']," +
      "[data-rn-create-aid-offer] [name='disaster_event_id']"
    ).forEach(i => { if (!i.value) i.value = eventParam(); });
    const nodeInput = document.querySelector(
      "[data-rn-create-logistic-need] [name='node_id']"
    );
    if (nodeInput && !nodeInput.value) nodeInput.value = posko;

    setStatus(
      b.detail_allowed
        ? "Data logistik dimuat (detail penuh)."
        : "Data logistik dimuat (ringkasan — koordinasi organisasi tertutup)."
    );
  } catch (err) {
    setStatus("Gagal memuat: " + (err && err.message || err));
  }
}


/* ---------- create forms (operator only) ---------- */

function getLogisticsPosko() {
  return (
    poskoParam() ||
    document.querySelector("[data-rn-create-logistic-need] [name='node_id']")?.value ||
    ""
  );
}

function setupLogisticNeedForm() {
  const form = document.querySelector("[data-rn-create-logistic-need]");
  const msg = document.querySelector("[data-rn-logistic-message]");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      if (msg) msg.textContent = "Menyimpan kebutuhan…";
      await RN_FRAPPE.call(
        "rescue_net.api_logistics.create_need",
        {
          posko: form.node_id.value.trim() || getLogisticsPosko(),
          item_text: form.item_name.value.trim(),
          quantity: Number(form.quantity_needed.value || 0),
          unit: form.unit.value.trim(),
          quantity_mode: "known",
          urgency: form.priority.value,
          needed_before: form.needed_before.value.trim()
        },
        { method: "POST" }
      );
      if (msg) msg.textContent = "Kebutuhan tersimpan.";
      form.reset();
      await loadBoard();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

function setupAidOfferForm() {
  const form = document.querySelector("[data-rn-create-aid-offer]");
  const msg = document.querySelector("[data-rn-aid-message]");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      if (msg) msg.textContent = "Menyimpan bantuan…";
      await RN_FRAPPE.call(
        "rescue_net.api_logistics.create_aid_offer",
        {
          target_posko: getLogisticsPosko(),
          donor_name: form.donor_name.value.trim(),
          item_text: form.item_name.value.trim(),
          quantity: Number(form.quantity.value || 0),
          unit: form.unit.value.trim(),
          quantity_mode: "known",
          pickup_location: form.pickup_location.value.trim()
        },
        { method: "POST" }
      );
      if (msg) msg.textContent = "Bantuan tersimpan.";
      form.reset();
      await loadBoard();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}


/* ---------- boot ---------- */

async function boot() {
  if (!window.RN_FRAPPE) {
    setStatus("Frappe client tidak tersedia.");
    return;
  }

  document.getElementById("movTabMasuk")?.addEventListener("click", () => {
    MOV_TAB = "masuk";
    document.getElementById("movTabMasuk").classList.add("is-active");
    document.getElementById("movTabKeluar").classList.remove("is-active");
    if (LOGISTIK_BOARD) renderMovements(LOGISTIK_BOARD);
  });
  document.getElementById("movTabKeluar")?.addEventListener("click", () => {
    MOV_TAB = "keluar";
    document.getElementById("movTabKeluar").classList.add("is-active");
    document.getElementById("movTabMasuk").classList.remove("is-active");
    if (LOGISTIK_BOARD) renderMovements(LOGISTIK_BOARD);
  });

  setupLogisticNeedForm();
  setupAidOfferForm();

  try {
    await loadPoskoOptions();
  } catch (e) {
    setStatus("Gagal memuat daftar posko: " + (e && e.message || e));
  }
  await loadBoard();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
