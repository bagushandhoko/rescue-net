(function () {
  function safe(v) {
    return v === null || v === undefined || v === "" ? "n/a" : v;
  }

  function getUser() {
    try {
      return JSON.parse(localStorage.getItem("RN_USER") || "null");
    } catch (e) {
      return null;
    }
  }

  function roleAllows(role, action) {
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

    return (rules[role] || []).includes(action);
  }


  function getSessionToken() {
    return localStorage.getItem("RN_SESSION_TOKEN") || "";
  }

  function getAuthHeaders() {
    const user = getUser();
    const token = getSessionToken();
    const headers = {};

    if (token) headers["X-RN-Session-Token"] = token;
    if (user && user.id) headers["X-RN-User-Id"] = user.id;
    if (user && user.role) headers["X-RN-Role"] = user.role;

    return headers;
  }

  function shouldAttachAuth(input) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    return url.includes(":8092") || url.startsWith("/api/") || url.startsWith("/auth/");
  }

  function installAuthenticatedFetch() {
    if (window.__RN_AUTH_FETCH_INSTALLED__) return;
    if (!window.fetch) return;

    const nativeFetch = window.fetch.bind(window);
    window.fetch = function rnAuthenticatedFetch(input, init = {}) {
      if (!shouldAttachAuth(input)) {
        return nativeFetch(input, init);
      }

      const headers = new Headers(init.headers || (input && input.headers) || {});
      Object.entries(getAuthHeaders()).forEach(([key, value]) => {
        if (value && !headers.has(key)) headers.set(key, value);
      });

      return nativeFetch(input, { ...init, headers });
    };

    window.__RN_AUTH_FETCH_INSTALLED__ = true;
  }

  function renderSessionPill() {
    const user = getUser();

    const topbars = document.querySelectorAll(".topbar");
    if (!topbars.length) return;

    topbars.forEach(topbar => {
      let pill = topbar.querySelector("[data-rn-session-pill]");
      if (!pill) {
        pill = document.createElement("div");
        pill.className = "status-pill";
        pill.setAttribute("data-rn-session-pill", "true");
        topbar.appendChild(pill);
      }

      if (user) {
        pill.innerHTML = `User: ${safe(user.display_name)}<br>Role: ${safe(user.role)}`;
      } else {
        pill.innerHTML = `<a href="auth.html">Login</a>`;
        if (location.pathname.endsWith("/index.html") || location.pathname.endsWith("/rescue-net/")) {
          pill.innerHTML = `<a href="pages/auth.html">Login</a>`;
        }
      }

    });
  }

  function applyRoleVisibility() {
    const user = getUser();
    const role = user ? user.role : "viewer";

    document.querySelectorAll("[data-requires-role-action]").forEach(el => {
      const action = el.getAttribute("data-requires-role-action");
      if (!roleAllows(role, action)) {
        el.style.display = "none";
      }
    });

    document.querySelectorAll("[data-command-only]").forEach(el => {
      if (role !== "command_center") {
        el.style.display = "none";
      }
    });
  }

  window.RN_SESSION = {
    getUser,
    getSessionToken,
    getAuthHeaders,
    roleAllows
  };

  installAuthenticatedFetch();

  function refreshSessionUi() {
    renderSessionPill();
    applyRoleVisibility();
  }

  document.addEventListener("DOMContentLoaded", refreshSessionUi);
  window.addEventListener("rn:session-changed", refreshSessionUi);
  window.addEventListener("storage", refreshSessionUi);
})();
