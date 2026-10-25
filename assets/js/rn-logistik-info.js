/* Shared read-only "Kondisi Logistik Posko" renderers.
   Used by posko-detail.html (info) — posko-logistik.html renders its own
   compact, action-focused views instead (see logistik.js). Both pull from
   the same guest rescue_net.api_control_centre.logistik_board RPC.
   Namespaced under window.RNLogistikInfo to avoid clashing with
   page-local helpers of the same short names (e.g. posko-detail.js's
   own safe()/fmt()). */
window.RNLogistikInfo = (function () {
  "use strict";

  let movTab = "masuk";

  function safe(v) {  // HTML-escaped — values go into innerHTML
    if (v === null || v === undefined || v === "") return "-";
    return String(v).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
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

  function statusChip(status, text) {
    const s = String(status || "").toLowerCase();
    let cls = "neutral";
    if (/(received|completed|diterima|closed|arrived)/.test(s)) cls = "good";
    else if (/(transit|dispatch|jalan|pickup)/.test(s)) cls = "warning";
    return `<span class="chip ${cls}">${safe(text || status)}</span>`;
  }

  /* "Daftar Barang" (owner 2026-10-25/26): one row per item — its stock card
     plus items that moved in/out — shared by Posko Logistik and Posko Detail.
     An item seen only in cancelled shipments is left out. */
  const DONE = /^(cancelled|received|received_verified|stock_transferred)$/;
  const normItem = s => String(s || "").toLowerCase().replace(/\s+/g, " ").trim();

  function habisChip(days) {
    if (days === null || days === undefined) return `<span class="rn-muted">—</span>`;
    const cls = days < 3 ? "danger" : days < 7 ? "warning" : "good";
    return `<span class="chip ${cls}">${fmt(days)} hari</span>`;
  }

  function itemListRows(b, keep) {
    const rows = new Map();
    const get = (item, unit, create) => {
      const key = normItem(item);
      if (!key) return null;
      if (!rows.has(key) && create) rows.set(key, { item, unit, card: null, masuk: [], keluar: [] });
      return rows.get(key) || null;
    };
    (b.stock_cards || []).forEach(c => { const r = get(c.item, c.unit, true); if (r) r.card = c; });
    const live = m => String(m.status || "") !== "cancelled";
    (b.movements_in || []).forEach(m => { const r = get(m.item_name, m.unit, live(m)); if (r) r.masuk.push(m); });
    (b.movements_out || []).forEach(m => { const r = get(m.item_name, m.unit, live(m)); if (r) r.keluar.push(m); });
    // a card that exists only because of cancelled shipments (no stock, no
    // need, nothing live) is noise — e.g. a cancelled test send
    const onlyCancelled = r => {
      const mv = r.masuk.concat(r.keluar);
      return mv.length && mv.every(m => !live(m)) && (!r.card || (!Number(r.card.stok_ada) && !Number(r.card.kebutuhan)));
    };
    const list = Array.from(rows.values()).filter(r => !onlyCancelled(r));
    return keep ? list.filter(keep) : list;
  }

  function renderItemList(b, opts) {
    opts = opts || {};
    const body = document.getElementById("itemListBody");
    if (!body) return [];
    const tools = document.getElementById("itemListTools");
    if (tools) scanButton(b, tools);
    const list = itemListRows(b, opts.keep);
    const cnt = document.getElementById("itemListCount");
    if (cnt) cnt.textContent = `${list.length} item`;
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="4" class="rn-muted">${safe(opts.emptyText || "Belum ada barang di posko ini.")}</td></tr>`;
      return list;
    }
    body.innerHTML = list.map((r, i) => {
      const c = r.card;
      const moving = r.keluar.filter(m => !DONE.test(String(m.status || ""))).length;
      return `
        <tr class="rn-item-row" data-i="${i}" tabindex="0" role="button" title="Buka kartu stok">
          <td><a href="#" class="rn-item-open"><b>${safe(r.item)}</b></a> <small>${r.unit ? safe(r.unit) : ""}</small>
            ${moving ? `<br><small class="rn-muted">${moving} kiriman keluar berjalan</small>` : ""}</td>
          <td>${c ? fmt(c.stok_ada) : (b.detail_allowed ? "—" : `<span class="rn-muted">terkunci</span>`)}</td>
          <td>${c && (c.masuk_7h || c.keluar_7h)
            ? `<span class="rn-in">${c.masuk_7h ? "+" + fmt(c.masuk_7h) : "0"}</span> / <span class="rn-out">${c.keluar_7h ? "−" + fmt(c.keluar_7h) : "0"}</span>`
            : `${r.masuk.length} masuk · ${r.keluar.length} keluar`}</td>
          <td>${c ? habisChip(c.estimasi_habis_hari) : "—"}</td>
        </tr>`;
    }).join("");
    const open = i => opts.onOpen && opts.onOpen(list[Number(i)]);
    body.querySelectorAll(".rn-item-row").forEach(tr => {
      tr.addEventListener("click", e => { e.preventDefault(); open(tr.dataset.i); });
      tr.addEventListener("keydown", e => { if (e.key === "Enter") open(tr.dataset.i); });
    });
    return list;
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

  function poskoLogistikUrl(item) {
    const q = new URLSearchParams(location.search);
    const id = q.get("id") || "posko-sim-logistik";
    const ev = q.get("event") || q.get("disaster_event_id") || "";
    return `posko-logistik.html?id=${encodeURIComponent(id)}&event=${encodeURIComponent(ev)}&penuhi=${encodeURIComponent(item || "")}`;
  }

  function renderKpi(b) {
    const k = b.kpi || {};
    const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    const collector = !!b.is_collector;
    const jiwaCard = document.getElementById("kpiJiwaCard");
    if (jiwaCard) {
      const label = jiwaCard.querySelector("span:not(.kpi-icon)");
      if (label && label.firstChild) {
        label.firstChild.textContent = collector ? "Peran Posko " : "Jiwa Dilayani ";
      }
    }
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

  function renderUrgentNeeds(b) {
    const body = document.getElementById("urgentNeedsBody");
    if (!body) return;
    const rows = b.urgent_needs || [];
    const total = b.urgent_needs_total || rows.length;

    const cnt = document.getElementById("urgentNeedsCount");
    if (cnt) cnt.textContent = `${total} item`;

    const shown = document.getElementById("urgentNeedsShown");
    if (shown) shown.textContent = `Menampilkan ${Math.min(rows.length, total)} dari ${total} item`;

    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" class="rn-muted">Tidak ada kebutuhan mendesak yang tercatat.</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(r => `
      <tr>
        <td><a href="${poskoLogistikUrl(r.item_name)}" title="Buka Logistik Posko — penuhi kebutuhan"><b>${safe(r.item_name)}</b></a> <small>${safe(r.unit)}</small>${r.report_channel
          ? `<small class="rn-rep-badge ${safe(r.reporter_confirmation || "pending")}">Laporan pelapor terverifikasi · ${safe(r.reporter_label)} · ${
              r.reporter_confirmation === "confirmed" ? "dikonfirmasi posko" : "belum dikonfirmasi"}</small>` : ""}</td>
        <td>${fmt(r.stok_tersedia)} ${safe(r.unit)}</td>
        <td class="rn-gap">${r.gap ? fmt(r.gap) + " " + safe(r.unit) : "—"}</td>
        <td>${habisDot(r.estimasi_habis)}</td>
        <td>${etaChip(r.waktu_harus_tiba)}</td>
        <td>${priorityChip(r.priority)}</td>
      </tr>
    `).join("");

    if (!b.detail_allowed) {
      body.insertAdjacentHTML("beforeend",
        `<tr><td colspan="6" class="rn-muted">Ringkasan koordinasi — organisasi posko ini belum membuka detail lengkap.</td></tr>`);
    }
  }

  function renderPublicShipmentsInfo(b) {
    const panel = document.getElementById("publicShipInfoPanel");
    const body = document.getElementById("publicShipInfoBody");
    const cnt = document.getElementById("publicShipInfoCount");
    if (!panel || !body) return;
    const rows = b.public_shipments || [];
    if (!rows.length) { panel.hidden = true; return; }
    if (cnt) cnt.textContent = rows.length;
    body.innerHTML = rows.map(s => `
      <tr>
        <td><b>${safe(s.donor_name)}</b></td>
        <td>${s.flow ? `<a href="lacak-logistik.html?flow=${encodeURIComponent(s.flow)}" title="Lacak kiriman">${safe(s.item_name)}</a>` : safe(s.item_name)}</td>
        <td>${fmt(s.quantity)} ${safe(s.unit)}</td>
        <td>${s.wave ? "Gel. " + s.wave : (safe(s.ready_at) || "—")}</td>
        <td>${statusChip(s.status)}</td>
      </tr>`).join("");
    panel.hidden = false;
  }

  function renderMovements(b) {
    const body = document.getElementById("movBody");
    const head = document.getElementById("movWhoHead");
    if (!body) return;
    const rows = movTab === "masuk" ? (b.movements_in || []) : (b.movements_out || []);
    const whoKey = movTab === "masuk" ? "dari" : "tujuan";
    if (head) head.textContent = movTab === "masuk" ? "Dari" : "Tujuan";

    // owner 2026-10-25: the sending posko prints a label (QR + barcode) per
    // shipment; managers get "Pindai barcode" for the custody scanner
    const manage = !!b.can_manage;
    const label = m => (manage && movTab !== "masuk" && m.flow)
      ? ` <a class="rn-mov-label" href="cetak-label.html?print=1&flow=${encodeURIComponent(m.flow)}" title="Cetak label kiriman (QR + barcode)">🖨 Label</a>` : "";
    body.innerHTML = rows.length
      ? rows.map(m => `
          <tr>
            <td>${safe(m[whoKey])}</td>
            <td>${m.flow ? `<a href="lacak-logistik.html?flow=${encodeURIComponent(m.flow)}" title="Lacak kiriman">${safe(m.item_name)}</a>` : safe(m.item_name)}</td>
            <td>${fmt(m.quantity)} ${safe(m.unit)}</td>
            <td>${statusChip(m.status, m.status_label)}${label(m)}${m.flow ? ` <a class="rn-mov-label" href="lacak-logistik.html?flow=${encodeURIComponent(m.flow)}" title="Lacak perjalanan kiriman">📍 Lacak</a>` : ""}</td>
          </tr>
        `).join("")
      : `<tr><td colspan="4">Belum ada pergerakan ${movTab}.${movTab === "keluar" && manage ? " Label 🖨 muncul di sini setelah barang dikirim." : ""}</td></tr>`;
    scanButton(b);
  }

  // toolbar beside the Masuk/Keluar tabs: scan + print (managers), track (all)
  function toolButton(parent, id, text, title) {
    let a = document.getElementById(id);
    if (!a) {
      a = document.createElement("a");
      a.id = id;
      a.className = "btn ghost mini rn-mov-scan";
      a.textContent = text;
      a.title = title;
      parent.appendChild(a);
    }
    return a;
  }

  function scanButton(b, host) {
    const tabs = document.getElementById("movTabMasuk");
    const parent = host || (tabs && tabs.parentNode);
    if (!parent) return;
    const manage = !!b.can_manage;
    const scan = toolButton(parent, "movScanBtn", "📷 Pindai barcode", "Pindai QR / barcode label kiriman");
    const page = location.pathname.split("/").pop() + location.search;
    scan.href = "scan.html?back=" + encodeURIComponent(page);
    scan.hidden = !manage;
    // owner 2026-10-25: straight to the printer with the labels of every
    // outgoing shipment still on its way (not cancelled / already received)
    const print = toolButton(parent, "movPrintBtn", "🖨 Cetak label", "Cetak label semua kiriman keluar yang masih berjalan");
    const live = (b.movements_out || []).filter(m => m.flow &&
      !/^(cancelled|received|received_verified|stock_transferred)$/.test(String(m.status || "")));
    print.href = live.length
      ? "cetak-label.html?print=1&" + live.slice(0, 30).map(m => "flow=" + encodeURIComponent(m.flow)).join("&")
      : "cetak-label.html";
    print.title = live.length ? `Pilih label dari ${Math.min(live.length, 30)} kiriman keluar` : "Belum ada kiriman keluar yang berjalan";
    print.hidden = !manage;
    const track = toolButton(parent, "movTrackBtn", "📍 Lacak resi", "Lacak kiriman dengan nomor resi RN-XXXXXXXX");
    track.href = "lacak-logistik.html";
    track.hidden = false;
  }

  function wireMovementsTabs(getBoard) {
    document.getElementById("movTabMasuk")?.addEventListener("click", () => {
      movTab = "masuk";
      document.getElementById("movTabMasuk").classList.add("is-active");
      document.getElementById("movTabKeluar").classList.remove("is-active");
      const b = getBoard();
      if (b) renderMovements(b);
    });
    document.getElementById("movTabKeluar")?.addEventListener("click", () => {
      movTab = "keluar";
      document.getElementById("movTabKeluar").classList.add("is-active");
      document.getElementById("movTabMasuk").classList.remove("is-active");
      const b = getBoard();
      if (b) renderMovements(b);
    });
  }

  return {
    renderKpi,
    renderUrgentNeeds,
    renderPublicShipmentsInfo,
    renderMovements,
    wireMovementsTabs,
    renderTools: scanButton,
    renderItemList,
    itemListRows,
    statusChip,
  };
})();
