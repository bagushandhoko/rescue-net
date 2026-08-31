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

function fmtWhen(v) {
  if (!v) return "-";
  const s = String(v).replace("T", " ");
  return s.slice(0, 16);
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

const FN_PAGES = {
  logistics: { label: "Logistik", href: "posko-logistik.html" },
  shelter: { label: "Shelter", href: "shelter-detail.html" },
  kitchen: { label: "Dapur Umum", href: "dapur-umum.html" }
};

function renderFnNav(b) {
  const nav = document.getElementById("poskoFnNav");
  if (!nav) return;
  const fns = (b.functions || []).filter(f => FN_PAGES[f]);
  if (fns.length < 2) { nav.hidden = true; return; }
  const pid = encodeURIComponent(poskoParam());
  const ev = encodeURIComponent(eventParam());
  nav.innerHTML =
    `<span class="rn-fn-label">Fungsi posko:</span>` +
    fns.map(f => {
      const p = FN_PAGES[f];
      const active = p.href === "posko-logistik.html" ? " is-active" : "";
      return `<a class="rn-fn-tab${active}" href="${p.href}?id=${pid}&event=${ev}">${p.label}</a>`;
    }).join("");
  nav.hidden = false;
}

function renderRoleBanner(b) {
  const el = document.getElementById("logistikRoleBanner");
  if (!el) return;
  const role = b.logistics_role;
  if (role === "collector") {
    el.className = "rn-role-banner is-collector";
    el.innerHTML = `<b>Posko Logistik Pengumpul</b> — di daerah aman, tidak melayani korban. Stok di sini dikirim ke posko penerima di daerah bencana.`;
    el.hidden = false;
  } else if (role === "receiver") {
    el.className = "rn-role-banner is-receiver";
    el.innerHTML = `<b>Posko Logistik Penerima</b> — di daerah bencana, melayani ${fmt(b.kpi && b.kpi.jiwa_dilayani || 0)} jiwa.`;
    el.hidden = false;
  } else {
    el.hidden = true;
  }
}

function renderPublicShipments(b) {
  const panel = document.getElementById("publicShipPanel");
  const body = document.getElementById("publicShipBody");
  const cnt = document.getElementById("publicShipCount");
  const rows = b.public_shipments || [];
  if (!panel || !body) return;
  if (!rows.length) { panel.hidden = true; return; }
  if (cnt) cnt.textContent = rows.length;
  body.innerHTML = rows.map(s => `
    <tr>
      <td><b>${safe(s.donor_name)}</b></td>
      <td>${safe(s.item_name)}</td>
      <td>${fmt(s.quantity)} ${safe(s.unit)}</td>
      <td>${s.wave ? "Gel. " + s.wave : (safe(s.ready_at) || "—")}</td>
      <td>${statusChip(s.status)}</td>
    </tr>`).join("");
  panel.hidden = false;
}

function renderKpi(b) {
  const k = b.kpi || {};
  const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  const collector = !!b.is_collector;
  const jiwaCard = document.getElementById("kpiJiwaCard");
  const jiwaEdit = document.getElementById("kpiJiwaEdit");
  if (jiwaCard) jiwaCard.querySelector("span").firstChild.textContent =
    collector ? "Peran Posko " : "Jiwa Dilayani ";
  if (jiwaEdit) jiwaEdit.style.display = collector ? "none" : "";
  set("kpiJiwa", collector ? "Pengumpul" : fmt(k.jiwa_dilayani || 0));
  set("kpiStok", fmt(k.stok_menipis || 0));
  set("kpiKritis", fmt(k.kebutuhan_kritis || 0));
  set("kpiMenuju", fmt(k.bantuan_menuju || 0));
  const h = document.getElementById("kpiKritisHint");
  if (h) h.textContent = `${fmt(k.kebutuhan_terbuka || 0)} kebutuhan terbuka`;
  const hs = document.getElementById("kpiStokHint");
  if (hs) hs.textContent = `${fmt(k.stok_item || 0)} item stok tercatat`;
  const jn = document.getElementById("kpiJiwaHint");
  if (jn) {
    jn.textContent = collector
      ? "posko pengumpul di daerah aman"
      : ((b.posko && b.posko.beneficiary_note) || "jumlah korban dilayani posko");
  }
}

function habisChip(days) {
  if (days === null || days === undefined) return `<span class="rn-muted">—</span>`;
  let cls = "good";
  if (days < 3) cls = "danger";
  else if (days < 7) cls = "warning";
  return `<span class="chip ${cls}">${fmt(days)} hari</span>`;
}

function renderStockCards(b) {
  const body = document.getElementById("urgentNeedsBody");
  const cards = b.stock_cards || [];
  const total = b.stock_cards_total || cards.length;

  const cnt = document.getElementById("urgentNeedsCount");
  if (cnt) cnt.textContent = `${total} item`;
  const shown = document.getElementById("urgentNeedsShown");
  if (shown) shown.textContent = b.detail_allowed
    ? `${cards.length} kartu stok`
    : "Detail dikunci — login sebagai operator posko";
  const more = document.getElementById("urgentNeedsMore");
  if (more) more.href = `posko-detail.html?id=${encodeURIComponent(poskoParam())}&event=${encodeURIComponent(eventParam())}`;

  if (!body) return;
  if (!b.detail_allowed) {
    body.innerHTML = `<tr><td colspan="10" class="rn-muted">Kartu stok hanya tampil untuk operator posko / organisasi yang membuka koordinasi.</td></tr>`;
    return;
  }
  body.innerHTML = cards.length
    ? cards.map(c => `
        <tr>
          <td><b>${safe(c.item)}</b> <small>${safe(c.unit)}</small></td>
          <td>${fmt(c.stok_ada)}</td>
          <td class="rn-in">${c.masuk_7h ? "+" + fmt(c.masuk_7h) : "—"}</td>
          <td class="rn-out">${c.keluar_7h ? "−" + fmt(c.keluar_7h) : "—"}</td>
          <td>${
            c.otw
              ? `<a href="#" class="rn-otw" data-item="${encodeURIComponent(c.item)}">${fmt(c.otw)} (${c.otw_count})</a>`
              : "—"
          }</td>
          <td>${c.kebutuhan ? fmt(c.kebutuhan) : "—"}</td>
          <td class="rn-gap">${c.gap ? fmt(c.gap) : "—"}</td>
          <td>${c.laju_harian ? fmt(c.laju_harian) + "/hari" : "—"}<br><small>${c.laju_sumber === "manual" ? "manual" : c.laju_sumber === "computed" ? "otomatis" : ""}</small></td>
          <td>${habisChip(c.estimasi_habis_hari)}${
            c.estimasi_habis_dengan_otw_hari && c.otw
              ? `<br><small>+OTW: ${fmt(c.estimasi_habis_dengan_otw_hari)} h</small>`
              : ""
          }</td>
          <td><button class="btn ghost mini rn-penuhi" data-item="${encodeURIComponent(c.item)}" data-unit="${encodeURIComponent(c.unit || "")}">Penuhi</button></td>
        </tr>
      `).join("")
    : `<tr><td colspan="10">Belum ada kartu stok.</td></tr>`;

  body.querySelectorAll(".rn-otw").forEach(a => {
    a.addEventListener("click", e => {
      e.preventDefault();
      openIncomingDrawer(decodeURIComponent(a.dataset.item));
    });
  });
  body.querySelectorAll(".rn-penuhi").forEach(btn => {
    btn.addEventListener("click", () => openFulfill(
      decodeURIComponent(btn.dataset.item),
      decodeURIComponent(btn.dataset.unit || "")
    ));
  });
}

function openIncomingDrawer(item) {
  const b = LOGISTIK_BOARD || {};
  const rows = (b.incoming || []).filter(
    f => (f.item_name || "").toLowerCase() === item.toLowerCase()
  );
  const list = rows.length
    ? rows.map(f => `
        <div class="rn-drawer-row">
          <div>
            <b>${safe(f.source_posko)}</b> · ${fmt(f.quantity)} ${safe(f.unit)}
            <br><small>${statusChip(f.flow_status)} · ETA ${fmtWhen(f.eta_final)} · ${safe(f.transport_provider)}</small>
          </div>
          <a class="btn ghost mini" href="${safe(f.distribusi_url)}">Proses distribusi →</a>
        </div>
      `).join("")
    : `<p class="rn-muted">Tidak ada kiriman OTW untuk item ini.</p>`;
  showDrawer(`Bantuan OTW — ${item}`, list);
}

function openFulfill(item, unit) {
  const posko = poskoParam();
  const html = `
    <form id="fulfillForm" class="rn-form">
      <p class="rn-muted">Penawaran ini bisa dari posko pengumpul di daerah aman, atau kiriman warga.</p>
      <label>Item<input value="${safe(item)}" readonly></label>
      <label>Nama donatur / posko pengumpul<input name="donor_name" required></label>
      <label>Jumlah<input name="quantity" type="number" step="0.01" required></label>
      <label>Satuan<input name="unit" value="${safe(unit)}"></label>
      <label>Lokasi pickup<input name="pickup_location" placeholder="gudang / alamat"></label>
      <label>Kontak<input name="contact" placeholder="No. HP / email"></label>
      <div class="form-actions"><button class="btn primary" type="submit">Kirim penawaran</button>
      <span class="form-message" id="fulfillMsg"></span></div>
    </form>`;
  showDrawer(`Penuhi kebutuhan — ${item}`, html);
  const form = document.getElementById("fulfillForm");
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const msg = document.getElementById("fulfillMsg");
    msg.textContent = "Mengirim…";
    try {
      // find an open need for this item at this posko
      const board = LOGISTIK_BOARD || {};
      let needRef = null;
      try {
        const on = await RN_FRAPPE.call(
          "rescue_net.api_control_centre.logistik_open_needs",
          { disaster_event: eventParam() }
        );
        const list = (on && on.needs) || [];
        const hit = list.find(x =>
          x.posko === board.posko?.name &&
          (x.item || "").toLowerCase() === item.toLowerCase()
        ) || list.find(x => (x.item || "").toLowerCase() === item.toLowerCase());
        needRef = hit && (hit.id || hit.name);
      } catch (e2) {}
      if (!needRef) { msg.textContent = "Tidak ada kebutuhan terbuka yang cocok untuk item ini."; return; }
      const r = await RN_FRAPPE.call(
        "rescue_net.api_control_centre.fulfill_need",
        {
          need: needRef,
          donor_name: form.donor_name.value.trim(),
          quantity: Number(form.quantity.value || 0),
          unit: form.unit.value.trim(),
          pickup_location: form.pickup_location.value.trim(),
          contact: form.contact.value.trim(),
        },
        { method: "POST" }
      );
      msg.textContent = r.message || "Tercatat.";
      form.reset();
      setTimeout(() => { hideDrawer(); loadBoard(); }, 1200);
    } catch (err) {
      msg.textContent = err.message || String(err);
    }
  });
}

