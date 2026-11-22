/* Edisi Tertutup (CT202): peta & SITREP LIVE dari backend RN.
 * Sumber: rescue_net.api_control_centre.active_disasters_board (publik, data riil saja;
 * data latihan/simulasi disaring backend). Tanpa angka contoh: bila kosong, tampil kosong.
 * Ming Ming 2026-11-22 (owner: "GIS di tampilan awal ganti dengan live bencana aktif di RN").
 */
(() => {
  "use strict";
  const API = "/rescue-net-frappe/api/method/rescue_net.api_control_centre.active_disasters_board";
  const REFRESH_MS = 60000;
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
    if (chip) chip.textContent = "LIVE · RN";
  }

  async function load() {
    try {
      const r = await fetch(API, { credentials: "include", headers: { Accept: "application/json" } });
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
