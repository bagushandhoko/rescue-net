/* Akun demo di halaman login (owner 2026-10-25): tombol "Pakai akun ini"
   mengisi formulir Masuk (email + kata sandi demo). Tidak login otomatis —
   pengguna tetap menekan Masuk. */
(function () {
  "use strict";
  var PASSWORD = "Demo12345";

  function useAccount(email) {
    var tab = document.querySelector('.rn-auth-tab[data-auth-tab="login"]');
    if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
    var form = document.getElementById("loginForm");
    if (!form) return;
    form.elements.email.value = email;
    form.elements.password.value = PASSWORD;
    form.scrollIntoView({ behavior: "smooth", block: "center" });
    var btn = form.querySelector('button[type="submit"]');
    if (btn) setTimeout(function () { btn.focus(); }, 300);
  }

  function boot() {
    document.querySelectorAll(".rn-demo-card[data-demo-email]").forEach(function (card) {
      var email = card.getAttribute("data-demo-email");
      var meta = document.createElement("div");
      meta.className = "rn-demo-meta";
      meta.innerHTML = '<code></code><button type="button" class="btn mini">Pakai akun ini</button>';
      meta.querySelector("code").textContent = email;
      meta.querySelector("button").addEventListener("click", function () { useAccount(email); });
      card.appendChild(meta);
    });
  }

  // Mode Operasional Riil (owner 2026-11-09): akun demo disembunyikan saat super admin mengaktifkan mode itu.
  // Gagal memeriksa -> tampilan lama (akun demo tampil), tidak ada yang rusak.
  function hideWhenOperational() {
    fetch(location.origin + "/rescue-net-frappe/api/method/rescue_net.api_operational_mode.status",
      { credentials: "omit", headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (j) {
        if (!(j && j.message && j.message.operational)) return;
        var box = document.getElementById("demoAccounts");
        if (box) { box.hidden = true; box.style.display = "none"; }
      })
      .catch(function () { /* opsional */ });
  }

  function start() { boot(); hideWhenOperational(); }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
