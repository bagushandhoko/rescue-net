/* Rescue-Net — Masuk & Registrasi (pages/auth.html)
 * Redesigned 2026-09-01 to match assets/img/mockup/login & registrasi.png.
 * Login uses Frappe /api/method/login; Daftar uses the guest endpoint
 * rescue_net.api_auth.register, then auto-logs-in with the same credentials.
 */
(function () {
  "use strict";

  var FRAPPE_BASE = location.origin + "/rescue-net-frappe";

  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }
  function safe(v) {
    return v === null || v === undefined || v === "" ? "n/a" : v;
  }
  function statusMsg(msg) {
    var el = document.getElementById("authStatus");
    if (el) el.textContent = msg;
  }
  function setMessage(id, msg, isError) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("is-error", !!isError);
    el.classList.toggle("is-ok", !!msg && !isError);
  }

  /* ---------- next= redirect target (relative only) ---------- */
  function nextTarget() {
    try {
      var raw = new URLSearchParams(location.search).get("next") || "";
      raw = decodeURIComponent(raw);
      if (raw && raw.indexOf("//") === -1) return raw;
    } catch (e) {}
    return "../index.html";
  }

  // After login (owner 2026-10-19): straight to the user's own posko page on
  // the newest disaster they handle. An explicit ?next= still wins.
  async function landingTarget() {
    try {
      var raw = new URLSearchParams(location.search).get("next") || "";
      if (raw && decodeURIComponent(raw).indexOf("//") === -1) return decodeURIComponent(raw);
    } catch (e) {}
    try {
      var res = await fetch(FRAPPE_BASE + "/api/method/rescue_net.api_auth.my_landing", { credentials: "include" });
      var m = res.ok ? ((await res.json()) || {}).message || {} : {};
      if (m.latest_event) { try { localStorage.setItem("rn_active_event", m.latest_event); } catch (e) {} }
      if (m.href) return m.href;
    } catch (e) {}
    return nextTarget();
  }

  // A fresh registrant's very next task depends on their chosen role: a
  // Petugas Posko exists to register a real posko, a Donatur exists to
  // give — send them straight there instead of a generic homepage. An
  // explicit ?next= (e.g. they were bounced here mid-flow) still wins.
  var ROLE_LANDING_PAGE = {
    relawan: "management-relawan.html",
    petugas_posko: "registrasi-posko.html",
    donatur: "program-khusus.html",
    organisasi: "organisasi-posko.html",
    pelapor: "posko-logistik.html"
  };
  function registerLandingTarget(role, poskoType) {
    try {
      var raw = new URLSearchParams(location.search).get("next") || "";
      raw = decodeURIComponent(raw);
      if (raw && raw.indexOf("//") === -1) return raw;
    } catch (e) {}
    var page = ROLE_LANDING_PAGE[role] || "../index.html";
    if (role === "petugas_posko" && poskoType) {
      // poskoType = daftar jenis terpilih (array) atau satu jenis (string)
      var list = Array.isArray(poskoType) ? poskoType : [poskoType];
      if (list.length) {
        page += "?type=" + encodeURIComponent(list[0]);
        if (list.length > 1) page += "&more=" + encodeURIComponent(list.slice(1).join(","));
      }
    }
    return page;
  }

  /* ---------- Frappe requests ---------- */
  async function frappeRequest(path, options) {
    options = options || {};
    var res = await fetch(FRAPPE_BASE + path, {
      credentials: "include",
      headers: Object.assign({ Accept: "application/json" }, options.headers || {}),
      method: options.method || "GET",
      body: options.body
    });
    var text = await res.text();
    var payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (_) {
      payload = { message: text };
    }
    if (!res.ok) {
      var err = new Error(
        (payload && (payload._server_messages || payload.message || payload.exception)) ||
          ("Frappe HTTP " + res.status)
      );
      err.status = res.status;
      err.payload = payload;
      throw err;
    }
    return Object.prototype.hasOwnProperty.call(payload, "message") ? payload.message : payload;
  }

  function cleanServerMessage(err) {
    var msg = err && err.message ? String(err.message) : "Terjadi kesalahan.";
    try {
      if (msg.charAt(0) === "[") {
        var arr = JSON.parse(msg);
        if (Array.isArray(arr) && arr.length) {
          var first = arr[0];
          if (typeof first === "string") {
            try { first = JSON.parse(first); } catch (_) { first = { message: first }; }
          }
          if (first && first.message) msg = first.message;
        }
      }
    } catch (_) {}
    return msg.replace(/<[^>]*>/g, "").trim();
  }

  async function loadSession() {
    try {
      var s = await frappeRequest("/api/method/rescue_net.api_auth.session_info");
      if (s && s.user && s.user !== "Guest") {
        try { localStorage.setItem("RN_USER", JSON.stringify(s)); } catch (e) {}
        return s;
      }
      return null;
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        try { localStorage.removeItem("RN_USER"); } catch (e) {}
        return null;
      }
      throw err;
    }
  }

  async function login(email, password) {
    var body = new URLSearchParams();
    body.set("usr", String(email || "").trim());
    body.set("pwd", String(password || ""));
    await frappeRequest("/api/method/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });
    var user = await loadSession();
    if (!user) throw new Error("Login berhasil tetapi sesi tidak terbentuk.");
    window.dispatchEvent(new CustomEvent("rn:session-changed", { detail: { user: user } }));
    return user;
  }

  async function logout() {
    try {
      await frappeRequest("/api/method/logout");
    } catch (e) {}
    try { localStorage.removeItem("RN_USER"); } catch (e) {}
    window.dispatchEvent(new CustomEvent("rn:session-changed"));
    location.reload();
  }

  async function register(payload) {
    return frappeRequest("/api/method/rescue_net.api_auth.register", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(payload).toString()
    });
  }

  /* ---------- UI: session vs forms ---------- */
  function renderSession(s) {
    var grid = document.getElementById("authGrid");
    var footer = document.querySelector(".rn-auth-footer");
    var panel = document.getElementById("sessionPanel");
    var box = document.getElementById("currentUser");
    var headerLogout = document.getElementById("logoutBtn");

    if (!s) {
      if (grid) grid.hidden = false;
      if (footer) footer.hidden = false;
      if (panel) panel.hidden = true;
      if (headerLogout) headerLogout.hidden = true;
      return;
    }

    if (grid) grid.hidden = true;
    if (footer) footer.hidden = true;
    if (panel) panel.hidden = false;
    if (headerLogout) headerLogout.hidden = false;

    var pending =
      s.role_request_status && String(s.role_request_status).toLowerCase() === "pending"
        ? "<div><span>Peran diminta</span><b>" +
          safe(s.requested_role === "pelapor" ? "Pelapor Terverifikasi" : s.requested_role) +
          " (menunggu verifikasi)</b></div>"
        : "";

    if (box) {
      box.innerHTML =
        "<div><span>User</span><b>" + safe(s.user) + "</b></div>" +
        "<div><span>Role</span><b>" + safe(s.role) + "</b></div>" +
        "<div><span>Organisasi</span><b>" + safe(s.organization_id) + "</b></div>" +
        "<div><span>Posko</span><b>" + safe(s.posko_id) + "</b></div>" +
        pending;
    }
    statusMsg("Sesi aktif sebagai " + safe(s.user) + ".");
  }

  /* ---------- tabs ---------- */
  function switchTab(name) {
    $all("[data-auth-pane]").forEach(function (pane) {
      pane.hidden = pane.getAttribute("data-auth-pane") !== name;
    });
    $all(".rn-auth-tab").forEach(function (tab) {
      var on = tab.getAttribute("data-auth-tab") === name;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
    });
    setMessage("loginMessage", "");
    setMessage("registerMessage", "");
  }

  /* ---------- password helpers ---------- */
  function wirePwToggles() {
    $all(".rn-auth-pw-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var input = btn.parentNode.querySelector("input");
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.classList.toggle("is-on", show);
        btn.setAttribute("aria-label", show ? "Sembunyikan password" : "Tampilkan password");
      });
    });
  }

  function pwChecks(pw) {
    return {
      len: (pw || "").length >= 8,
      upper: /[A-Z]/.test(pw || ""),
      digit: /[0-9]/.test(pw || "")
    };
  }
  function renderPwRules(pw) {
    var list = document.getElementById("pwRules");
    if (!list) return;
    var c = pwChecks(pw);
    $all("li", list).forEach(function (li) {
      var ok = !!c[li.getAttribute("data-rule")];
      li.classList.toggle("is-ok", ok);
      var i = li.querySelector("i");
      if (i) i.innerHTML = ok ? "&#10003;" : "&#9675;";
    });
  }

  /* ---------- Google login/register ---------- */
  async function goToGoogle(btn) {
    var original = btn.textContent;
    try {
      btn.classList.add("is-disabled");
      // redirect_to becomes a server-side `Location:` header resolved
      // against the OAuth callback's own URL, not this page — must be
      // absolute, not the relative path nextTarget() returns for our own
      // client-side use.
      var absoluteNext = new URL(nextTarget(), window.location.href).href;
      var r = await frappeRequest(
        "/api/method/rescue_net.api_auth.social_login_url?provider=google&redirect_to=" +
          encodeURIComponent(absoluteNext)
      );
      if (!r || !r.available || !r.url) {
        statusMsg((r && r.reason) || "Login Google belum tersedia.");
        btn.classList.remove("is-disabled");
        return;
      }
      window.location.href = r.url;
    } catch (err) {
      statusMsg("Gagal membuka login Google: " + cleanServerMessage(err));
      btn.classList.remove("is-disabled");
    }
  }

  function wireGoogleButtons() {
    ["googleLoginBtn", "googleRegisterBtn"].forEach(function (id) {
      var btn = document.getElementById(id);
      if (!btn) return;
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        goToGoogle(btn);
      });
    });
  }

  /* ---------- referensi verifikasi (progressive disclosure) ---------- */
  function wireReferenceToggle() {
    var chk = document.getElementById("consentVerificationChk");
    var wrap = document.getElementById("referenceFields");
    if (!chk || !wrap) return;
    chk.addEventListener("change", function () {
      wrap.hidden = !chk.checked;
    });
  }

  /* Pelapor Terverifikasi: instansi/jabatan/wilayah + a reference the verifier can call */
  function wireReporterToggle() {
    var wrap = document.getElementById("reporterFields");
    var chk = document.getElementById("consentVerificationChk");
    var refs = document.getElementById("referenceFields");
    var typeWrap = document.getElementById("poskoTypeFields");
    var orgWrap = document.getElementById("orgFields");
    if (!wrap) return;
    $all('input[name="role"]').forEach(function (r) {
      r.addEventListener("change", function () {
        if (typeWrap && r.checked) typeWrap.hidden = r.value !== "petugas_posko";
        if (orgWrap && r.checked) orgWrap.hidden = r.value !== "organisasi";
        var on = r.value === "pelapor" && r.checked;
        if (r.checked) wrap.hidden = !on;
        if (on && chk && !chk.checked) { chk.checked = true; if (refs) refs.hidden = false; }
      });
    });
  }

  /* ---------- init ---------- */
  async function init() {
    wirePwToggles();
    wireGoogleButtons();
    wireReferenceToggle();
    wireReporterToggle();

    $all("[data-auth-tab]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        switchTab(el.getAttribute("data-auth-tab"));
      });
    });

    // deep links from the manual (2026-10-26): auth.html#daftar opens the
    // Daftar tab; #daftar-<peran> also picks that role (organisasi, relawan…)
    var hm = /^#daftar(?:-([a-z_]+))?$/.exec(location.hash || "");
    if (hm) {
      switchTab("register");
      var roleRadio = hm[1] && document.querySelector('#registerForm input[name="role"][value="' + hm[1].replace("-", "_") + '"]');
      if (roleRadio) {
        roleRadio.checked = true;
        roleRadio.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    var regPw = document.querySelector('#registerForm input[name="password"]');
    if (regPw) {
      regPw.addEventListener("input", function () {
        renderPwRules(regPw.value);
      });
    }

    var forgot = document.getElementById("forgotLink");
    if (forgot) {
      forgot.addEventListener("click", function (e) {
        e.preventDefault();
        var input = document.querySelector('#loginForm input[name="email"]');
        var email = input ? input.value : "";
        window.location.href =
          FRAPPE_BASE + "/update-password" +
          (email ? "?email=" + encodeURIComponent(email) : "");
      });
    }

    [document.getElementById("logoutBtn"), document.getElementById("sessionLogout")].forEach(
      function (b) {
        if (b) b.addEventListener("click", function () { logout(); });
      }
    );

    /* login submit */
    var loginForm = document.getElementById("loginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        var f = loginForm.elements;
        var email = (f.email.value || "").trim();
        var pass = f.password.value || "";
        if (!email || !pass) {
          setMessage("loginMessage", "Email dan password wajib diisi.", true);
          return;
        }
        var btn = loginForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        setMessage("loginMessage", "Memproses…");
        try {
          await login(email, pass);
          setMessage("loginMessage", "Berhasil. Mengalihkan…");
          window.location.href = await landingTarget();
        } catch (err) {
          setMessage("loginMessage", cleanServerMessage(err) || "Email atau password salah.", true);
          btn.disabled = false;
        }
      });
    }

    /* register submit */
    var registerForm = document.getElementById("registerForm");
    if (registerForm) {
      registerForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        var f = registerForm.elements;
        var full_name = (f.full_name.value || "").trim();
        var email = (f.email.value || "").trim();
        var phoneDigits = (f.phone.value || "").replace(/[^0-9]/g, "");
        var pass = f.password.value || "";
        var roleEl = registerForm.querySelector('input[name="role"]:checked');
        var role = roleEl ? roleEl.value : "relawan";
        var consentEl = registerForm.querySelector('input[name="consent_verification"]');
        var consentVerification = consentEl && consentEl.checked ? 1 : 0;
        var referenceName = consentVerification ? (f.reference_name.value || "").trim() : "";
        var referenceRelation = consentVerification ? (f.reference_relation.value || "").trim() : "";
        var referenceContact = consentVerification ? (f.reference_contact.value || "").trim() : "";

        if (!full_name || !email || !pass) {
          setMessage("registerMessage", "Nama, email, dan password wajib diisi.", true);
          return;
        }
        var reporterAgency = role === "pelapor" ? (f.reporter_agency.value || "").trim() : "";
        var reporterPosition = role === "pelapor" ? (f.reporter_position.value || "").trim() : "";
        var reporterArea = role === "pelapor" ? (f.reporter_area.value || "").trim() : "";
        if (role === "pelapor" && !(reporterAgency && reporterPosition)) {
          setMessage("registerMessage", "Pelapor terverifikasi wajib mengisi instansi/kelompok dan jabatan/peran.", true);
          return;
        }
        var poskoTypes = role === "petugas_posko"
          ? $all('input[name="posko_types"]:checked', registerForm).map(function (c) { return c.value; })
          : [];
        if (role === "petugas_posko" && !poskoTypes.length) {
          setMessage("registerMessage", "Pilih minimal satu jenis posko yang akan Anda kelola.", true);
          return;
        }
        var orgTitle = role === "organisasi" ? (f.org_title.value || "").trim() : "";
        if (role === "organisasi" && !orgTitle) {
          setMessage("registerMessage", "Nama organisasi wajib diisi.", true);
          return;
        }
        var c = pwChecks(pass);
        if (!c.len || !c.upper || !c.digit) {
          setMessage("registerMessage", "Password belum memenuhi semua syarat.", true);
          renderPwRules(pass);
          return;
        }

        var phone = phoneDigits ? "+62" + phoneDigits.replace(/^0+/, "") : "";
        var btn = registerForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        setMessage("registerMessage", "Membuat akun…");
        try {
          var out = await register({
            full_name: full_name,
            email: email,
            phone: phone,
            password: pass,
            role: role,
            consent_verification: consentVerification,
            reference_name: referenceName,
            reference_relation: referenceRelation,
            reference_contact: referenceContact,
            reporter_agency: reporterAgency,
            reporter_position: reporterPosition,
            reporter_area: reporterArea
          });
          setMessage("registerMessage", (out && out.message) || "Akun dibuat. Masuk…");
          await login(email, pass);
          if (orgTitle) {
            try {
              await RN_FRAPPE.call("rescue_net.api_community_cluster.create_organization", {
                title: orgTitle,
                organization_type: f.org_type.value || "community",
                contact_person: (f.org_contact.value || "").trim() || null,
                notes: (f.org_notes.value || "").trim() || null,
                coordination_scheme: (registerForm.querySelector('input[name="org_scheme"]:checked') || {}).value || "mandiri",
                open_to_public: (registerForm.querySelector('input[name="org_open"]:checked') || {}).value || "0"
              }, { method: "POST" });
            } catch (orgErr) {
              setMessage("registerMessage", "Akun dibuat, tetapi organisasi belum tersimpan: " + cleanServerMessage(orgErr) + " Lengkapi di halaman Organisasi.", true);
              await new Promise(function (ok) { setTimeout(ok, 2500); });
            }
          }
          window.location.href = registerLandingTarget(role, poskoTypes);
        } catch (err) {
          setMessage("registerMessage", cleanServerMessage(err), true);
          btn.disabled = false;
        }
      });
    }

    /* session check */
    try {
      var s = await loadSession();
      renderSession(s);
      if (!s) statusMsg("Silakan masuk atau daftar.");
    } catch (err) {
      renderSession(null);
      statusMsg(cleanServerMessage(err));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

/* "Bergabung sesuai peran Anda": a role tile opens the Daftar tab with that role chosen */
document.addEventListener("click", function (e) {
  var t = e.target.closest("[data-pick-role]");
  if (!t) return;
  var radio = document.querySelector('#registerForm input[name="role"][value="' + t.getAttribute("data-pick-role") + '"]');
  if (radio) {
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }
  var form = document.getElementById("registerForm");
  if (form && form.scrollIntoView) form.scrollIntoView({ behavior: "smooth", block: "start" });
});
