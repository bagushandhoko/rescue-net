/* Tombol kecil Simulasi / Riil di pojok kanan bawah setiap halaman (owner 2026-11-18). Dibuat Suri (Claude CT105).
 * - Bawaan RIIL: Rescue-Net datang kosong sampai ada bencana riil. Cookie rn_tampilan=simulasi = tampilan latihan.
 * - Tulisan miring menunjukkan tampilan TUJUAN: di Riil tertulis "simulasi", di Simulasi tertulis "riil".
 * - Klik: simpan pilihan, lalu muat halaman yang sama di tampilan baru.
 * - Kembali ke Riil dari halaman detail posko (posko simulasi tidak ada di data riil) -> halaman Organisasi & Posko.
 * Dimuat otomatis oleh rn-public-header.js dan rn-mobile-drawer.js. */
(function () {
  if (window.__rnModeToggle) return;
  window.__rnModeToggle = true;

  var POSKO_PAGES = /\/pages\/(posko-detail|posko-logistik|posko-distribusi|posko-medis-detail|shelter-detail|dapur-umum|posko-alat|alat-komunikasi|kelola-posko|search-found)\.html$/;

  function isSim() { return /(?:^|;\s*)rn_tampilan=simulasi(?:;|$)/.test(document.cookie); }

  function save(v) {
    var sec = location.protocol === "https:" ? "; Secure" : "";
    try {
      sessionStorage.removeItem("rn_opmode");
      localStorage.removeItem("rn_active_event");
      localStorage.removeItem("rn-active-event");
    } catch (e) {}
    document.cookie = "rn_tampilan=" + v + "; path=/; max-age=31536000; SameSite=Lax" + sec;
  }

  function tujuan(keSimulasi) {
    var u = new URL(location.href);
    ["event", "disaster_event_id", "disaster_event"].forEach(function (k) { u.searchParams.delete(k); });
    if (!keSimulasi && (u.searchParams.get("id") || u.searchParams.get("posko")) && POSKO_PAGES.test(u.pathname)) {
      return "/rescue-net/pages/organisasi-posko.html";
    }
    return u.pathname + (u.searchParams.toString() ? "?" + u.searchParams.toString() : "") + u.hash;
  }

  function pasang() {
    if (document.getElementById("rnModeToggle") || !document.body) return;
    if (document.body.classList.contains("mockup-viewer")) return;
    var sim = isSim();
    var b = document.createElement("button");
    b.id = "rnModeToggle";
    b.type = "button";
    b.textContent = sim ? "riil" : "simulasi";
    b.title = sim
      ? "Sedang menampilkan data SIMULASI (latihan). Klik untuk kembali ke data riil."
      : "Sedang menampilkan data riil. Klik untuk melihat data simulasi (latihan).";
    b.setAttribute("aria-label", b.title);
    // owner 2026-11-18 (revisi): kembali ke pojok KANAN BAWAH, lurus (tidak diputar), ukuran huruf 14px tebal tetap,
    // latar transparan tapi terbaca. Di Simulasi oranye sebagai tanda. Ukuran tombol = tombol Tanya AI (padding 11x16, 36px, 14px dari tepi).
    b.style.cssText = [
      "position:fixed", "right:14px", "bottom:14px", "z-index:10050",
      "font-style:italic", "font-weight:700", "font-size:14px", "line-height:14px", "font-family:inherit",
      "letter-spacing:.3px", "padding:10px 16px", "box-sizing:border-box", "border-radius:999px", "cursor:pointer",
      "border:1px solid " + (sim ? "rgba(232,104,40,.75)" : "rgba(122,58,26,.25)"),
      "background:" + (sim ? "rgba(232,104,40,.62)" : "rgba(255,255,255,.62)"),
      "color:" + (sim ? "#fff" : "#7a3a1a"),
      "text-shadow:" + (sim ? "0 1px 2px rgba(0,0,0,.45)" : "0 0 3px #fff,0 0 2px #fff"),
      "box-shadow:0 1px 6px rgba(0,0,0,.18)",
      "backdrop-filter:blur(2px)", "-webkit-backdrop-filter:blur(2px)"
    ].join(";");
    b.addEventListener("click", function () {
      var keSim = !isSim();
      save(keSim ? "simulasi" : "riil");
      location.href = tujuan(keSim);
    });
    document.body.appendChild(b);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", pasang);
  else pasang();
})();
