/* Setting → Verifikasi Dua Langkah (2026-10-26): rescue_net.api_twofa.
   Setup without email: QR on screen, confirm one code. System Managers who
   finished their own setup can require 2FA for all System Managers. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var call = function (m, a, post) { return window.RN_FRAPPE.call("rescue_net.api_twofa." + m, a || {}, post ? { method: "POST" } : undefined); };
  var msg = function (t, bad) { $("twofaMsg").textContent = t || ""; $("twofaMsg").style.color = bad ? "#c0392b" : ""; };

  function render(st) {
    $("twofaStatus").innerHTML = st.setup_done
      ? "✅ Aktif untuk akun Anda. Login berikutnya meminta kode dari aplikasi."
      : "Belum aktif untuk akun Anda.";
    $("twofaStart").hidden = !!st.setup_done;
    var en = $("twofaEnforce");
    en.hidden = !st.is_system_manager;
    en.textContent = st.enforced_for_admin ? "Matikan kewajiban 2FA untuk admin" : "Wajibkan 2FA untuk semua System Manager";
    en.dataset.on = st.enforced_for_admin ? "1" : "0";
    if (st.is_system_manager) {
      $("twofaStatus").innerHTML += "<br>Kewajiban 2FA untuk System Manager: <b>" + (st.enforced_for_admin ? "aktif" : "belum aktif") + "</b>.";
    }
  }

  async function load() {
    try { render(await call("status")); }
    catch (e) { $("twofaSection").hidden = true; }   // not logged in
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!$("twofaSection")) return;
    $("twofaStart").addEventListener("click", async function () {
      msg("Menyiapkan…");
      try {
        var r = await call("setup_start", {}, true);
        $("twofaQr").src = "data:image/svg+xml;base64," + r.qr_svg_base64;
        $("twofaSecret").textContent = r.secret;
        $("twofaSetup").hidden = false;
        msg("");
      } catch (e) { msg((e && e.message) || e, true); }
    });
    $("twofaVerifyForm").addEventListener("submit", async function (e) {
      e.preventDefault();
      try {
        render(await call("setup_verify", { code: e.target.code.value }, true));
        $("twofaSetup").hidden = true;
        msg("Berhasil. Simpan aplikasi authenticator Anda; tanpa itu Anda tidak bisa login bila 2FA diwajibkan.");
      } catch (err) { msg((err && err.message) || err, true); }
    });
    $("twofaEnforce").addEventListener("click", async function () {
      var turnOn = this.dataset.on !== "1";
      try {
        render(await call("set_admin_enforcement", { enable: turnOn ? 1 : 0 }, true));
        msg(turnOn ? "2FA kini wajib untuk semua System Manager." : "Kewajiban 2FA dimatikan.");
      } catch (err) { msg((err && err.message) || err, true); }
    });
    load();
  });
})();
