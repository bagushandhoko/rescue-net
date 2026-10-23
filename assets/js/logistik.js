/* Posko Logistik — management console (login/authorized-operator actions
   for this posko). The read-only "kondisi posko" info (KPI, Kebutuhan
   Mendesak, Kiriman Masyarakat, Barang Masuk/Keluar) lives on
   posko-detail.html via rn-logistik-info.js instead — both pull from the
   same guest rescue_net.api_control_centre.logistik_board RPC.
   Action gating uses board.detail_allowed (org-sharing/role based), not a
   plain "is anyone logged in" check. */

let LOGISTIK_BOARD = null;
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

// HTML-escaped (item names / labels come from posko staff, donors and, since
// 2026-10-01, outside verified reporters — every value goes into innerHTML)
function safe(v) {
  if (v === null || v === undefined || v === "") return "-";
  return String(v).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
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

  let points = [], viewer = {};
  for (let attempt = 0; attempt < 2 && !points.length; attempt++) {
    if (attempt > 0) await new Promise(r => setTimeout(r, 800));
    try {
      const res = await RN_FRAPPE.call(
        "rescue_net.api_control_centre.event_poskos",
        { disaster_event: eventParam() }
      );
      points = Array.isArray(res) ? res : (res.points || []);
      viewer = (res && res.viewer) || {};
    } catch (e) {
      points = [];
    }
  }

  if (!points.length) {
    sel.innerHTML = `<option value="${poskoParam() || ""}">${poskoParam() || "posko"}</option>`;
    return;
  }

  if (!window.RNPoskoPicker) {
    // fallback: flat list (shared picker script failed to load)
    const want = poskoParam();
    sel.innerHTML = points
      .map(pt => {
        const id = pt.posko_id || pt.id || pt.name;
        return `<option value="${id}"${id === want ? " selected" : ""}>${safe(pt.name)}</option>`;
      })
      .join("");
    if (!want && sel.options.length) sel.selectedIndex = 0;
    sel.addEventListener("change", () => loadBoard());
    return;
  }

  window.RNPoskoPicker.mount({
    selectEl: sel,
    points,
    viewer,
    current: poskoParam(),
    // logistics-type poskos first, within each group
    sortFn: (a, b) => {
      const la = /logist|gudang|warehouse/i.test(a.posko_type || "") ? 0 : 1;
      const lb = /logist|gudang|warehouse/i.test(b.posko_type || "") ? 0 : 1;
      return la - lb;
    },
    labelFn: pt => pt.name || pt.title || "",
    onChange: () => loadBoard(),
  });
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

/* "Kiriman Masyarakat" — read-only for everyone (mockup); an operator
   (can_manage) additionally gets a "Terima" action column. Panel is hidden
   when the posko exposes no detail or has nothing pending. */
function renderPublicShipments(b) {
  const panel = document.getElementById("publicShipInfoPanel");
  const body = document.getElementById("publicShipInfoBody");
  const cnt = document.getElementById("publicShipInfoCount");
  const aksiHead = document.querySelector("#publicShipInfoPanel .rn-col-aksi");
  const rows = b.public_shipments || [];
  if (!panel || !body) return;
  if (!b.detail_allowed || !rows.length) { panel.hidden = true; return; }
  const canManage = !!b.can_manage;
  if (cnt) cnt.textContent = rows.length;
  if (aksiHead) aksiHead.hidden = !canManage;
  body.innerHTML = rows.map(s => `
    <tr>
      <td><b>${safe(s.donor_name)}</b></td>
      <td>${s.flow ? `<a href="lacak-logistik.html?flow=${encodeURIComponent(s.flow)}" title="Lacak kiriman">${safe(s.item_name)}</a>` : safe(s.item_name)}</td>
      <td>${fmt(s.quantity)} ${safe(s.unit)}</td>
      <td>${s.wave ? "Gel. " + s.wave : (safe(s.ready_at) || "—")}</td>
      <td>${statusChip(s.status)}</td>
      ${canManage
        ? `<td><button type="button" class="btn ghost mini" data-receive-ship="${s.id}">Terima</button></td>`
        : ""}
    </tr>`).join("");
  panel.hidden = false;

  body.querySelectorAll("[data-receive-ship]").forEach(btn =>
    btn.addEventListener("click", () => receivePublicShipment(btn.dataset.receiveShip))
  );
}

async function receivePublicShipment(aidOffer) {
  if (!confirm("Tandai kiriman ini sudah diterima dan masukkan ke stok?")) return;
  try {
    await RN_FRAPPE.call(
      "rescue_net.api_logistics.receive_aid_offer_and_update_stock",
      { aid_offer: aidOffer },
      { method: "POST" }
    );
    await loadBoard();
  } catch (err) {
    alert("Gagal menerima kiriman: " + (err && err.message || err));
  }
}

/* The page is the read-only "Kondisi Logistik" dashboard (mockup) for
   everyone. An operator of THIS posko (b.can_manage) gets inline edit on
   top: "+ Tambah" on Kebutuhan Mendesak, "Ubah" on the Jiwa Dilayani KPI,
   "Terima" on Kiriman Masyarakat rows, plus the deeper operator panels
   (Kartu Stok Rinci, Kelompok Barang). A member of ANOTHER org whose posko
   opened participation (b.can_coordinate) gets ONLY "Tambah Bantuan
   Tersedia" (record aid bound for this posko). Everyone else: read-only + a
   one-line hint. */
function renderManageAccess(b) {
  const canManage = !!b.can_manage;
  const canCoordinate = !!b.can_coordinate;
  const isCollector = !!b.is_collector;

  const noAccess = document.getElementById("logistikNoAccess");
  if (noAccess) {
    noAccess.hidden = canManage || canCoordinate;
    const a = document.getElementById("logistikNoAccessLink");
    if (a) a.href = `auth.html?next=${encodeURIComponent(location.pathname + location.search)}`;
  }

  // inline edit affordances on the dashboard (operator of THIS posko only)
  const addNeed = document.getElementById("btnOpenAddNeed");
  const canReport = !!b.can_report && !canManage;  // Pelapor Terverifikasi: needs only, any posko
  if (addNeed) {
    addNeed.hidden = !(canManage || canReport);
    addNeed.textContent = canReport ? "+ Laporkan Kebutuhan" : "+ Tambah";
  }
  const modalTitle = document.getElementById("addNeedModalTitle");
  if (modalTitle) modalTitle.textContent = canReport ? "Laporkan Kebutuhan (Pelapor Terverifikasi)" : "Tambah Kebutuhan Logistik";
  const reporterNote = document.getElementById("reporterNeedNote");
  if (reporterNote) reporterNote.hidden = !canReport;
  if (noAccess && canReport) noAccess.hidden = true;
  const editJiwa = document.getElementById("btnEditJiwa");
  if (editJiwa) editJiwa.hidden = !canManage || isCollector;

  // deeper operator-only analytics panels
  ["itemGroupPanel", "stockCardsPanel"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = !canManage;
  });

  // "Tambah Bantuan Tersedia" — operator OR cross-org coordinator
  const aid = document.getElementById("aidOfferPanel");
  if (aid) aid.hidden = !(canManage || canCoordinate);
  const aidNote = document.getElementById("aidCoordNote");
  if (aidNote) aidNote.hidden = !(canCoordinate && !canManage);
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
  const canManage = !!b.can_manage;
  body.innerHTML = cards.length
    ? cards.map(c => `
        <tr>
          <td><a href="#" class="rn-stok-src" data-item="${encodeURIComponent(c.item)}"><b>${safe(c.item)}</b></a> <small>${safe(c.unit)}</small></td>
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
          <td>
            <button class="btn ghost mini rn-penuhi" data-item="${encodeURIComponent(c.item)}" data-unit="${encodeURIComponent(c.unit || "")}">Penuhi</button>
            ${canManage ? `<button class="btn primary mini rn-kirim" data-item="${encodeURIComponent(c.item)}" data-unit="${encodeURIComponent(c.unit || "")}" data-stok="${safe(c.stok_ada)}">Kirim</button>` : ""}
          </td>
        </tr>
      `).join("")
    : `<tr><td colspan="10">Belum ada kartu stok.</td></tr>`;

  body.querySelectorAll(".rn-otw").forEach(a => {
    a.addEventListener("click", e => {
      e.preventDefault();
      openIncomingDrawer(decodeURIComponent(a.dataset.item));
    });
  });
  body.querySelectorAll(".rn-stok-src").forEach(a => {
    a.addEventListener("click", e => {
      e.preventDefault();
      openStockSources(decodeURIComponent(a.dataset.item));
    });
  });
  body.querySelectorAll(".rn-penuhi").forEach(btn => {
    btn.addEventListener("click", () => openFulfill(
      decodeURIComponent(btn.dataset.item),
      decodeURIComponent(btn.dataset.unit || "")
    ));
  });
  body.querySelectorAll(".rn-kirim").forEach(btn => {
    btn.addEventListener("click", () => openDispatch(
      decodeURIComponent(btn.dataset.item),
      decodeURIComponent(btn.dataset.unit || ""),
      btn.dataset.stok
    ));
  });
}

