// Halaman login DMS (Ming Ming 2026-11-23, owner: "halaman pertama langsung halaman login, latar penanganan bencana").
// Login nyata ke backend RN (Frappe /api/method/login, cookie sesi sama dengan modul RN).
(() => {
  "use strict";
  const API = "/rescue-net-frappe/api/method/";
  const TEMPLATE_KEY = "rn_dms_operation_template"; // dibaca rn-dms-menus.js bila organisasi belum punya template
  const AGENCIES = {
    bnpb: { name: "BNPB / BPBD", label: "Email / NIP / ID Pusdalops", ph: "nama@bpbd.go.id", accent: "#f97316", soft: "rgba(249,115,22,.15)", line: "rgba(249,115,22,.4)", ink: "#fff" },
    pmi: { name: "PMI", label: "Email / No. Registrasi PMI", ph: "nama@pmi.or.id", accent: "#ef4444", soft: "rgba(239,68,68,.15)", line: "rgba(239,68,68,.4)", ink: "#fff" },
    tni: { name: "TNI / POLRI", label: "Email / NRP / ID Satgas", ph: "nama@tni.mil.id", accent: "#84cc16", soft: "rgba(132,204,22,.15)", line: "rgba(132,204,22,.4)", ink: "#090e1a" },
    kementerian: { name: "Kementerian / Lembaga", label: "Email / NIP (.go.id)", ph: "nama@kementerian.go.id", accent: "#3b82f6", soft: "rgba(59,130,246,.15)", line: "rgba(59,130,246,.45)", ink: "#fff" }
  };
  const root = document.documentElement.style;
  const form = document.querySelector("[data-login-form]");
  const msg = document.querySelector("[data-msg]");
  const submit = document.querySelector("[data-submit]");
  const submitLabel = document.querySelector("[data-submit-label]");
  const tabs = [...document.querySelectorAll(".tab[data-agency]")];

  // Tujuan sesudah login: hanya halaman di folder pages (cegah open redirect).
  function target() {
    const next = new URLSearchParams(location.search).get("next") || "";
    return /^[a-z0-9-]+\.html([?#][^\s\\]*)?$/i.test(next) && !next.startsWith("dms-login") ? next : "";
  }

  function show(text, kind) {
    msg.hidden = !text;
    msg.textContent = text || "";
    msg.className = "msg" + (kind ? " " + kind : "");
  }

  function savedAgency() {
    try { const v = localStorage.getItem(TEMPLATE_KEY); if (AGENCIES[v]) return v; } catch (_) {}
    return "bnpb";
  }

  function selectAgency(key, focus) {
    const a = AGENCIES[key];
    if (!a) return;
    root.setProperty("--accent", a.accent);
    root.setProperty("--accent-soft", a.soft);
    root.setProperty("--accent-line", a.line);
    root.setProperty("--accent-ink", a.ink);
    tabs.forEach((t) => {
      const on = t.dataset.agency === key;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    document.querySelector("[data-agency-pill]").textContent = a.name;
    document.querySelector("[data-id-label]").textContent = a.label;
    form.elements.usr.placeholder = a.ph;
    try { localStorage.setItem(TEMPLATE_KEY, key); } catch (_) {}
    show("");
  }

  tabs.forEach((t, i) => {
    t.addEventListener("click", () => selectAgency(t.dataset.agency));
    t.addEventListener("keydown", (e) => {
      const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      selectAgency(tabs[(i + step + tabs.length) % tabs.length].dataset.agency, true);
    });
  });

  document.querySelector("[data-eye]").addEventListener("click", (e) => {
    const btn = e.currentTarget;
    const showing = form.elements.pwd.type === "text";
    form.elements.pwd.type = showing ? "password" : "text";
    btn.setAttribute("aria-pressed", String(!showing));
    btn.setAttribute("aria-label", showing ? "Tampilkan kata sandi" : "Sembunyikan kata sandi");
    btn.querySelector("use").setAttribute("href", showing ? "#i-eye" : "#i-eye-off");
  });

  // ===== Login = kode login RN (assets/js/auth.js): /api/method/login, 2FA tmp_id+otp, Google, lupa sandi, my_landing =====
  const FRAPPE = location.origin + "/rescue-net-frappe";
  const otpField = document.querySelector("[data-otp-field]");
  let pending2fa = null;

  const ID_MSG = [
    [/invalid login credentials|incorrect password|invalid password/i, "Email atau kata sandi salah."],
    [/user disabled|not allowed to login|account.*disabled/i, "Akun ini dinonaktifkan. Hubungi admin satker."],
    [/too many|rate limit|temporarily locked/i, "Terlalu banyak percobaan. Tunggu sebentar lalu coba lagi."],
    [/invalid verification code|incorrect verification code/i, "Kode verifikasi salah."]
  ];
  const translate = (m) => { for (const [re, t] of ID_MSG) if (re.test(m)) return t; return m; };
  function serverMessage(payload) { return translate(rawServerMessage(payload)); }
  function rawServerMessage(payload) {
    try {
      const list = JSON.parse(payload._server_messages || "[]");
      const first = list.length ? JSON.parse(list[0]) : null;
      if (first && first.message) return String(first.message).replace(/<[^>]*>/g, "").trim();
    } catch (_) {}
    const m = payload && (payload.message || payload.exception);
    return typeof m === "string" ? m.replace(/<[^>]*>/g, "").replace(/^[\w.]+Error:\s*/, "").trim() : "";
  }

  async function sessionInfo() {
    const r = await fetch(FRAPPE + "/api/method/rescue_net.api_auth.session_info", { credentials: "include", headers: { Accept: "application/json" }, cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return ((await r.json()) || {}).message || {};
  }

  // Sama dengan RN landingTarget(): ?next= menang; lalu halaman kerja pengguna (my_landing); lalu Control Centre.
  async function landing() {
    const next = target();
    if (next) return next;
    try {
      const r = await fetch(FRAPPE + "/api/method/rescue_net.api_auth.my_landing", { credentials: "include" });
      const m = r.ok ? (((await r.json()) || {}).message || {}) : {};
      if (m.latest_event) { try { localStorage.setItem("rn_active_event", m.latest_event); } catch (_) {} }
      if (m.href && m.href.indexOf("//") === -1) return m.href;
    } catch (_) {}
    return "war-room.html";
  }

  document.querySelector("[data-forgot]").addEventListener("click", (e) => {
    e.preventDefault();
    const email = String(form.elements.usr.value || "").trim();
    location.href = FRAPPE + "/update-password" + (email ? "?email=" + encodeURIComponent(email) : "");
  });

  // Google: login Google RN kembali ke rescue-net.online (sesi per domain), jadi DMS butuh serah sesi
  // sekali pakai dari backend RN (api_auth.dms_sso_*). Selama backend itu belum terpasang, beri tahu dengan jujur.
  document.querySelector("[data-google]").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const next = target() || "";
      const r = await fetch(FRAPPE + "/api/method/rescue_net.api_auth.dms_sso_google_url?next=" + encodeURIComponent(next), { credentials: "include", headers: { Accept: "application/json" } });
      const m = r.ok ? (((await r.json()) || {}).message || {}) : {};
      if (m.available && m.url) { location.href = m.url; return; }
      show(m.reason || "Login Google untuk DMS sedang disambungkan ke backend RN. Sementara gunakan email dan kata sandi akun RN.", "err");
    } catch (_) {
      show("Login Google untuk DMS sedang disambungkan. Sementara gunakan email dan kata sandi akun RN.", "err");
    }
    btn.disabled = false;
  });

  // Kembali dari Google lewat rescue-net.online: tukar tiket sekali pakai menjadi sesi di domain DMS.
  (async () => {
    const ticket = new URLSearchParams(location.search).get("sso");
    if (!ticket) return;
    show("Menyelesaikan login Google…");
    try {
      const r = await fetch(FRAPPE + "/api/method/rescue_net.api_auth.dms_sso_claim", {
        method: "POST", credentials: "include",
        headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ ticket }).toString()
      });
      const p = await r.json().catch(() => ({}));
      if (!r.ok || p.exc_type) throw new Error(serverMessage(p) || "Tiket login tidak berlaku.");
      const s = await sessionInfo();
      if (!s.user || s.user === "Guest") throw new Error("Sesi tidak terbentuk.");
      try { localStorage.setItem("RN_USER", JSON.stringify(s)); } catch (_) {}
      history.replaceState(null, "", location.pathname + (target() ? "?next=" + encodeURIComponent(target()) : ""));
      location.replace(await landing());
    } catch (err) {
      show("Login Google gagal: " + (err.message || err) + " Coba lagi atau pakai email dan kata sandi.", "err");
    }
  })();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const usr = String(form.elements.usr.value || "").trim();
    const pwd = String(form.elements.pwd.value || "");
    const otp = String(form.elements.otp.value || "").replace(/\s+/g, "");
    if (pending2fa ? !otp : (!usr || !pwd)) {
      show(pending2fa ? "Masukkan kode verifikasi 6 digit." : "Email dan kata sandi wajib diisi.", "err");
      (pending2fa ? form.elements.otp : usr ? form.elements.pwd : form.elements.usr).focus();
      return;
    }
    submit.disabled = true;
    submitLabel.textContent = "Memproses…";
    show("");
    try {
      const body = new URLSearchParams();
      if (pending2fa) { body.set("otp", otp); body.set("tmp_id", pending2fa); }
      else { body.set("usr", usr); body.set("pwd", pwd); }
      const r = await fetch(FRAPPE + "/api/method/login", {
        method: "POST", credentials: "include",
        headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString()
      });
      const p = await r.json().catch(() => ({}));
      if (p && p.verification && p.tmp_id) {
        pending2fa = p.tmp_id;
        otpField.hidden = false;
        form.elements.otp.value = "";
        form.elements.otp.focus();
        show("Masukkan kode 6 digit dari aplikasi authenticator Anda.");
        return;
      }
      if (!r.ok || p.exc_type) {
        if (pending2fa) { pending2fa = null; otpField.hidden = true; }
        show(r.status === 429 ? "Terlalu banyak percobaan. Tunggu sebentar lalu coba lagi."
          : (serverMessage(p) || "Email atau kata sandi salah."), "err");
        return;
      }
      pending2fa = null;
      const s = await sessionInfo();
      if (!s.user || s.user === "Guest") { show("Login berhasil tetapi sesi tidak terbentuk.", "err"); return; }
      try { localStorage.setItem("RN_USER", JSON.stringify(s)); } catch (_) {}
      window.dispatchEvent(new CustomEvent("rn:session-changed", { detail: { user: s } }));
      form.elements.pwd.value = "";
      show("Berhasil. Mengalihkan…", "ok");
      location.replace(await landing());
    } catch (_) {
      show("Backend belum terjangkau. Periksa koneksi lalu coba lagi.", "err");
    } finally {
      submit.disabled = false;
      submitLabel.textContent = "Masuk";
    }
  });

  selectAgency(savedAgency());

  // Sudah login? Langsung ke pusat kendali.
  sessionInfo().then(async (s) => { if (s.user && s.user !== "Guest") location.replace(await landing()); }).catch(() => {});
})();
