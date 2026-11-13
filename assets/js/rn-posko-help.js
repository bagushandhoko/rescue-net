/* Tombol "?" di setiap halaman -> langsung menampilkan bagian manual/panduan halaman itu.
   Owner 2026-11-11: "tambahkan di setiap halaman posko '?' ... langsung tampilkan manual untuk masing2 posko itu";
   2026-11-12: "'?' kok nggak tampil di halaman2, semua link ke manual detail" -> semua halaman + pemeriksa posisi
   (di halaman ringkasan judul detail disembunyikan setelah dimuat, tombol ikut hilang). Dibuat Suri (Claude CT105).
   Halaman posko -> panduan.html#p-<jenis>; halaman lain -> manual.html#<bagian>. */
(function () {
  var PAGE = (location.pathname.split("/").pop() || "").toLowerCase();
  var P = "panduan.html", M = "manual.html";
  var BY_PAGE = {
    // 12 Nov 2026: halaman ini punya bagian sendiri di Manual Bagian F
    "sitrep.html": [M, "h-sitrep", "Laporan Situasi (SITREP) & API pelaporan"],
    "evidence.html": [M, "h-evidence", "Evidence Center (bukti lapangan)"],
    "kelola-bencana.html": [M, "h-kelola-bencana", "Kelola Bencana"],
    "war-room.html": [M, "h-war-room", "Control Centre (War Room)"],
    "data-consolidation.html": [M, "h-konsolidasi", "Konsolidasi Data"],
    "kebutuhan-publik.html": [M, "h-kebutuhan-publik", "Kebutuhan Publik"],
    "lacak-logistik.html": [M, "h-lacak", "Lacak Kiriman Bantuan"],
    "scan.html": [M, "h-scan", "Pindai Barcode / Serah Terima"],
    "relawan-saya.html": [M, "h-relawan-saya", "Pengaturan Relawan"],
    "kehadiran-relawan.html": [M, "h-kehadiran", "Kehadiran Relawan"],
    "program-khusus.html": [M, "h-program-khusus", "Program Khusus & Donasi"],
    "edit-bantuan.html": [M, "h-edit-bantuan", "Ubah / Batalkan Bantuan (Kode Edit)"],
    "jejak-audit.html": [M, "h-jejak-audit", "Jejak Audit"],
    "pengadaan-tender.html": [M, "h-pengadaan", "Pengadaan & Tender"],
    "notifikasi-settings.html": [M, "h-notifikasi", "Pengaturan Notifikasi (WhatsApp/SMS)"],
    "ai-settings.html": [M, "h-ai-settings", "Pengaturan AI (kunci sendiri)"],
    "ai-analyst.html": [M, "h-ai-analyst", "Analis AI"],
    "contact-directory.html": [M, "h-kontak", "Direktori Kontak"],
    "perencanaan-pengungsi.html": [M, "h-perencanaan", "Perencanaan Pengungsi"],
    "masukan-masyarakat.html": [M, "h-masukan", "Masukan Masyarakat"],
    "status-akses.html": [M, "h-status-akses", "Status Akses Jalan & Infrastruktur"],
    "riwayat-kegiatan.html": [M, "h-riwayat", "Riwayat Kegiatan"],
    "back-office.html": [M, "h-back-office", "Back Office Penanganan"],
    "resource-profile.html": [M, "h-sumber-daya", "Profil Sumber Daya"],
    "posko-logistik.html": [P, "p-logistik", "Posko Logistik"],
    "posko-distribusi.html": [P, "p-distribusi", "Posko Distribusi"],
    "posko-medis-detail.html": [P, "p-medis", "Posko Medis"],
    "shelter-detail.html": [P, "p-shelter", "Shelter / Pengungsian"],
    "dapur-umum.html": [P, "p-dapur", "Dapur Umum"],
    "management-relawan.html": [P, "p-relawan", "Posko Relawan"],
    "posko-alat.html": [P, "p-alat", "Posko Alat Kerja"],
    "alat-kerja.html": [M, "alat-kerja", "Recovery Program & Alat Kerja"],
    "alat-komunikasi.html": [P, "p-komunikasi", "Posko Komunikasi"],
    "search-found.html": [P, "p-sar", "Posko SAR"],
    "komando-pusat.html": [P, "p-komando", "Posko Komando"],
    "posko-detail.html": [P, "jenis", "Jenis Posko"],
    "bencana-aktif.html": [M, "mulai", "Mulai & memilih bencana"],
    "map.html": [M, "mulai", "Peta & memilih bencana"],
    "peta-nasional.html": [M, "mulai", "Peta & memilih bencana"],
    "laporan-masyarakat.html": [M, "laporan", "Mengirim laporan masyarakat"],
    "kirim-bantuan.html": [M, "bantuan", "Menyalurkan bantuan"],
    "donor-program.html": [M, "bantuan", "Program khusus & donasi"],
    "management-distribusi.html": [M, "distribusi", "Distribusi & armada"],
    "kelola-posko.html": [M, "kelola-posko", "Kelola Posko Saya"],
    "registrasi-posko.html": [M, "posko", "Mendaftar & mengelola posko"],
    "auth.html": [M, "registrasi", "Registrasi akun & organisasi"],
    "organisasi-posko.html": [M, "organisasi", "Organisasi terbuka & tertutup"],
    "koordinasi-organisasi.html": [M, "organisasi", "Koordinasi organisasi (termasuk backup data organisasi)"],
    "verification-approval.html": [M, "verifikasi", "Verifikasi berjenjang"],
    "tawarkan-alat.html": [M, "alat-kerja", "Recovery Program & Alat Kerja"],
    "penyedia-alat.html": [M, "alat-kerja", "Posko Alat Kerja & Tawarkan Alat"],
    "pengadaan-tender.html": [M, "lainnya", "Fitur lainnya"]
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
      if (BY_TEXT[i][0].test(txt)) { cur = [P, BY_TEXT[i][1], BY_TEXT[i][2]]; return; }
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
      ".rn-ph-btn.rn-ph-float{position:fixed;top:70px;right:14px;z-index:8000;margin:0;box-shadow:0 4px 12px rgba(0,0,0,.18)}" +
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
    var url = cur[0] + "#" + cur[1];
    var ov = document.createElement("div");
    ov.className = "rn-ph-ov";
    ov.innerHTML = '<div class="rn-ph-box" role="dialog" aria-modal="true" aria-label="Panduan ' + cur[2] + '">' +
      '<div class="rn-ph-head">❓ ' + (cur[0] === P ? "Panduan " : "Manual: ") + cur[2] +
      '<a href="' + url + '" target="_blank" rel="noopener">Buka di tab baru ↗</a>' +
      '<button type="button" aria-label="Tutup">×</button></div>' +
      '<iframe src="' + url + '" title="Panduan ' + cur[2] + '"></iframe></div>';
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
        s.textContent = ".sidebar,.rn-public-header,.topbar,.rn-drawer-hamburger,.rn-ai-fab,#rnAiFab,.rn-mobile-topbar,#rnPoskoHelp{display:none!important}" +
          ".app-shell{display:block!important;zoom:1!important;width:auto!important;min-width:0!important}" +
          "body{min-width:0!important;padding:0!important}.main{padding:12px 16px!important;min-height:0!important}";
        d.head.appendChild(s);
        var t = d.getElementById(cur[1]);
        if (t) t.scrollIntoView({ block: "start" });
      } catch (e) { /* beda origin: biarkan tampil apa adanya */ }
    });
    ov.querySelector(".rn-ph-head button").focus();
  }

  function visible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  }
  function visibleHeading() {
    var all = document.querySelectorAll(".main h1, .main h2, main h1, main h2, .page-header h1, .page-header h2");
    for (var i = 0; i < all.length; i++) if (visible(all[i])) return all[i];
    return null;
  }
  function button() {
    var b = document.getElementById("rnPoskoHelp");
    if (b) return b;
    css();
    b = document.createElement("button");
    b.type = "button";
    b.id = "rnPoskoHelp";
    b.className = "rn-ph-btn";
    b.textContent = "?";
    b.setAttribute("data-no-i18n", "");
    b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); open(); });
    return b;
  }
  // Tempel di judul yang TERLIHAT; bila tak ada, melayang di kanan atas. Dipanggil ulang bila tombol tersembunyi.
  function place(force) {
    var b = document.getElementById("rnPoskoHelp");
    if (b && visible(b)) return true;
    var h = visibleHeading();
    if (!h && !force) return false;
    guessType();
    b = button();
    b.title = (cur[0] === P ? "Panduan " : "Manual: ") + cur[2];
    b.setAttribute("aria-label", "Buka " + b.title);
    if (h) { b.classList.remove("rn-ph-float"); h.appendChild(b); }
    else { b.classList.add("rn-ph-float"); document.body.appendChild(b); }
    return true;
  }

  function start() {
    var n = 0;
    var t = setInterval(function () {
      n++;
      place(n >= 4);
      if (n > 40) clearInterval(t); // ±20 detik: halaman ringkasan/detail sering mengganti bagian yang terlihat
    }, 500);
    window.addEventListener("resize", function () { place(true); });
    document.addEventListener("visibilitychange", function () { if (!document.hidden) place(true); });
    document.addEventListener("click", function () { setTimeout(function () { place(true); }, 700); }, true);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
