/* Posko Logistik dashboard — matches the DMS mock-up.
   Data from rescue_net.api_control_centre.logistik_board (guest, visibility-gated).
   The two create forms (collapsed drawer) still hit the login-scoped
   api_logistics.* endpoints for operators. */

let LOGISTIK_BOARD = null;
let MOV_TAB = "masuk";
let KATEGORI = "";

/* Coarse item categories so the "Kategori" filter in the topbar can narrow
   both the Kebutuhan Mendesak table and the Kartu Stok Rinci table. */
function itemCategory(name) {
  const s = String(name || "").toLowerCase();
  if (/(air|minum|mineral|galon|aqua)/.test(s)) return "Air & Minuman";
  if (/(beras|mie|instan|sembako|makan|nasi|biskuit|roti|gula|garam|minyak|susu|pangan|lauk)/.test(s)) return "Pangan";
  if (/(selimut|pakaian|baju|sandang|terpal|tenda|tikar|matras|seprai)/.test(s)) return "Sandang & Hunian";
  if (/(obat|medis|p3k|masker|perban|antiseptik|vitamin|infus|oralit)/.test(s)) return "Obat & Medis";
  if (/(popok|pembalut|sabun|pasta|higien|hygiene|sanitasi|tissue|diapers)/.test(s)) return "Higienis";
  return "Lainnya";
}

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

// The <select> starts out with a literal "Memuat…" placeholder <option> (no
// value attribute, so .value falls back to its text). If that ever leaks
// into poskoParam() — e.g. the posko-list call failed before the select was
// populated — it must never be treated as a real posko id, and must never
// get written back into the URL (loadBoard() does that via replaceState),
// or the page gets permanently stuck on a bogus ?id= that can never resolve.
const POSKO_PLACEHOLDER = "Memuat…";

