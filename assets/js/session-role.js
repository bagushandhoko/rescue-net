(function () {
  const FRAPPE_METHOD_BASE =
    location.origin +
    "/rescue-net-frappe/api/method";

  function safe(v) {
    return (
      v === null ||
      v === undefined ||
      v === ""
    )
      ? "n/a"
      : v;
  }

  function getUser() {
    try {
      return JSON.parse(
        localStorage.getItem(
          "RN_USER"
        ) || "null"
      );
    } catch (_) {
      return null;
    }
  }

  /*
   * Kept only for old page compatibility.
   * Frappe cookie is now authoritative.
   */
  function getSessionToken() {
    return "";
  }

  /*
   * Legacy X-RN-* headers are retired.
   */
  function getAuthHeaders() {
    return {};
  }

  function roleAllows(
    role,
    action
  ) {
    /*
     * System Manager is global authority
     * in the Frappe implementation.
     */
    if (
      role === "system_manager"
    ) {
      return true;
    }

    const rules = {
      // Pelapor Terverifikasi: report needs at any posko, nothing else
      verified_reporter: [
        "report_need"
      ],
      command_center: [
        "verify",
        "create_posko",
        "create_distribution",
        "create_stock",
        "create_medical",
        "create_shelter",
        "create_search_found",
        "create_work_tool",
        "create_donor_program",
        "upload_evidence",
        "ai_ask"
      ],

      posko_operator: [
        "create_stock",
        "create_distribution",
        "create_volunteer_assignment",
        "upload_evidence",
        "ai_ask"
      ],

      medical_operator: [
        "create_medical",
        "upload_evidence",
        "ai_ask"
      ],

      shelter_operator: [
        "create_shelter",
        "upload_evidence",
        "ai_ask"
      ],

      donor: [
        "create_aid_offer",
        "create_donor_program",
        "upload_evidence"
      ],

      volunteer: [
        "view_assignment"
      ],

      viewer: []
    };

    return (
      rules[role] || []
    ).includes(action);
  }

  function normalizeSession(
    session
  ) {
    if (!session) {
      return null;
    }

    const userId =
      session.user ||
      session.frappe_user ||
      session.rn_user_account ||
      session.user_id ||
      "";

    return {
      ...session,

      id:
        session.id ||
        userId,

      username:
        session.username ||
        userId,

      email:
        session.email ||
        (
          String(userId).includes("@")
            ? userId
            : null
        ),

      display_name:
        session.display_name ||
        session.full_name ||
        userId,

      role:
        session.role ||
        "viewer",

      organization_id:
        session.organization_id ??
        session.organization ??
        null,

      posko_id:
        session.posko_id ??
        session.posko ??
        null
    };
  }

  async function refreshSession() {
    try {
      const res = await fetch(
        FRAPPE_METHOD_BASE +
        "/rescue_net.api_auth.session_info",
        {
          method: "GET",

          credentials:
            "include",

          headers: {
            "Accept":
              "application/json"
          }
        }
      );

      if (
        res.status === 401 ||
        res.status === 403
      ) {
        localStorage.removeItem(
          "RN_FRAPPE_SESSION_MARKER"
        );

        localStorage.removeItem(
          "RN_USER"
        );

        refreshSessionUi();

        return null;
      }

      if (!res.ok) {
        throw new Error(
          await res.text()
        );
      }

      const payload =
        await res.json();

      const session =
        normalizeSession(
          Object.prototype
            .hasOwnProperty.call(
              payload,
              "message"
            )
            ? payload.message
            : payload
        );

      localStorage.removeItem(
        "RN_FRAPPE_SESSION_MARKER"
      );

      if (session) {
        localStorage.setItem(
          "RN_USER",
          JSON.stringify(session)
        );
      }

      refreshSessionUi();

      window.dispatchEvent(
        new CustomEvent(
          "rn:frappe-session",
          {
            detail: session
          }
        )
      );

      return session;

    } catch (err) {
      console.error(
        "[RN Session]",
        err
      );

      return null;
    }
  }

  async function requireSession() {
    const session =
      await refreshSession();

    if (session) {
      return session;
    }

    const next =
      encodeURIComponent(
        location.pathname +
        location.search +
        location.hash
      );

    let loginPath =
      "auth.html";

    if (
      !location.pathname.includes(
        "/pages/"
      )
    ) {
      loginPath =
        "pages/auth.html";
    }

    location.href =
      loginPath +
      "?next=" +
      next;

    return null;
  }

  function renderSessionPill() {
    const user =
      getUser();

    const topbars =
      document.querySelectorAll(
        ".topbar"
      );

    if (!topbars.length) {
      return;
    }

    topbars.forEach(
      topbar => {
        let pill =
          topbar.querySelector(
            "[data-rn-session-pill]"
          );

        if (!pill) {
          pill =
            document.createElement(
              "div"
            );

          pill.className =
            "status-pill";

          pill.setAttribute(
            "data-rn-session-pill",
            "true"
          );

          topbar.appendChild(
            pill
          );
        }

        if (user) {
          // audit SOP 12 Nov (S5): kode peran teknis (community_coordinator, viewer, ...) diganti nama peran Indonesia.
          const ROLE_ID = {
            viewer: "Pengguna", community_coordinator: "Koordinator komunitas", posko_operator: "Petugas posko",
            posko_admin: "Admin posko", org_admin: "Admin organisasi", organization_admin: "Admin organisasi",
            system_manager: "Super admin", administrator: "Super admin", volunteer: "Relawan", relawan: "Relawan",
            donor: "Donatur", reporter: "Pelapor", verifier: "Verifikator", logistics_officer: "Petugas logistik",
            medical_officer: "Petugas medis", control_centre: "Control Centre", guest: "Tamu",
            command_center: "Control Centre", medical_operator: "Petugas medis", shelter_operator: "Petugas shelter",
            verified_reporter: "Pelapor terverifikasi", logistics_operator: "Petugas logistik", kitchen_operator: "Petugas dapur", organization: "Akun organisasi", user: "Pengguna", system: "Sistem"
          };
          const rc = String(user.role || "").toLowerCase();
          const roleLabel = ROLE_ID[rc] || (rc ? rc.replace(/_/g, " ").replace(/^./, c => c.toUpperCase()) : "Pengguna");
          pill.innerHTML =
            `Masuk sebagai ${safe(user.display_name)}<br>` +
            `Peran: ${safe(roleLabel)}`;

        } else {
          let href =
            "auth.html";

          if (
            !location.pathname.includes(
              "/pages/"
            )
          ) {
            href =
              "pages/auth.html";
          }

          pill.innerHTML =
            `<a href="${href}">` +
            "Login</a>";
        }
      }
    );
  }

  /* owner 2026-11-09 (audit login nyata): petugas posko / pengelola organisasi sering berperan umum
     "viewer" — hak sebenarnya dari penugasan posko. Tampilkan form kerja posko untuk mereka;
     server tetap memeriksa izin per posko. */
  function effectiveRole(u) {
    if (!u) return "viewer";
    var r = u.role || "viewer";
    if ((r === "viewer" || r === "donor" || r === "volunteer") && (u.posko_id || u.manages_org)) return "posko_operator";
    return r;
  }

  function applyRoleVisibility() {
    const user =
      getUser();

    const role =
      effectiveRole(user);

    document
      .querySelectorAll(
        "[data-requires-role-action]"
      )
      .forEach(el => {
        const action =
          el.getAttribute(
            "data-requires-role-action"
          );

        el.style.display =
          roleAllows(
            role,
            action
          )
            ? ""
            : "none";
      });

    document
      .querySelectorAll(
        "[data-command-only]"
      )
      .forEach(el => {
        const allowed =
          role ===
            "command_center" ||
          role ===
            "system_manager";

        el.style.display =
          allowed
            ? ""
            : "none";
      });
  }

  function refreshSessionUi() {
    renderSessionPill();
    applyRoleVisibility();
  }

  window.RN_SESSION = {
    getUser,
    getSessionToken,
    getAuthHeaders,
    roleAllows,
    refresh:
      refreshSession,
    require:
      requireSession
  };

  document.addEventListener(
    "DOMContentLoaded",
    () => {
      /*
       * Render cached state immediately,
       * then reconcile against authoritative
       * Frappe session.
       */
      refreshSessionUi();

      refreshSession();
    }
  );

  window.addEventListener(
    "rn:session-changed",
    () => {
      refreshSession();
    }
  );

  window.addEventListener(
    "storage",
    refreshSessionUi
  );
})();