/* "Asal item" — where the stock for this item came from (donations +
   arrived kiriman from other poskos). */
async function openStockSources(item) {
  showDrawer(`Asal item — ${item}`, `<p class="rn-muted">Memuat…</p>`);
  try {
    const r = await RN_FRAPPE.call(
      "rescue_net.api_control_centre.logistik_stock_sources",
      { posko: poskoParam(), item }
    );
    const rows = (r && r.sources) || [];
    showDrawer(`Asal item — ${item}`, rows.length
      ? `<div class="rn-drawer-list">${rows.map(s => `
          <div class="rn-drawer-row">
            <div>
              <b>${safe(s.from)}</b> · ${fmt(s.quantity)} ${safe(s.unit)}
              <br><small>${safe(s.kind)} · ${s.received ? "diterima" : safe(s.status)} · ${safe(s.at)}</small>
            </div>
          </div>`).join("")}</div>`
      : `<p class="rn-muted">Belum ada catatan asal untuk item ini.</p>`);
  } catch (e) {
    showDrawer(`Asal item — ${item}`, `<p class="rn-muted">Gagal memuat: ${safe(e && e.message || e)}</p>`);
  }
}

/* "Kirim stok" — dispatch this posko's stock to a receiver posko, optionally
   routed through a transport posko's armada (RN Transport Space). Backend:
   api_logistics.create_flow. If "Lewat" is left "Langsung — cari transporter",
   no armada is set and the flow shows up in Posko Distribusi's pickup queue
   for any transport posko to claim. */
