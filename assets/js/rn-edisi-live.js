/* Edisi Tertutup (CT202): peta & SITREP LIVE dari backend RN.
 * Sumber: rescue_net.api_control_centre.active_disasters_board (publik, data riil saja;
 * data latihan/simulasi disaring backend). Tanpa angka contoh: bila kosong, tampil kosong.
 * Ming Ming 2026-11-22 (owner: "GIS di tampilan awal ganti dengan live bencana aktif di RN").
 */
(() => {
  "use strict";
  const API = "/rescue-net-frappe/api/method/rescue_net.api_control_centre.active_disasters_board";
  const REFRESH_MS = 60000;
  // Pilihan tampilan SAMA dengan RN (assets/js/rn-tampilan-data.js): cookie rn_tampilan, bawaan riil.
  // CT202 satu domain dengan proxy RN, jadi modul RN di jendela ikut pilihan ini.
  const viewNow = () => (/(?:^|;\s*)rn_tampilan=simulasi(?:;|$)/.test(document.cookie) ? "simulasi" : "riil");
  function viewSave(v) {
    const sec = location.protocol === "https:" ? "; Secure" : "";
    try { sessionStorage.removeItem("rn_opmode"); } catch (_) {}
    if (v === "riil") { try { localStorage.removeItem("rn_active_event"); localStorage.removeItem("rn-active-event"); } catch (_) {} }
    document.cookie = "rn_tampilan=" + (v === "simulasi" ? "simulasi" : "riil") + "; path=/; max-age=31536000; SameSite=Lax" + sec;
  }
  let operational = false;
  const mapNode = document.querySelector("[data-live-map]");
  if (!mapNode || typeof L === "undefined") return;

  const SEV = {
    critical: { color: "#e7615c", label: "Kritis" },
    urgent: { color: "#e7615c", label: "Mendesak" },
    high: { color: "#e8aa49", label: "Tinggi" },
    normal: { color: "#4fb3d9", label: "Waspada" },
    low: { color: "#61bf91", label: "Rendah" },
  };
  const sev = (s) => SEV[String(s || "normal").toLowerCase()] || SEV.normal;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("id-ID") : "—");

  const map = L.map(mapNode, { zoomControl: true, attributionControl: true, worldCopyJump: true })
    .setView([-2.5, 118], 5);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  const layer = L.layerGroup().addTo(map);
  window.addEventListener("resize", () => map.invalidateSize());
  setTimeout(() => map.invalidateSize(), 300);

  const statusNode = document.querySelector("[data-live-status]");
  const emptyNode = document.querySelector("[data-live-empty]");
  const listNode = document.querySelector("[data-live-events]");
  const chip = document.querySelector("[data-live-chip]");
  const setText = (sel, v) => document.querySelectorAll(sel).forEach((n) => { n.textContent = v; });

  function openInWindow(title, url) {
    if (typeof window.rnEdisiOpenWindow === "function") window.rnEdisiOpenWindow(title, url);
    else window.open(url, "_blank", "noopener");
  }
  mapNode.addEventListener("click", (e) => {
    const a = e.target.closest("[data-live-open]");
    if (!a) return;
    e.preventDefault();
    openInWindow(a.dataset.liveTitle || "Rescue-Net", a.dataset.liveOpen);
  });
  listNode?.addEventListener("click", (e) => {
    const a = e.target.closest("[data-live-open]");
    if (!a) return;
    e.preventDefault();
    const ll = a.dataset.liveCenter;
    if (ll) { const [lat, lng] = ll.split(",").map(Number); map.flyTo([lat, lng], 9); }
    openInWindow(a.dataset.liveTitle || "Rescue-Net", a.dataset.liveOpen);
  });

  function openLink(title, url, text) {
    return `<a href="${esc(url)}" data-live-open="${esc(url)}" data-live-title="${esc(title)}">${esc(text)}</a>`;
  }

  const viewBox = document.querySelector("[data-view-switch]");
  function paintView() {
    const v = operational ? "riil" : viewNow();
    viewBox?.querySelectorAll("button[data-view]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.view === v));
      b.disabled = operational;
    });
    if (viewBox) viewBox.title = operational
      ? "Mode Operasional Riil aktif di RN: data simulasi disembunyikan untuk semua pengunjung."
      : "Pilihan sama dengan Rescue-Net: berlaku untuk peta dan semua modul RN di jendela";
    const sim = v === "simulasi";
    setText("[data-live-active-label]", sim ? "Bencana aktif (termasuk simulasi)" : "Bencana riil aktif");
    setText("[data-live-empty-title]", sim ? "Tidak ada bencana aktif" : "Tidak ada bencana riil aktif");
    setText("[data-live-empty-text]", sim ? "RN tidak mencatat bencana aktif, termasuk simulasi."
      : "Peta akan menampilkan bencana dan posko begitu RN mencatat bencana aktif. Pilih Lihat Simulasi untuk data latihan.");
    setText("[data-live-source]", sim
      ? "Sumber: Bencana Aktif RN, TERMASUK data SIMULASI (latihan, bukan kejadian nyata). Diperbarui tiap 1 menit."
      : "Sumber: Bencana Aktif RN (data riil; latihan/simulasi tidak dihitung). Diperbarui tiap 1 menit.");
    return v;
  }
  viewBox?.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-view]");
    if (!b || b.disabled) return;
    viewSave(b.dataset.view);
    paintView();
    load();
    // modul RN yang sedang terbuka di jendela dimuat ulang supaya ikut pilihan baru
    document.querySelectorAll(".rn-edisi-window iframe").forEach((f) => { try { f.contentWindow.location.reload(); } catch (_) { f.src = f.src; } });
  });
  fetch("/rescue-net-frappe/api/method/rescue_net.api_operational_mode.status", { credentials: "include" })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => { operational = !!(j && j.message && j.message.operational); paintView(); load(); })
    .catch(() => {});

  function render(data) {
    const events = Array.isArray(data.events) ? data.events : [];
    const t = data.totals || {};
    layer.clearLayers();
    const bounds = [];
    events.forEach((ev) => {
      const s = sev(ev.severity);
      const evUrl = `bencana-aktif.html?event=${encodeURIComponent(ev.id || ev.event_id)}`;
      (ev.posko_points || []).forEach((p) => {
        L.circleMarker([p.lat, p.lng], { radius: 5, color: "#0d1823", weight: 1, fillColor: s.color, fillOpacity: 0.85 })
          .bindPopup(`<b>${esc(p.title || p.name)}</b><br><small>${esc(p.posko_type || "posko")} · ${esc(ev.name)}</small><br>${openLink(p.title || p.name, p.href, "Buka posko di jendela")}`)
          .addTo(layer);
        bounds.push([p.lat, p.lng]);
      });
      if (ev.center) {
        L.circleMarker([ev.center.lat, ev.center.lng], { radius: 13, color: s.color, weight: 3, fillColor: s.color, fillOpacity: 0.25 })
          .bindPopup(`<b>${esc(ev.name)}</b><br><small>${esc(ev.location || "")}</small><br>` +
            `Status: ${esc(ev.status_label || s.label)}<br>Posko: ${fmt(ev.posko_count)} · Jiwa berisiko: ${fmt(ev.jiwa_berisiko)}<br>` +
            `Pengungsi: ${fmt(ev.pengungsi)} · Kebutuhan kritis: ${fmt(ev.kebutuhan_kritis)}<br>${openLink(ev.name, evUrl, "Buka Bencana Aktif di jendela")}`)
          .addTo(layer);
        bounds.push([ev.center.lat, ev.center.lng]);
      }
    });
    if (bounds.length) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });

    setText("[data-rn-active-events]", fmt(t.bencana_aktif ?? events.length));
    setText("[data-live-jiwa]", fmt(t.jiwa_berisiko));
    setText("[data-live-kebutuhan]", fmt(t.kebutuhan_kritis));
    setText("[data-live-posko-kritis]", fmt(t.posko_kritis));
    setText("[data-live-distribusi]", fmt(t.distribusi_terhambat));
    const noCoords = events.filter((e) => !e.center).length;

    if (emptyNode) emptyNode.hidden = events.length > 0;
    if (listNode) {
      listNode.innerHTML = events.length ? events.slice(0, 8).map((ev) => {
        const s = sev(ev.severity);
        const url = `bencana-aktif.html?event=${encodeURIComponent(ev.id || ev.event_id)}`;
        const c = ev.center ? `${ev.center.lat},${ev.center.lng}` : "";
        return `<li><i style="background:${s.color}"></i><a href="${esc(url)}" data-live-open="${esc(url)}" data-live-title="${esc(ev.name)}" data-live-center="${esc(c)}">${esc(ev.name)}</a><small>${esc(ev.status_label || s.label)} · ${fmt(ev.posko_count)} posko</small></li>`;
      }).join("") : "<li class=\"is-empty\">Tidak ada bencana riil aktif di RN saat ini.</li>";
    }
    const time = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    if (statusNode) statusNode.textContent = `Data live RN · ${events.length} bencana aktif${noCoords ? ` (${noCoords} belum ada koordinat posko)` : ""} · diperbarui ${time}`;
    const v = paintView();
    if (chip) chip.textContent = v === "simulasi" ? "LIVE · RN · TERMASUK SIMULASI" : "LIVE · RN · RIIL";
    if (statusNode && v === "simulasi") statusNode.textContent += " · termasuk simulasi";
  }

  async function load() {
    try {
      const v = operational ? "riil" : viewNow();
      const r = await fetch(API + "?rn_tampilan=" + v, { credentials: "include", headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(String(r.status));
      const payload = await r.json();
      render((payload && payload.message) || {});
    } catch (err) {
      if (statusNode) statusNode.textContent = `Data RN tidak dapat dimuat (${err.message}). Mencoba lagi…`;
      if (chip) chip.textContent = "RN TIDAK TERSAMBUNG";
    }
  }
  load();
  setInterval(() => { if (!document.hidden) load(); }, REFRESH_MS);
})();