function poskoParam() {
  const p = new URLSearchParams(location.search);
  const sel = document.getElementById("logistikPoskoSelect");
  // Clean each candidate individually (not the final result) so a bad
  // placeholder in the URL still falls through to a real value from the
  // select, instead of short-circuiting the whole lookup to "".
  const clean = v => (v && v !== POSKO_PLACEHOLDER ? v : "");
  return (
    clean(p.get("id")) ||
    clean(p.get("posko")) ||
    clean(sel && sel.value) ||
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
  for (let attempt = 0; attempt < 2 && !points.length; attempt++) {
    if (attempt > 0) await new Promise(r => setTimeout(r, 800));
    try {
      const res = await RN_FRAPPE.call(
        "rescue_net.api_control_centre.event_poskos",
        { disaster_event: eventParam() }
      );
      points = Array.isArray(res) ? res : (res.points || []);
    } catch (e) {
      points = [];
    }
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

/* The merged-posko function switcher now lives in the sidebar top group
   (rn-navigation-v2.js → mountPoskoFunctionGroup). */

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
  if (jiwaCard) jiwaCard.querySelector("span:not(.kpi-icon)").firstChild.textContent =
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

function renderKategoriOptions(b) {
  const sel = document.getElementById("logistikKategori");
  if (!sel) return;
  const names = []
    .concat((b.urgent_needs || []).map(r => r.item_name))
    .concat((b.stock_cards || []).map(c => c.item));
  const cats = Array.from(new Set(names.map(itemCategory))).sort();
  if (KATEGORI && !cats.includes(KATEGORI)) KATEGORI = "";
  const cur = KATEGORI;
  sel.innerHTML =
    `<option value="">Semua Kategori</option>` +
    cats.map(c => `<option value="${c}"${c === cur ? " selected" : ""}>${c}</option>`).join("");
}

function etaChip(txt) {
  const s = String(txt || "").trim();
  if (!s || s === "-") return `<span class="rn-muted">—</span>`;
  const cls = /jam|hari ini|hr ini|<\s*24/i.test(s) ? "warning" : "neutral";
  return `<span class="chip ${cls}">${safe(s)}</span>`;
}

function habisDot(txt) {
  const s = String(txt || "").trim();
  if (!s || s === "-") return `<span class="rn-muted">—</span>`;
  const m = s.match(/(\d+(?:[.,]\d+)?)\s*(jam|hari)/i);
  let cls = "mid";
  if (m) {
    const n = parseFloat(m[1].replace(",", "."));
    const isJam = /jam/i.test(m[2]);
    if (isJam || (!isJam && n < 3)) cls = "hi";
    else if (!isJam && n < 7) cls = "mid";
    else cls = "lo";
  }
  return `<span class="rn-habis"><i class="rn-habis-dot ${cls}"></i>${safe(s)}</span>`;
}

function renderUrgentNeeds(b) {
  const body = document.getElementById("urgentNeedsBody");
  const all = b.urgent_needs || [];
  const rows = KATEGORI ? all.filter(r => itemCategory(r.item_name) === KATEGORI) : all;
  const total = b.urgent_needs_total || all.length;

  const cnt = document.getElementById("urgentNeedsCount");
  if (cnt) cnt.textContent = `${total} item`;

  const shown = document.getElementById("urgentNeedsShown");
  if (shown) {
    shown.textContent = KATEGORI
      ? `Menampilkan ${rows.length} dari ${total} item · ${KATEGORI}`
      : `Menampilkan ${Math.min(all.length, total)} dari ${total} item`;
  }

  const more = document.getElementById("urgentNeedsMore");
  if (more) more.href =
    `posko-detail.html?id=${encodeURIComponent(poskoParam())}&event=${encodeURIComponent(eventParam())}`;

  if (!body) return;
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6" class="rn-muted">${
      KATEGORI ? `Tidak ada kebutuhan mendesak untuk kategori "${safe(KATEGORI)}".`
               : "Tidak ada kebutuhan mendesak yang tercatat."
    }</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(r => `
    <tr>
      <td><b>${safe(r.item_name)}</b> <small>${safe(r.unit)}</small></td>
      <td>${fmt(r.stok_tersedia)} ${safe(r.unit)}</td>
      <td class="rn-gap">${r.gap ? fmt(r.gap) + " " + safe(r.unit) : "—"}</td>
      <td>${habisDot(r.estimasi_habis)}</td>
      <td>${etaChip(r.waktu_harus_tiba)}</td>
      <td>${priorityChip(r.priority)}</td>
    </tr>
  `).join("");

  if (!b.detail_allowed) {
    body.insertAdjacentHTML("beforeend",
      `<tr><td colspan="6" class="rn-muted">Ringkasan koordinasi — login sebagai operator posko untuk daftar penuh.</td></tr>`);
  }
}

function renderStockCards(b) {
  const body = document.getElementById("stockCardsBody");
  const all = b.stock_cards || [];
  const cards = KATEGORI ? all.filter(c => itemCategory(c.item) === KATEGORI) : all;
  const total = b.stock_cards_total || all.length;

  const cnt = document.getElementById("stockCardsCount");
  if (cnt) cnt.textContent = `${total} item`;
  const shown = document.getElementById("stockCardsShown");
  if (shown) shown.textContent = b.detail_allowed
    ? (KATEGORI ? `${cards.length} dari ${all.length} kartu stok · ${KATEGORI}` : `${all.length} kartu stok`)
    : "Detail dikunci — login sebagai operator posko";
  const more = document.getElementById("stockCardsMore");
  if (more) more.href = `posko-detail.html?id=${encodeURIComponent(poskoParam())}&event=${encodeURIComponent(eventParam())}`;

  if (!body) return;
  if (!b.detail_allowed) {
    body.innerHTML = `<tr><td colspan="10" class="rn-muted">Kartu stok hanya tampil untuk operator posko / organisasi yang membuka koordinasi.</td></tr>`;
    return;
  }
  if (!cards.length && KATEGORI) {
    body.innerHTML = `<tr><td colspan="10" class="rn-muted">Tidak ada kartu stok untuk kategori "${safe(KATEGORI)}".</td></tr>`;
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
  const rows = item
    ? (b.incoming || []).filter(
        f => (f.item_name || "").toLowerCase() === item.toLowerCase()
      )
    : (b.incoming || []);
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
    : `<p class="rn-muted">${item ? "Tidak ada kiriman OTW untuk item ini." : "Belum ada bantuan yang sedang menuju posko."}</p>`;
  showDrawer(item ? `Bantuan OTW — ${item}` : "Bantuan Menuju Posko (OTW)", list);
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
  const steps = [
    { label: "Gudang", icon: "home" },
    { label: "Sortir", icon: "package" },
    { label: "Perjalanan", icon: "truck" },
    { label: "Tiba", icon: "map-pin" },
  ];
  const nodes = steps
    .map((s, i) => {
      const n = i + 1;
      const nodeCls = n < t.step ? " is-done" : n === t.step ? " is-current" : "";
      const node = `<span class="rn-trace-node${nodeCls}" title="${safe(s.label)}"><span class="rn-trace-icon" data-icon="${s.icon}"></span></span>`;
      // the segment BEFORE this node (none before the first) is filled once
      // the walk has reached this node.
      const seg = i === 0 ? "" : `<i class="rn-trace-seg${n <= t.step ? " is-done" : ""}"></i>`;
      return seg + node;
    })
    .join("");
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
    <div class="rn-trace-steps">${nodes}</div>
  `;
  if (window.RNIconFill) window.RNIconFill(el);
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

/* ---------- Bukti Kondisi & Lapangan (photos, same feed as Control Centre) ---------- */

/* Seeded/uploaded captions are tagged "[Kondisi Stok] …" / "[Kondisi Posko] …";
   everything else is general field evidence. */
function buktiCat(row) {
  const c = String(row && (row.evidence_caption || row.caption || row.title) || "").toLowerCase();
  if (/^\s*\[kondisi stok\]/.test(c) || /kondisi stok|stok gudang|pallet|inventaris/.test(c)) return "stok";
  if (/^\s*\[kondisi posko\]/.test(c) || /kondisi posko|bangunan posko|gedung .*posko/.test(c)) return "posko";
  return "lapangan";
}

function buktiCleanCap(row) {
  const raw = (row && (row.evidence_caption || row.caption || row.title)) || "Bukti lapangan";
  return String(raw).replace(/^\s*\[[^\]]+\]\s*/, "");
}

function buktiUploadHref(kind) {
  return `evidence.html?event=${encodeURIComponent(eventParam())}` +
         `&posko=${encodeURIComponent(poskoParam())}` +
         (kind ? `&kind=${encodeURIComponent(kind)}` : "");
}

function buktiTileHtml(label, kind, row, idAttr) {
  if (row) {
    const cap = buktiCleanCap(row);
    return `
      <button type="button" class="rn-upload-tile is-filled" data-bukti-tile="${row.__i}">
        <span class="rn-upload-tile-thumb">
          <img src="${safe(row.evidence_url)}" alt="${safe(cap)}" loading="lazy">
        </span>
        <b>${label}</b>
        <span>Diperbarui ${fmtWhen(row.created_at || row.creation || row.observed_at)} · lihat foto</span>
      </button>`;
  }
  return `
    <a class="rn-upload-tile" id="${idAttr}" href="${buktiUploadHref(kind)}">
      <b>${label}</b><span>Belum ada — unggah foto</span>
    </a>`;
}

function renderEvidence(b) {
  const tiles = document.getElementById("buktiTiles");
  const grid = document.getElementById("buktiGrid");
  const meta = document.getElementById("buktiMeta");
  const seeAll = document.getElementById("buktiSeeAll");
  const rows = (b.bukti || []).map((r, i) => Object.assign({ __i: i }, r));
  window.__LOG_BUKTI = rows;

  if (seeAll) seeAll.href = buktiUploadHref("");

  const stokRow = rows.filter(r => buktiCat(r) === "stok")[0] || null;
  const poskoRow = rows.filter(r => buktiCat(r) === "posko")[0] || null;
  const usedIdx = new Set([stokRow, poskoRow].filter(Boolean).map(r => r.__i));
  const rest = rows.filter(r => !usedIdx.has(r.__i));

  if (tiles) {
    tiles.innerHTML =
      buktiTileHtml("Kondisi Stok", "stok", stokRow, "uploadStok") +
      buktiTileHtml("Kondisi Posko", "posko", poskoRow, "uploadPosko");
    tiles.querySelectorAll("[data-bukti-tile]").forEach(el => {
      el.addEventListener("click", () => openBuktiModal(rows[Number(el.dataset.buktiTile)]));
    });
  }

  if (grid) {
    grid.innerHTML = rest.length
      ? rest.map(r => {
          const cap = buktiCleanCap(r);
          const sub = [r.location_text, r.reporter_name || r.uploader].filter(Boolean).join(" · ");
          return `
            <button type="button" class="rn-bukti-item" data-bukti="${r.__i}">
              <span class="rn-bukti-thumb">
                <img src="${safe(r.evidence_url)}" alt="${safe(cap)}" loading="lazy">
              </span>
              <span class="rn-bukti-cap">${safe(cap)}</span>
              ${sub ? `<span class="rn-bukti-sub">${safe(sub)}</span>` : ""}
            </button>`;
        }).join("")
      : `<p class="rn-muted">Bukti lapangan lain belum ada.</p>`;
    grid.querySelectorAll("[data-bukti]").forEach(el => {
      el.addEventListener("click", () => openBuktiModal(rows[Number(el.dataset.bukti)]));
    });
  }

  if (meta) {
    meta.textContent = rows.length
      ? `Foto terakhir diunggah ${fmtWhen(b.bukti_last_at)} · ${b.bukti_total || rows.length} bukti`
      : "Belum ada bukti foto untuk posko ini.";
  }
}

function openBuktiModal(row) {
  if (!row) return;
  const modal = document.getElementById("buktiModal");
  if (!modal) return;
  const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = safe(v); };
  const img = document.getElementById("buktiModalImg");
  const cap = buktiCleanCap(row);
  if (img) { img.src = row.evidence_url || ""; img.alt = cap; }
  set("buktiModalTitle", cap);
  set("buktiModalLoc", row.location_text || "Lokasi tidak dicatat");
  set("buktiModalDesc",
    String(row.description || row.evidence_details || cap).replace(/^\s*\[[^\]]+\]\s*/, ""));
  set("buktiModalType", row.evidence_type || "photo");
  set("buktiModalReporter",
    [row.reporter_name || row.uploader, row.uploader_role].filter(Boolean).join(" · ") || "-");
  set("buktiModalStatus", row.status || row.verification_status || "-");
  set("buktiModalTime", fmtWhen(row.created_at || row.creation || row.observed_at));
  const open = document.getElementById("buktiModalOpen");
  if (open) open.href = row.evidence_url || "#";
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeBuktiModal() {
  const modal = document.getElementById("buktiModal");
  if (modal) modal.hidden = true;
  document.body.style.overflow = "";
}

/* ---------- KPI cards → jump to the data behind each figure ---------- */

function makeKpiClickable(el, handler, hint) {
  if (!el || el.dataset.wired) return;
  el.dataset.wired = "1";
  el.classList.add("is-clickable");
  el.setAttribute("role", "button");
  el.setAttribute("tabindex", "0");
  if (hint) el.title = hint;
  el.addEventListener("click", handler);
  el.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handler(); }
  });
}

function flash(el) {
  if (!el) return;
  el.classList.remove("rn-flash");
  void el.offsetWidth;
  el.classList.add("rn-flash");
}

function scrollToPanel(sel) {
  const el = document.querySelector(sel);
  if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); flash(el.closest(".panel") || el); }
}

function wireKpiCards(b) {
  makeKpiClickable(
    document.getElementById("kpiJiwaCard"),
    () => {
      location.href =
        `posko-detail.html?id=${encodeURIComponent(poskoParam())}&event=${encodeURIComponent(eventParam())}`;
    },
    "Buka detail posko — data jiwa dilayani"
  );

  makeKpiClickable(
    document.getElementById("kpiStokCard"),
    () => {
      const p = document.getElementById("stockCardsPanel");
      if (p) { p.open = true; p.scrollIntoView({ behavior: "smooth", block: "start" }); flash(p); }
    },
    "Lihat Kartu Stok Rinci — item yang menipis"
  );

  makeKpiClickable(
    document.getElementById("kpiKritisCard"),
    () => scrollToPanel("#urgentNeedsBody"),
    "Lihat tabel Kebutuhan Mendesak"
  );

  makeKpiClickable(
    document.getElementById("kpiMenujuCard"),
    () => openIncomingDrawer(null),
    "Lihat semua bantuan yang sedang menuju posko (OTW)"
  );
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

  // Keep the URL + the sidebar function group in sync with the active posko,
  // so opening this page plain (no ?id=) and picking a posko still shows the
  // merged-posko function switcher in the sidebar.
  try {
    const u = new URL(location.href);
    if (u.searchParams.get("id") !== posko) {
      u.searchParams.set("id", posko);
      history.replaceState(null, "", u);
    }
    if (window.rnRefreshPoskoFunctionGroup) window.rnRefreshPoskoFunctionGroup();
  } catch (e) {}

  setStatus("Memuat data logistik…");
  try {
    const b = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.logistik_board",
      { posko, disaster_event: eventParam() }
    );
    LOGISTIK_BOARD = b;

    renderShareBanner(b);
    renderRoleBanner(b);
    renderKpi(b);
    renderKategoriOptions(b);
    renderUrgentNeeds(b);
    renderStockCards(b);
    renderPublicShipments(b);
    renderMovements(b);
    renderTrace(b);
    renderConversions(b);
    renderEvidence(b);
    wireUploadLinks();
    wireKpiCards(b);

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

  document.getElementById("kpiJiwaEdit")?.addEventListener("click", e => {
    e.stopPropagation();
    editBeneficiary();
  });

  document.getElementById("logistikKategori")?.addEventListener("change", e => {
    KATEGORI = e.target.value || "";
    if (LOGISTIK_BOARD) {
      renderUrgentNeeds(LOGISTIK_BOARD);
      renderStockCards(LOGISTIK_BOARD);
    }
  });

  document.getElementById("buktiModalClose")?.addEventListener("click", closeBuktiModal);
  document.getElementById("buktiModal")?.addEventListener("click", e => {
    if (e.target.id === "buktiModal") closeBuktiModal();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeBuktiModal();
  });

  setupLogisticNeedForm();
  setupAidOfferForm();

  try {
    await loadPoskoOptions();
  } catch (e) {
    setStatus("Gagal memuat daftar posko: " + (e && e.message || e));
  }
  await loadBoard();

  // Deep-link from Control Centre "Kebutuhan Kritis" → open the Penuhi drawer
  // for a specific item (?penuhi=<item name>).
  const penuhiItem = new URLSearchParams(location.search).get("penuhi");
  if (penuhiItem) {
    const b = LOGISTIK_BOARD || {};
    const hit =
      (b.urgent_needs || []).find(
        r => String(r.item_name || "").toLowerCase() === penuhiItem.toLowerCase()
      ) ||
      (b.stock_cards || []).find(
        c => String(c.item || "").toLowerCase() === penuhiItem.toLowerCase()
      );
    openFulfill(penuhiItem, (hit && hit.unit) || "");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
