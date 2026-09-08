/* ============================================================
 * notifikasi-settings.js — WhatsApp gateway config for Rescue-Net.
 * System Manager only. Talks to rescue_net.api_notify.*
 * ============================================================ */
(function () {
  "use strict";

  var BASE = location.origin + "/rescue-net-frappe/api/method";
  var SESSION = null;

  function $(id) { return document.getElementById(id); }
  function msg(t) { var e = $("nsStatus"); if (e) e.textContent = t; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  async function call(method, args, write) {
    args = args || {};
    var url = BASE + "/" + method;
    var headers = { Accept: "application/json" };
    var opts = { credentials: "same-origin", headers: headers };
    if (write) {
      if (!SESSION || !SESSION.csrf_token) throw new Error("Sesi Frappe belum siap.");
      headers["Content-Type"] = "application/json";
      headers["X-Frappe-CSRF-Token"] = SESSION.csrf_token;
      opts.method = "POST";
      opts.body = JSON.stringify(args);
    } else {
      var q = new URLSearchParams();
      Object.keys(args).forEach(function (k) {
        if (args[k] !== null && args[k] !== undefined && args[k] !== "") q.set(k, args[k]);
      });
      if (q.toString()) url += "?" + q.toString();
    }
    var res = await fetch(url, opts);
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.message || data.exception || ("Frappe API error " + res.status));
    return Object.prototype.hasOwnProperty.call(data, "message") ? data.message : data;
  }

  async function ensureSession() {
    if (SESSION) return SESSION;
    SESSION = await call("rescue_net.api_ai.session_info");
    return SESSION;
  }

  function currentScope() {
    return ($("nsScope").value || "global").trim() || "global";
  }

  function renderStatus(payload) {
    var s = (payload && payload.setting) || {};
    var box = $("nsCurrent");
    box.innerHTML =
      row("Scope", esc(payload.scope || "global")) +
      row("Provider", esc(s.provider || "simulasi")) +
      row("Aktif", s.enabled ? "ya" : "tidak") +
      row("Endpoint", esc(s.api_base || "(default provider)")) +
      row("Sender ID", esc(s.sender_id || "—")) +
      row("Token", s.token_set ? ("tersimpan ****" + esc(s.token_last4 || "")) : "belum ada") +
      (payload.exists ? "" : row("Catatan", "belum pernah disimpan — memakai simulasi"));

    var f = $("nsForm");
    f.provider.value = s.provider || "simulasi";
    f.enabled.checked = !!s.enabled;
    f.api_base.value = s.api_base || "";
    f.sender_id.value = s.sender_id || "";
    f.note.value = s.note || "";
    f.api_token.value = "";
    f.api_token.placeholder = s.token_set ? "(biarkan kosong untuk menyimpan token lama)" : "tempel token gateway";
  }

  function row(k, v) {
    return "<div><span>" + esc(k) + "</span><b>" + v + "</b></div>";
  }

  async function load() {
    try {
      await ensureSession();
      msg("Memuat konfigurasi…");
      var payload = await call("rescue_net.api_notify.get_notification_setting", { scope: currentScope() });
      renderStatus(payload);
      msg("Siap.");
    } catch (e) {
      msg("Gagal memuat: " + (e && e.message || e));
    }
  }

  async function save(ev) {
    ev.preventDefault();
    var f = ev.target;
    try {
      await ensureSession();
      msg("Menyimpan…");
      var out = await call("rescue_net.api_notify.save_notification_setting", {
        scope: currentScope(),
        provider: f.provider.value,
        enabled: f.enabled.checked ? 1 : 0,
        api_base: f.api_base.value.trim(),
        api_token: f.api_token.value.trim(),
        sender_id: f.sender_id.value.trim(),
        note: f.note.value.trim(),
      }, true);
      msg("Tersimpan ✓ (" + out.provider + (out.enabled ? ", aktif)" : ", nonaktif)"));
      load();
    } catch (e) {
      msg("Gagal simpan: " + (e && e.message || e));
    }
  }

  async function sendTest() {
    var to = ($("nsTestTo").value || "").trim();
    if (!to) { $("nsTestMsg").textContent = "Isi nomor tujuan dulu."; return; }
    try {
      await ensureSession();
      $("nsTestMsg").textContent = "Mengirim…";
      var r = await call("rescue_net.api_notify.send_test_whatsapp", { to: to, scope: currentScope() }, true);
      $("nsTestMsg").textContent =
        "Hasil: " + r.status +
        (r.provider ? " · provider " + r.provider : "") +
        (r.provider_message_id ? " · id " + r.provider_message_id : "") +
        (r.error ? " · " + r.error : "") +
        (r.status === "simulated" ? " (dicatat di RN Notification Log, tidak benar-benar dikirim)" : "");
    } catch (e) {
      $("nsTestMsg").textContent = "Gagal: " + (e && e.message || e);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("nsForm").addEventListener("submit", save);
    $("nsReload").addEventListener("click", load);
    $("nsScope").addEventListener("change", load);
    $("nsTestBtn").addEventListener("click", sendTest);
    load();
  });
})();