/* "Kirim stok" — 3 langkah (owner 2026-10-19/20):
   1. Tujuan & barang (bencana yang dilayani posko ini, rentang kirim, jumlah,
      berat, posko tujuan di bencana itu)
   2. Booking space distribusi utama (armada yang melayani bencana + posko
      ini + berangkat dalam rentang) — atau langsung ke tujuan
   3. Cara barang sampai ke titik serah armada utama (atau ke tujuan):
      antar sendiri / masuk antrean (posko distribusi yang menjalankan) /
      pilih posko distribusi transporter (booking jemput-antar)
   Booking armada posko lain: satu organisasi disetujui otomatis, beda
   organisasi menunggu konfirmasi posko distribusinya. */
function isoDay(offset) {          // local date, YYYY-MM-DD
  const d = new Date(); d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const val = v => (v === null || v === undefined || v === "") ? "" : safe(v);   // form value (no "-")

function armadaCard(a, name, on) {
  return `<label class="rn-evc-card${on ? " is-on" : ""}">
    <input type="radio" name="${name}" value="${safe(a.id)}"${on ? " checked" : ""}>
    <span class="rn-evc-title">${safe(a.provider)} <small class="rn-muted">${safe(a.jenis)}</small></span>
    <span class="rn-evc-meta">Berangkat ${safe(a.berangkat)} · tiba ${safe(a.eta)}${a.sisa_kg != null ? ` · sisa ${fmt(a.sisa_kg)} kg` : ""}
      <span class="rn-evc-badge${a.same_org ? "" : " closed"}">${a.same_org ? "Satu organisasi · langsung disetujui" : "Perlu konfirmasi posko"}</span></span>
    <span class="rn-evc-loc">${safe(a.posko_title)}${a.rute ? " · " + safe(a.rute) : ""}${a.handover ? " · serah terima: " + safe(a.handover) : ""}${a.jadwal_kosong ? " · jadwal belum diisi" : ""}</span></label>`;
}
function plainCard(name, value, title, sub, on) {
  return `<label class="rn-evc-card${on ? " is-on" : ""}">
    <input type="radio" name="${name}" value="${safe(value)}"${on ? " checked" : ""}>
    <span class="rn-evc-title">${title}</span><span class="rn-evc-meta">${sub}</span><span></span></label>`;
}

async function openDispatch(item, unit, stok) {
  const st = { step: 1, event: eventParam(), from: isoDay(0), to: isoDay(3), dest: "", main: "",
    first: "", courier: "", qty: "", unit: unit || "", note: "", kg: "", opt: null, optKey: "" };
  const T = `Kirim stok — ${item}`;
  showDrawer(T, `<p class="rn-muted">Memuat pilihan…</p>`);

  async function options() {
    const key = [st.event, st.from, st.to].join("|");
    if (st.opt && st.optKey === key) return st.opt;
    st.opt = await RN_FRAPPE.call("rescue_net.api_control_centre.logistik_dispatch_options", {
      disaster_event: st.event, source_posko: poskoParam(), window_from: st.from, window_to: st.to, item,
    });
    st.optKey = key;
    st.event = st.opt.disaster_event || st.event;
    return st.opt;
  }

  const steps = () => `<ol class="rn-dispatch-steps">${["Tujuan & barang", "Distribusi utama", "Ke titik serah"]
    .map((t, i) => `<li class="${st.step === i + 1 ? "is-on" : st.step > i + 1 ? "is-done" : ""}">${i + 1}. ${t}</li>`).join("")}</ol>`;

  async function render() {
    let opt;
    try { opt = await options(); } catch (e) {
      showDrawer(T, `<p class="rn-muted">Gagal: ${safe(e && e.message || e)}</p>`); return;
    }
    const events = opt.events || [], dests = opt.destinations || [], armada = opt.armada || [];
    if (!dests.some(d => d.id === st.dest)) st.dest = "";
    if (!armada.some(a => a.id === st.main)) st.main = "";
    const destT = (dests.find(d => d.id === st.dest) || {}).title || "";
    const main = armada.find(a => a.id === st.main);
    const summary = `<p class="rn-dispatch-sum"><b>${safe(item)}</b> · ${val(st.qty)} ${val(st.unit)}${st.kg ? ` · ${val(st.kg)} kg` : ""} → <b>${safe(destT)}</b></p>`;
    let body = "";
    // owner 2026-10-20: never send beyond stock — the server checks it too
    const sk = opt.stock;
    const avail = sk ? Number(sk.available) : Number(stok || 0);
    const sUnit = (sk && sk.unit) || unit || "";
    if (sUnit) st.unit = sUnit;
    if (st.step === 1) {
      body = `
      <div class="rn-dispatch-stock${avail > 0 ? "" : " is-empty"}">
        <span>Stok tersedia untuk dikirim</span>
        <b>${fmt(avail)} ${safe(sUnit)}</b>
        ${sk ? `<small>Tercatat ${fmt(sk.observed)} ${safe(sUnit)}${sk.observed_at ? " (" + safe(String(sk.observed_at).slice(0, 16)) + ")" : ""}${Number(sk.sent_since) ? ` · sudah dikirim ${fmt(sk.sent_since)} ${safe(sUnit)} sejak itu` : ""}</small>` : ""}
        ${avail > 0 ? "" : `<small>Stok habis — catat stok baru dulu sebelum mengirim.</small>`}
      </div>
      <label>Bencana yang dilayani
        ${events.length > 1
          ? `<select name="disaster_event">${events.map(ev => `<option value="${safe(ev.id)}"${ev.id === st.event ? " selected" : ""}>${safe(ev.title)}</option>`).join("")}</select>`
          : `<input value="${safe((events[0] && events[0].title) || st.event)}" readonly>`}
      </label>
      <div class="rn-dispatch-window">
        <label>Kirim dari<input type="date" name="window_from" value="${val(st.from)}" required></label>
        <label>Sampai<input type="date" name="window_to" value="${val(st.to)}" required></label>
      </div>
      <div class="rn-dispatch-window">
        <label>Jumlah dikirim <small class="rn-muted">maks ${fmt(avail)}</small>
          <input name="quantity" type="number" step="0.01" min="0" max="${avail}" required value="${val(st.qty)}"></label>
        <label>Satuan<input name="unit" value="${val(st.unit)}" readonly></label>
      </div>
      <label>Perkiraan berat (kg) <small class="rn-muted">— wajib bila memakai armada / transporter</small>
        <input name="weight_kg" type="number" step="0.1" min="0" value="${val(st.kg)}"></label>
      <label>Tujuan (posko penerima di bencana ini)
        <select name="destination_posko" required>
          <option value="">— pilih posko tujuan —</option>
          ${dests.map(d => `<option value="${safe(d.id)}"${d.id === st.dest ? " selected" : ""}>${safe(d.title)}${d.city ? " — " + safe(d.city) : ""}${d.role === "receiver" ? " · penerima" : ""}${d.jiwa ? " · " + fmt(d.jiwa) + " jiwa" : ""}</option>`).join("")}
        </select>
      </label>
      <div class="form-actions"><button class="btn primary" type="submit"${avail > 0 ? "" : " disabled"}>Lanjut →</button><span class="form-message" id="dispatchMsg"></span></div>`;
    } else if (st.step === 2) {
      body = summary + `
      <div class="rn-evc"><b>Booking space distribusi utama</b>
        <small class="rn-muted">${armada.length} armada melayani bencana ini & posko Anda, berangkat ${safe(st.from)} s/d ${safe(st.to)}</small>
        <div class="rn-evc-grid">${plainCard("main", "", "Langsung ke tujuan", "Tanpa armada utama", !st.main)}${armada.map(a => armadaCard(a, "main", st.main === a.id)).join("")}</div></div>
      <div class="form-actions"><button class="btn ghost" type="button" data-back>← Kembali</button>
        <button class="btn primary" type="submit">Lanjut →</button><span class="form-message" id="dispatchMsg"></span></div>`;
    } else {
      const target = main ? `titik serah terima ${safe(main.provider)}${main.handover ? " (" + safe(main.handover) + ")" : ""}` : `tujuan ${safe(destT)}`;
      const couriers = armada.filter(a => a.courier && a.id !== st.main);
      if (!couriers.some(a => a.id === st.courier)) st.courier = "";
      body = summary + (main ? `<p class="rn-muted">Distribusi utama: <b>${safe(main.provider)}</b> — ${main.same_org ? "satu organisasi, langsung disetujui" : "menunggu konfirmasi posko distribusi"}</p>` : "") + `
      <div class="rn-evc"><b>Barang sampai ke ${target} dengan cara</b>
        <div class="rn-evc-grid">
          ${plainCard("first", "self_deliver", "Antar sendiri", "Posko Anda mengantar barang ke " + target, st.first === "self_deliver")}
          ${plainCard("first", "queue", "Masuk antrean", "Tunggu — posko distribusi memilih untuk menjemput & menjalankan", st.first === "queue")}
          ${plainCard("first", "transporter", "Pilih posko distribusi transporter", "Jemput-antar antar posko & titik distribusi", st.first === "transporter")}
        </div></div>
      <div class="rn-evc" data-couriers${st.first === "transporter" ? "" : " hidden"}><b>Transporter</b>
        <small class="rn-muted">${couriers.length} transporter jemput-antar melayani bencana ini</small>
        <div class="rn-evc-grid">${couriers.length ? couriers.map(a => armadaCard(a, "courier", st.courier === a.id)).join("")
          : `<div class="rn-evc-empty">Belum ada transporter jemput-antar di rentang ini.</div>`}</div></div>
      <label>Catatan<input name="note" placeholder="opsional" value="${val(st.note)}"></label>
      <div class="form-actions"><button class="btn ghost" type="button" data-back>← Kembali</button>
        <button class="btn primary" type="submit">Kirim</button><span class="form-message" id="dispatchMsg"></span></div>`;
    }
    showDrawer(T, `<form id="dispatchForm" class="rn-form">${steps()}${body}</form>`);
    wire();
  }

  function keep(form) {
    const v = n => form.elements[n] ? form.elements[n].value : undefined;
    const r = n => { const x = form.querySelector(`input[name="${n}"]:checked`); return x ? x.value : undefined; };
    if (st.step === 1) {
      st.qty = v("quantity"); st.unit = v("unit"); st.kg = v("weight_kg"); st.dest = v("destination_posko");
      st.from = v("window_from"); st.to = v("window_to");
      if (form.elements.disaster_event && form.elements.disaster_event.tagName === "SELECT") st.event = v("disaster_event");
    } else if (st.step === 2) {
      st.main = r("main") || "";
    } else {
      st.first = r("first") || ""; st.courier = r("courier") || ""; st.note = v("note") || "";
    }
  }

  function wire() {
    const form = document.getElementById("dispatchForm");
    const msg = () => document.getElementById("dispatchMsg");
    form.querySelectorAll('input[type="radio"]').forEach(x => x.addEventListener("change", () => {
      form.querySelectorAll(`input[name="${x.name}"]`).forEach(y => y.closest(".rn-evc-card").classList.toggle("is-on", y.checked));
      if (x.name === "first") form.querySelector("[data-couriers]").hidden = x.value !== "transporter";
    }));
    if (st.step === 1) {
      ["disaster_event", "window_from", "window_to"].forEach(n => {
        const el = form.elements[n];
        if (el && el.tagName !== "INPUT" || (el && el.type === "date")) el.addEventListener("change", () => { keep(form); render(); });
      });
    }
    const back = form.querySelector("[data-back]");
    if (back) back.addEventListener("click", () => { keep(form); st.step -= 1; render(); });
    form.addEventListener("submit", async e => {
      e.preventDefault();
      keep(form);
      if (st.step === 1) {
        if (st.from && st.to && st.to < st.from) { msg().textContent = "Tanggal 'Sampai' harus setelah 'Kirim dari'."; return; }
        if (!(Number(st.qty) > 0)) { msg().textContent = "Isi jumlah dikirim."; return; }
        const sk1 = st.opt && st.opt.stock, max1 = sk1 ? Number(sk1.available) : Number(stok || 0);
        if (Number(st.qty) > max1) { msg().textContent = `Melebihi stok: maksimal ${fmt(max1)} ${st.unit || ""}.`; return; }
        if (!st.dest) { msg().textContent = "Pilih posko tujuan."; return; }
        st.step = 2; render(); return;
      }
      if (st.step === 2) {
        if (st.main && !(Number(st.kg) > 0)) { msg().textContent = "Isi perkiraan berat (kg) di langkah 1 untuk booking armada."; return; }
        st.step = 3; render(); return;
      }
      if (!st.first) { msg().textContent = "Pilih cara barang sampai."; return; }
      if (st.first === "transporter" && !st.courier) { msg().textContent = "Pilih transporter."; return; }
      if (st.first === "transporter" && !(Number(st.kg) > 0)) { msg().textContent = "Isi perkiraan berat (kg) di langkah 1."; return; }
      msg().textContent = "Mengirim…";
      try {
        const r = await RN_FRAPPE.call("rescue_net.api_logistics.create_flow", {
          destination_posko: st.dest, item_text: item, quantity: Number(st.qty || 0),
          unit: String(st.unit || "").trim(), quantity_mode: "exact", source_posko: poskoParam(),
          transport_space: st.main || undefined, disaster_event: st.event,
          window_from: st.from ? st.from + " 00:00:00" : undefined,
          window_to: st.to ? st.to + " 23:59:59" : undefined,
          weight_kg: Number(st.kg) > 0 ? Number(st.kg) : undefined,
          first_mile: st.first, first_mile_space: st.first === "transporter" ? st.courier : undefined,
        }, { method: "POST" });
        const bk = s => s === "confirmed" ? "disetujui otomatis (satu organisasi)" : "menunggu konfirmasi posko distribusi";
        const parts = ["Terkirim."];
        if (r.booking) parts.push(`Booking distribusi utama ${bk(r.booking_status)}.`);
        if (r.first_mile_booking) parts.push(`Booking transporter ${bk(r.first_mile_status)}.`);
        if (st.first === "queue") parts.push("Masuk antrean jemput Posko Distribusi.");
        if (st.first === "self_deliver") parts.push(`Antar sendiri ke ${st.main ? "titik serah terima armada" : "posko tujuan"}.`);
        msg().textContent = parts.join(" ");
        setTimeout(() => { hideDrawer(); loadBoard(); }, 2200);
      } catch (err) {
        msg().textContent = (err && err.message) || String(err);
      }
    });
  }
  render();
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

/* KPI tile -> this posko's own rows (see poskoDrill). */
const LOGISTIK_KPI_DIM = { kritis: "kebutuhan", stok: "stok", menuju: "distribusi" };

async function decideReportedNeed(btn) {
  const need = btn.getAttribute("data-rep-need");
  const act = btn.getAttribute("data-rep-act");
  let note = null;
  if (act === "reject") {
    note = prompt("Alasan menolak laporan ini (opsional):", "");
    if (note === null) return;
  }
  btn.disabled = true;
  try {
    await RN_FRAPPE.call("rescue_net.api_logistics.confirm_reported_need", { need, action: act, note }, { method: "POST" });
    await loadBoard();
  } catch (err) {
    btn.disabled = false;
    alert("Gagal: " + (err && err.message || err));
  }
}

document.addEventListener("click", e => {
  const btn = e.target.closest("[data-rep-need]");
  if (btn) { e.preventDefault(); decideReportedNeed(btn); }
});

// "Kebutuhan Mendesak" = this posko's own open needs (shared renderer).
function renderNeedsBoard(board) {
  if (window.RNLogistikInfo) RNLogistikInfo.renderUrgentNeeds(board || {});
  // the posko's own operators confirm / reject needs reported by verified reporters
  if (!board || !board.can_manage) return;
  const trs = document.querySelectorAll("#urgentNeedsBody tr");
  (board.urgent_needs || []).forEach((it, i) => {
    if (!it.report_channel || (it.reporter_confirmation || "pending") !== "pending" || !it.need || !trs[i]) return;
    trs[i].cells[0].insertAdjacentHTML("beforeend",
      `<span class="rn-rep-act"><button type="button" class="btn mini" data-rep-need="${safe(it.need)}" data-rep-act="confirm">Konfirmasi</button>` +
      `<button type="button" class="btn mini" data-rep-need="${safe(it.need)}" data-rep-act="reject">Tolak</button></span>`);
  });
}

function eventWideHref() {
  return `management-distribusi.html?event=${encodeURIComponent(eventParam())}`;
}
function wireEventWideLinks() {
  document.querySelectorAll("[data-rn-event-wide]").forEach(a => { a.href = eventWideHref(); });
}

/* KPI tile -> the rows of THIS posko behind the figure (from the board
   already loaded); a link leads to the disaster-wide view. */
function poskoDrill(kpi, b) {
  const title = (b.posko && b.posko.title) || "posko ini";
  const more = `<p><a class="btn ghost mini" href="${eventWideHref()}">Lihat semua posko di bencana ini → Manajemen Distribusi</a></p>`;
  const list = (rows, line, empty) => rows.length
    ? `<div class="rn-drill-list">${rows.map(r => `<div class="rn-drill-item">${line(r)}</div>`).join("")}</div>`
    : `<p class="rn-muted">${empty}</p>`;
  if (kpi === "kritis") {
    const rows = b.urgent_needs || [];
    return [`Kebutuhan — ${title}`, list(rows, r =>
      `<div class="rn-drill-item-main"><b>${safe(r.item_name)}</b> ${statusChip(r.priority || "normal")}
        ${r.gap ? `<span class="rn-muted">gap ${fmt(r.gap)} ${safe(r.unit)}</span>` : ""}</div>`,
      "Tidak ada kebutuhan terbuka di posko ini.") + more];
  }
  if (kpi === "stok") {
    if (!b.detail_allowed) return [`Stok — ${title}`, `<p class="rn-muted">Organisasi posko ini menutup detail stok; hanya ringkasan yang tampil.</p>` + more];
    const rows = (b.stock_cards || []).slice().sort((x, y) => num(x.estimasi_habis_hari ?? 9999) - num(y.estimasi_habis_hari ?? 9999));
    return [`Stok — ${title}`, list(rows, r =>
      `<div class="rn-drill-item-main"><b>${safe(r.item)}</b> <span class="rn-muted">${fmt(r.stok_ada)} ${safe(r.unit)}</span>
        ${r.estimasi_habis_hari != null ? habisChip(r.estimasi_habis_hari) : ""}</div>`,
      "Belum ada stok tercatat di posko ini.") + more];
  }
  const rows = (b.incoming || []).filter(f => !/received|diterima|cancel|reject/i.test(f.flow_status || ""));
  return [`Bantuan Menuju — ${title}`, (b.detail_allowed ? list(rows, f =>
    `<div class="rn-drill-item-main"><b>${safe(f.item_name)}</b> <span class="rn-muted">${fmt(f.quantity)} ${safe(f.unit)}</span> ${statusChip(f.flow_status)}</div>
     <div class="rn-muted">dari ${safe(f.source_posko || "donatur")}${f.eta_final ? " · ETA " + fmtWhen(f.eta_final) : ""}</div>`,
    "Tidak ada kiriman yang sedang menuju posko ini.")
    : `<p class="rn-muted">Organisasi posko ini menutup detail pengiriman.</p>`) + more];
}

async function openLogistikDrill(kpi) {
  const b = LOGISTIK_BOARD || {};

  if (kpi === "jiwa") {
    const p = b.posko || {};
    showDrawer("Jiwa Dilayani", `
      <p><b>${fmt(b.kpi && b.kpi.jiwa_dilayani || 0)}</b> jiwa dilayani posko ini.</p>
      <p class="rn-muted">${safe(p.beneficiary_note)}</p>
      ${p.beneficiary_updated_at ? `<p class="rn-muted">Diperbarui ${fmtWhen(p.beneficiary_updated_at)}</p>` : ""}`);
    return;
  }

  if (LOGISTIK_KPI_DIM[kpi]) showDrawer(...poskoDrill(kpi, b));
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
  const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = (v === null || v === undefined || v === "") ? "-" : String(v); };
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
    // A posko page is the workspace of THIS posko only (owner 2026-10-19):
    // its own stock, needs, incoming and outgoing. The cross-posko picture of
    // the whole disaster lives in Manajemen Distribusi / Control Centre.
    const b = await RN_FRAPPE.call("rescue_net.api_control_centre.logistik_board",
      { posko, disaster_event: eventParam() });
    LOGISTIK_BOARD = b;

    renderShareBanner(b);
    renderRoleBanner(b);
    // read-only "Kondisi Logistik" dashboard (mockup) — shared renderers
    if (window.RNLogistikInfo) {
      RNLogistikInfo.renderKpi(b);
      RNLogistikInfo.renderMovements(b);
    }
    renderNeedsBoard(b);
    wireEventWideLinks();
    renderManageAccess(b);      // toggles the operator inline actions on top
    renderKategoriOptions(b);
    renderStockCards(b);
    renderPublicShipments(b);
    renderTrace(b);
    renderConversions(b);
    renderEvidence(b);
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
    const jiwa = form.jiwa_terdampak ? form.jiwa_terdampak.value.trim() : "";
    if (["urgent", "critical"].includes(form.priority.value) && !(Number(jiwa) > 0)) {
      if (msg) msg.textContent = "Isi jumlah jiwa yang membutuhkan untuk kebutuhan urgent/critical.";
      form.jiwa_terdampak && form.jiwa_terdampak.focus();
      return;
    }
    try {
      if (msg) msg.textContent = "Menyimpan kebutuhan…";
      await RN_FRAPPE.call(
        "rescue_net.api_logistics.create_need",
        {
          posko: form.node_id.value.trim() || getLogisticsPosko(),
          item_text: form.item_name.value.trim(),
          quantity: Number(form.quantity_needed.value || 0),
          unit: form.unit.value.trim(),
          quantity_mode: "exact",
          urgency: form.priority.value,
          needed_before: form.needed_before.value.trim(),
          jiwa_terdampak: jiwa || null
        },
        { method: "POST" }
      );
      const reported = LOGISTIK_BOARD && LOGISTIK_BOARD.can_report && !LOGISTIK_BOARD.can_manage;
      if (msg) msg.textContent = reported
        ? "Laporan terkirim — tampil di posko ini dengan tanda belum dikonfirmasi."
        : "Kebutuhan tersimpan.";
      form.reset();
      await loadBoard();
      if (!reported) closeAddNeedModal();
    } catch (err) {
      if (msg) msg.textContent = err.message;
    }
  });
}

