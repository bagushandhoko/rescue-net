/* Tombol kecil Simulasi / Riil di pojok kanan bawah setiap halaman (owner 2026-11-18). Dibuat Suri (Claude CT105).
 * - Bawaan RIIL: Rescue-Net datang kosong sampai ada bencana riil. Cookie rn_tampilan=simulasi = tampilan latihan.
 * - Tulisan menunjukkan tampilan TUJUAN: di Riil tertulis "simulasi", di Simulasi tertulis "riil".
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
    // owner 2026-11-19: bentuk & ukuran SAMA PERSIS dengan tombol Tanya AI (.rn-aic-btn): tanpa garis tepi,
    // padding 11x16, huruf tebal 14px/1, bulat penuh, bayangan sama, 14px dari tepi (+area aman HP), lebar = lebar Tanya AI.
    // Garis tipis dibuat dengan bayangan dalam (inset) agar tidak menambah ukuran. Tulisan miring di tengah.
    b.className = "rn-mode-toggle";
    // owner 2026-11-19 (2): warna & huruf juga SAMA PERSIS dengan Tanya AI (gradasi oranye, tulisan putih tebal tegak).
    b.style.cssText = [
      "position:fixed", "right:14px", "bottom:calc(14px + env(safe-area-inset-bottom,0px))", "z-index:9990",
      "border:0", "border-radius:999px", "padding:11px 16px", "box-sizing:border-box", "min-width:107px",
      "text-align:center", "white-space:nowrap", "font:700 14px/1 system-ui,sans-serif", "cursor:pointer",
      "background:linear-gradient(135deg,#ef523d,#e8835d)", "color:#fff",
      "box-shadow:0 8px 24px rgba(200,70,40,.35)"
    ].join(";");
    if (!document.getElementById("rnModeToggleCss")) {
      var st = document.createElement("style");
      st.id = "rnModeToggleCss";
      st.textContent = "@media (max-width:720px){body:has(.pk-sticky:not([hidden])) .rn-mode-toggle{bottom:84px!important}}" +
        "@media print{.rn-mode-toggle{display:none!important}}";
      document.head.appendChild(st);
    }
    // samakan lebar dengan tombol Tanya AI bila ada (font sama -> ukuran sama persis)
    function samakan() {
      var ai = document.querySelector(".rn-aic-btn");
      if (!ai) return false;
      var r = ai.getBoundingClientRect();
      if (r.width > 0) { b.style.width = r.width + "px"; b.style.height = r.height + "px"; }
      var f = getComputedStyle(ai).fontFamily;
      if (f) b.style.fontFamily = f;
      return true;
    }
    var coba = 0;
    (function tunggu() { if (!samakan() && ++coba < 20) setTimeout(tunggu, 300); })();
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
