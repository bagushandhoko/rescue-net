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
    return /^[a-z0-9-]+\.html([?#][^\s\\]*)?$/i.test(next) && !next.startsWith("dms-login") ? next : "edisi-tertutup.html";
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

  document.querySelector("[data-forgot]").addEventListener("click", () =>
    show("Hubungi admin satker atau Pusdatin instansi Anda untuk memulihkan kata sandi."));

  async function sessionUser() {
    const r = await fetch(API + "rescue_net.api_auth.session_info", { credentials: "include", headers: { Accept: "application/json" }, cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const p = await r.json();
    return (p && p.message && p.message.user) || "Guest";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const usr = String(form.elements.usr.value || "").trim();
    const pwd = String(form.elements.pwd.value || "");
    if (!usr || !pwd) { show("Isi akun dan kata sandi.", "err"); (usr ? form.elements.pwd : form.elements.usr).focus(); return; }
    submit.disabled = true;
    submitLabel.textContent = "Memeriksa akun…";
    show("");
    try {
      const r = await fetch(API + "login", {
        method: "POST", credentials: "include",
        headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ usr, pwd }).toString()
      });
      const p = await r.json().catch(() => ({}));
      if (p && (p.verification || p.tmp_id)) {
        show("Akun ini memakai kode verifikasi. Silakan masuk lewat halaman login Rescue-Net.", "err");
        return;
      }
      if (!r.ok || p.exc_type) {
        show(r.status === 429 ? "Terlalu banyak percobaan. Tunggu sebentar lalu coba lagi." : "Login gagal. Periksa akun dan kata sandi.", "err");
        return;
      }
      if ((await sessionUser()) === "Guest") throw new Error("session missing");
      form.elements.pwd.value = "";
      show("Berhasil masuk. Membuka pusat kendali DMS…", "ok");
      location.replace(target());
    } catch (_) {
      show("Backend belum terjangkau. Periksa koneksi lalu coba lagi.", "err");
    } finally {
      submit.disabled = false;
      submitLabel.textContent = "Masuk";
    }
  });

  selectAgency(savedAgency());

  // Sudah login? Langsung ke pusat kendali.
  sessionUser().then((u) => { if (u && u !== "Guest") location.replace(target()); }).catch(() => {});
})();