function openAddNeedModal() {
  const modal = document.getElementById("addNeedModal");
  if (!modal) return;
  modal.hidden = false;
  modal.querySelector("[name='item_name']")?.focus();
}

function closeAddNeedModal() {
  const modal = document.getElementById("addNeedModal");
  if (modal) modal.hidden = true;
}

function setupAddNeedModal() {
  const modal = document.getElementById("addNeedModal");
  if (!modal) return;
  document.getElementById("btnOpenAddNeed")?.addEventListener("click", openAddNeedModal);
  modal.querySelectorAll("[data-close]").forEach(el =>
    el.addEventListener("click", closeAddNeedModal)
  );
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !modal.hidden) closeAddNeedModal();
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
          quantity_mode: "exact",
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

  document.getElementById("btnEditJiwa")?.addEventListener("click", editBeneficiary);

  if (window.RNLogistikInfo) RNLogistikInfo.wireMovementsTabs(() => LOGISTIK_BOARD);

  // KPI tiles → drill-down (delegated; tiles never re-render)
  document.querySelectorAll(".kpi-card[data-kpi]").forEach(card => {
    const open = () => openLogistikDrill(card.dataset.kpi);
    card.addEventListener("click", e => {
      if (e.target.closest("#btnEditJiwa")) return;   // the "Ubah" button
      open();
    });
    card.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
    });
  });


  document.getElementById("logistikKategori")?.addEventListener("change", e => {
    KATEGORI = e.target.value || "";
    if (LOGISTIK_BOARD) renderStockCards(LOGISTIK_BOARD);
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
  setupAddNeedModal();

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
