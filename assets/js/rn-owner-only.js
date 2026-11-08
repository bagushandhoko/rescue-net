/* rn-owner-only.js (owner 2026-11-02 23:15/23:20): pengaturan/form tulis tidak tampil ke tamu
   maupun pengguna login yang bukan pengelola.
   - [data-login-only]  : hanya untuk pengguna login (form "buat baru" milik sendiri; server
                          tetap memeriksa kepemilikan organisasi/posko).
   - [data-owner-only]  : hanya setelah halaman memanggil RN_OWNER_ONLY.grant() — yaitu ketika
                          API mengembalikan can_manage/can_edit untuk data yang sedang dibuka. */
(function () {
  "use strict";
  var root = document.documentElement;
  var st = document.createElement("style");
  st.textContent = "html:not(.rn-logged-in) [data-login-only]{display:none!important}" +
    "html:not(.rn-can-operate) [data-owner-only]{display:none!important}";
  (document.head || root).appendChild(st);
  window.RN_OWNER_ONLY = {
    grant: function (on) { root.classList.toggle("rn-can-operate", on !== false); },
    loggedIn: function () { return root.classList.contains("rn-logged-in"); }
  };
  if (window.RN_FRAPPE && window.RN_FRAPPE.call) {
    window.RN_FRAPPE.call("rescue_net.api_auth.session_info", {}).then(function (d) {
      if (d && d.user && d.user !== "Guest") root.classList.add("rn-logged-in");
    }).catch(function () {});
  }
})();