function showDrawer(title, html) {
  let d = document.getElementById("rnDrawer");
  if (!d) {
    d = document.createElement("div");
    d.id = "rnDrawer";
    d.className = "rn-drawer";
    d.innerHTML = `<div class="rn-drawer-card"><header><b id="rnDrawerTitle"></b><button id="rnDrawerX" type="button">×</button></header><div id="rnDrawerBody"></div></div>`;
    document.body.appendChild(d);
    d.addEventListener("click", e => { if (e.target === d) hideDrawer(); });
    d.querySelector("#rnDrawerX").addEventListener("click", hideDrawer);
  }
  d.querySelector("#rnDrawerTitle").textContent = title;
  d.querySelector("#rnDrawerBody").innerHTML = html;
  d.classList.add("is-open");
}
function hideDrawer() {
  const d = document.getElementById("rnDrawer");
  if (d) d.classList.remove("is-open");
}

async function editBeneficiary() {
  const posko = poskoParam();
  const cur = (LOGISTIK_BOARD && LOGISTIK_BOARD.posko && LOGISTIK_BOARD.posko.beneficiary_count) || 0;
  const val = prompt("Jumlah jiwa yang dilayani posko ini:", cur);
  if (val === null) return;
  const note = prompt("Catatan (opsional):",
    (LOGISTIK_BOARD && LOGISTIK_BOARD.posko && LOGISTIK_BOARD.posko.beneficiary_note) || "");
  try {
    await RN_FRAPPE.call(
      "rescue_net.api_control_centre.set_posko_beneficiary",
      { posko, count: Number(val || 0), note: note || "" },
      { method: "POST" }
    );
    loadBoard();
  } catch (err) {
    setStatus("Gagal simpan jiwa dilayani: " + (err.message || err));
  }
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

    renderFnNav(b);
    renderShareBanner(b);
    renderRoleBanner(b);
    renderKpi(b);
    renderStockCards(b);
    renderPublicShipments(b);
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

  document.getElementById("kpiJiwaEdit")?.addEventListener("click", editBeneficiary);

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
