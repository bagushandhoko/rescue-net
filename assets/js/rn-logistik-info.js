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

  function safe(v) {
    return (v === null || v === undefined || v === "") ? "-" : v;
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
        <td>${safe(s.item_name)}</td>
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

    body.innerHTML = rows.length
      ? rows.map(m => `
          <tr>
            <td>${safe(m[whoKey])}</td>
            <td>${safe(m.item_name)}</td>
            <td>${fmt(m.quantity)} ${safe(m.unit)}</td>
            <td>${statusChip(m.status)}</td>
          </tr>
        `).join("")
      : `<tr><td colspan="4">Belum ada pergerakan ${movTab}.</td></tr>`;
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
  };
})();
