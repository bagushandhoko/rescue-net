/* Tombol "?" di setiap halaman posko -> langsung menampilkan bab panduan jenis posko itu.
   Owner 2026-11-11: "tambahkan di setiap halaman posko '?' di bagian atas yang kalau di klik langsung
   tampilkan manual untuk masing2 posko itu". Dibuat Suri (Claude CT105). Panduan: pages/panduan.html#p-*. */
(function () {
  var PAGE = (location.pathname.split("/").pop() || "").toLowerCase();
  var BY_PAGE = {
    "posko-logistik.html": ["p-logistik", "Posko Logistik"],
    "posko-distribusi.html": ["p-distribusi", "Posko Distribusi"],
    "posko-medis-detail.html": ["p-medis", "Posko Medis"],
    "shelter-detail.html": ["p-shelter", "Shelter / Pengungsian"],
    "dapur-umum.html": ["p-dapur", "Dapur Umum"],
    "management-relawan.html": ["p-relawan", "Posko Relawan"],
    "kehadiran-relawan.html": ["p-relawan", "Posko Relawan"],
    "posko-alat.html": ["p-alat", "Posko Alat Kerja"],
    "alat-kerja.html": ["p-alat", "Posko Alat Kerja"],
    "alat-komunikasi.html": ["p-komunikasi", "Posko Komunikasi"],
    "search-found.html": ["p-sar", "Posko SAR"],
    "komando-pusat.html": ["p-komando", "Posko Komando"],
    "posko-detail.html": ["jenis", "Jenis Posko"]
  };
  // posko-detail / posko-logistik melayani beberapa jenis: tebak dari teks halaman bila bisa.
  var BY_TEXT = [
    [/gudang pengumpul|collection hub/i, "p-hub", "Gudang Pengumpul"],
    [/posko medis|pos kesehatan|\bmedis\b/i, "p-medis", "Posko Medis"],
    [/shelter|pengungsian/i, "p-shelter", "Shelter / Pengungsian"],
    [/dapur umum/i, "p-dapur", "Dapur Umum"],
    [/posko distribusi|transport/i, "p-distribusi", "Posko Distribusi"],
    [/assessment|kaji cepat|asesmen/i, "p-assessment", "Posko Assessment"],
    [/\bSAR\b|pencarian/i, "p-sar", "Posko SAR"],
    [/komunikasi|radio/i, "p-komunikasi", "Posko Komunikasi"],
    [/alat kerja|alat berat/i, "p-alat", "Posko Alat Kerja"],
    [/posko relawan/i, "p-relawan", "Posko Relawan"],
    [/komando/i, "p-komando", "Posko Komando"],
    [/posko logistik|logistik/i, "p-logistik", "Posko Logistik"]
  ];
  var cur = BY_PAGE[PAGE];
  if (!cur) return;

  function guessType() {
    if (PAGE !== "posko-detail.html" && PAGE !== "posko-logistik.html") return;
    var el = document.querySelector("[data-posko-type], .rn-posko-type, .posko-type, #pdType, .chip.type, .rn-pd-type");
    var txt = (el && el.textContent) || "";
    if (!txt) {
      var h = document.querySelector(".main h2, .main h1, main h2, main h1");
      var sub = document.querySelector(".main .subtitle, main .subtitle, .main .eyebrow, main .eyebrow");
      txt = ((h && h.textContent) || "") + " " + ((sub && sub.textContent) || "");
    }
    for (var i = 0; i < BY_TEXT.length; i++) {
      if (BY_TEXT[i][0].test(txt)) { cur = [BY_TEXT[i][1], BY_TEXT[i][2]]; return; }
    }
  }

  function css() {
    if (document.getElementById("rnPhCss")) return;
    var st = document.createElement("style");
    st.id = "rnPhCss";
    st.textContent =
      ".rn-ph-btn{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;margin-left:10px;border-radius:50%;" +
      "border:2px solid #b8361f;background:#fff;color:#b8361f;font:800 17px/1 Nunito,Roboto,sans-serif;cursor:pointer;vertical-align:middle;flex:0 0 auto}" +
      ".rn-ph-btn:hover,.rn-ph-btn:focus-visible{background:#b8361f;color:#fff;outline:none}" +
      ".rn-ph-ov{position:fixed;inset:0;z-index:9000;background:rgba(30,20,15,.45);display:flex;align-items:center;justify-content:center;padding:16px}" +
      ".rn-ph-box{background:#fff;border-radius:14px;width:min(860px,100%);height:min(86vh,900px);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.3)}" +
      ".rn-ph-head{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #eadfdb;font:700 16px Nunito,Roboto,sans-serif;color:#2a1f1b}" +
      ".rn-ph-head a{margin-left:auto;font-size:14px;font-weight:600;color:#b8361f}" +
      ".rn-ph-head button{border:0;background:#f3ece8;border-radius:8px;width:34px;height:34px;font-size:20px;cursor:pointer}" +
      ".rn-ph-box iframe{flex:1;border:0;width:100%}";
    document.head.appendChild(st);
  }

  function open() {
    guessType();
    var url = "panduan.html#" + cur[0];
    var ov = document.createElement("div");
    ov.className = "rn-ph-ov";
    ov.innerHTML = '<div class="rn-ph-box" role="dialog" aria-modal="true" aria-label="Panduan ' + cur[1] + '">' +
      '<div class="rn-ph-head">❓ Panduan ' + cur[1] +
      '<a href="panduan.html#' + cur[0] + '" target="_blank" rel="noopener">Buka di tab baru ↗</a>' +
      '<button type="button" aria-label="Tutup">×</button></div>' +
      '<iframe src="' + url + '" title="Panduan ' + cur[1] + '"></iframe></div>';
    function close() { ov.remove(); document.removeEventListener("keydown", esc); }
    function esc(e) { if (e.key === "Escape") close(); }
    ov.addEventListener("click", function (e) { if (e.target === ov) close(); });
    ov.querySelector(".rn-ph-head button").addEventListener("click", close);
    document.addEventListener("keydown", esc);
    document.body.appendChild(ov);
    // Di dalam jendela: sembunyikan menu & kepala situs agar isi panduan lega (halaman satu origin).
    var fr = ov.querySelector("iframe");
    fr.addEventListener("load", function () {
      try {
        var d = fr.contentDocument, s = d.createElement("style");
        s.textContent = ".sidebar,.rn-public-header,.topbar,.rn-drawer-hamburger,.rn-ai-fab,#rnAiFab,.rn-mobile-topbar{display:none!important}" +
          ".app-shell{display:block!important;zoom:1!important;width:auto!important;min-width:0!important}" +
          "body{min-width:0!important;padding:0!important}.main{padding:12px 16px!important;min-height:0!important}";
        d.head.appendChild(s);
        var t = d.getElementById(cur[0]);
        if (t) t.scrollIntoView({ block: "start" });
      } catch (e) { /* beda origin: biarkan tampil apa adanya */ }
    });
    ov.querySelector(".rn-ph-head button").focus();
  }

  function visibleHeading() {
    var all = document.querySelectorAll(".main h1, .main h2, main h1, main h2, .page-header h1, .page-header h2");
    for (var i = 0; i < all.length; i++) {
      var r = all[i].getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && getComputedStyle(all[i]).visibility !== "hidden") return all[i];
    }
    return null;
  }
  function place(force) {
    if (document.getElementById("rnPoskoHelp")) return true;
    var h = visibleHeading();
    if (!h && !force) return false;
    css();
    guessType();
    var b = document.createElement("button");
    b.type = "button";
    b.id = "rnPoskoHelp";
    b.className = "rn-ph-btn";
    b.textContent = "?";
    b.title = "Panduan " + cur[1];
    b.setAttribute("aria-label", "Buka panduan " + cur[1]);
    b.setAttribute("data-no-i18n", "");
    b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); open(); });
    if (h) h.appendChild(b);
    else { // tidak ada judul yang terlihat: tombol melayang di kanan atas
      b.style.cssText = "position:fixed;top:70px;right:14px;z-index:8000;margin:0;box-shadow:0 4px 12px rgba(0,0,0,.18)";
      document.body.appendChild(b);
    }
    return true;
  }

  function start() {
    if (place()) return;
    var n = 0, t = setInterval(function () { if (place(n >= 10) || ++n > 20) clearInterval(t); }, 300);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
