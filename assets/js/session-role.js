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
          pill.innerHTML =
            `User: ${
              safe(
                user.display_name
              )
            }<br>` +
            `Role: ${
              safe(user.role)
            }`;

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

  function applyRoleVisibility() {
    const user =
      getUser();

    const role =
      user
        ? user.role
        : "viewer";

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
