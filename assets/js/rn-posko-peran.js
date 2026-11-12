/* Kotak peran di halaman posko (Logistik, Medis, Shelter, Dapur, Detail Posko).
   Owner 2026-11-11: "tidak membingungkan user pengguna ... terapkan secara similar di posko lain, bedakan user, publik dan
   pemilik posko" (pola yang sama dengan Posko Distribusi). Dibuat Suri (Claude CT105).
   Publik/pengguna: kotak hijau + tombol aksi (Kirim bantuan, Laporkan kondisi). Pemilik: kotak oranye cara mencatat.
   Data peran: rescue_net.api_control_centre.posko_edit_scope (sama dengan rn-posko-scope.js). */
(function () {
  "use strict";
  if (!window.RN_FRAPPE || !window.RN_FRAPPE.call) return;
  var PAGE = (location.pathname.split("/").pop() || "").toLowerCase();
  var KIND = {
    "posko-logistik.html": { bantu: "Kirim bantuan ke posko ini", lapor: "Laporkan kebutuhan / kondisi", catat: "stok masuk/keluar, kebutuhan, dan bantuan tersedia" },
    "posko-medis-detail.html": { bantu: "Kirim bantuan obat / alat medis", lapor: "Laporkan pasien / kondisi", catat: "kasus pasien, pemakaian dan penerimaan obat, kebutuhan" },
    "shelter-detail.html": { bantu: "Kirim bantuan ke shelter ini", lapor: "Laporkan kondisi pengungsi", catat: "okupansi, kebutuhan shelter, dan stok" },
    "dapur-umum.html": { bantu: "Kirim bahan makanan", lapor: "Laporkan kebutuhan makan", catat: "produksi porsi, bahan, dan distribusi makanan" },
    "posko-detail.html": { bantu: "Kirim bantuan ke posko ini", lapor: "Laporkan kondisi", catat: "data operasional posko" }
  };
  var K = KIND[PAGE];
  if (!K) return;
  var qs = new URLSearchParams(location.search);
  var pid = qs.get("id") || qs.get("posko") || "";
  if (!pid) return; // halaman ringkasan semua posko: tidak perlu kotak peran
  var ev = String(qs.get("event") || qs.get("disaster_event_id") || "").replace(/^disaster_events:/, "");
  if (!ev) { try { ev = localStorage.getItem("rn_active_event") || ""; } catch (e) {} }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function css() {
    if (document.getElementById("rnPeranCss")) return;
    var st = document.createElement("style");
    st.id = "rnPeranCss";
    st.textContent =
      ".rn-peran{margin:10px 0 12px;padding:12px 48px 12px 14px;border-radius:12px;border:1px solid #9fd3b4;background:#e9f6ee;color:#174d31;font-size:15px;line-height:1.45}" +
      ".rn-peran.own{border-color:#e8c49d;background:#fff4e8;color:#5a3412}.rn-peran.sm{border-color:#c9c3e6;background:#f3f1fb;color:#2f2a55}" +
      ".rn-peran-act{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}" +
      ".rn-peran-act a{display:inline-flex;align-items:center;min-height:40px;padding:8px 14px;border-radius:999px;font-weight:700;text-decoration:none;font-size:14px}" +
      ".rn-peran-act a.go{background:#1f7a4d;color:#fff}.rn-peran-act a.go:hover{background:#17603c}" +
      ".rn-peran-act a.alt{background:#fff;color:#1f7a4d;border:1px solid #1f7a4d}";
    document.head.appendChild(st);
  }
  function anchor() {
    var hs = document.querySelectorAll(".main h1, .main h2, main h1, main h2");
    for (var i = 0; i < hs.length; i++) {
      var r = hs[i].getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return hs[i].closest(".topbar, header, .page-header, .panel-header, section, .panel") || hs[i];
    }
    return null;
  }
  function render(scope, canManage) {
    if (document.getElementById("rnPeran")) return;
    var a = anchor();
    var main = document.querySelector("main.main, .main, main");
    if (!a && !main) return;
    css();
    var logged = !!(scope && scope.logged_in);
    var sm = !!(scope && scope.is_system_manager);
    // pemilik = can_manage_posko (operator/penugasan/anggota org pemilik) — sama dengan halaman Kelola Posko
    var owner = logged && !sm && !!canManage;
    var box = document.createElement("div");
    box.id = "rnPeran";
    var bantu = "kirim-bantuan.html?posko=" + encodeURIComponent(pid) + (ev ? "&event=" + encodeURIComponent(ev) : "");
    var lapor = "laporan-masyarakat.html" + (ev ? "?event=" + encodeURIComponent(ev) : "");
    var act = '<div class="rn-peran-act"><a class="go" href="' + esc(bantu) + '">' + esc(K.bantu) + '</a>' +
      '<a class="alt" href="' + esc(lapor) + '">' + esc(K.lapor) + "</a></div>";
    if (owner) {
      box.className = "rn-peran own";
      box.innerHTML = "🔧 <b>Anda pengelola posko ini.</b> Catat " + esc(K.catat) +
        " lewat tombol <b>+ Tambah / Catat</b> di tiap bagian. Publik dan pengguna lain hanya melihat ringkasan.";
    } else if (sm) {
      box.className = "rn-peran sm";
      box.innerHTML = "🛡 <b>Super admin.</b> Anda bisa melihat dan mengubah semua posko. Pengelola posko ini adalah organisasi pemiliknya.";
    } else if (logged) {
      box.className = "rn-peran";
      box.innerHTML = "👉 <b>Anda pengguna (bukan pengelola posko ini).</b> Anda bisa membantu atau melapor; mencatat data posko hanya untuk pengelolanya." + act;
    } else {
      box.className = "rn-peran";
      box.innerHTML = "👉 <b>Ingin membantu posko ini?</b> Kirim bantuan atau laporkan kondisi lapangan." + act +
        '<small style="display:block;margin-top:6px;opacity:.85">Mengirim perlu login. <a href="auth.html">Login / daftar</a></small>';
    }
    if (a) a.parentNode.insertBefore(box, a.nextSibling);
    else main.insertBefore(box, main.firstChild); // HP: judul halaman disembunyikan
  }
  function start() {
    Promise.all([
      window.RN_FRAPPE.call("rescue_net.api_control_centre.posko_edit_scope", { posko: pid, disaster_event: ev || null }),
      window.RN_FRAPPE.call("rescue_net.api_posko_manage.can_manage", { posko: pid }).catch(function () { return {}; })
    ]).then(function (r) {
        var scope = r[0] || {}, cm = !!(r[1] && r[1].can_manage);
        var n = 0, t = setInterval(function () { if (anchor() || ++n > 10) { clearInterval(t); render(scope, cm); } }, 300);
      })
      .catch(function () { /* tanpa data peran: biarkan halaman apa adanya */ });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
