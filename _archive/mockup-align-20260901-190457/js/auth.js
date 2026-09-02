const RN_FRAPPE_BASE =
  location.origin + "/rescue-net-frappe";

function statusMsg(msg) {
  const el =
    document.getElementById("authStatus");

  if (el) {
    el.textContent = msg;
  }
}

function safe(v) {
  return (
    v === null ||
    v === undefined ||
    v === ""
  )
    ? "n/a"
    : v;
}

async function frappeRequest(
  path,
  options = {}
) {
  const config = {
    credentials: "include",
    headers: {
      "Accept": "application/json",
      ...(options.headers || {})
    },
    ...options
  };

  const res = await fetch(
    RN_FRAPPE_BASE + path,
    config
  );

  const text = await res.text();

  let payload = {};

  try {
    payload = text
      ? JSON.parse(text)
      : {};
  } catch (_) {
    payload = {
      message: text
    };
  }

  if (!res.ok) {
    const err = new Error(
      payload.message ||
      payload.exception ||
      `Frappe HTTP ${res.status}`
    );

    err.status = res.status;
    err.payload = payload;

    throw err;
  }

  return (
    Object.prototype.hasOwnProperty.call(
      payload,
      "message"
    )
      ? payload.message
      : payload
  );
}

function normalizeSession(session) {
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

async function loadSession() {
  try {
    const session =
      await frappeRequest(
        "/api/method/" +
        "rescue_net.api_auth.session_info"
      );

    const user =
      normalizeSession(session);

    if (user) {
      localStorage.setItem(
        "RN_USER",
        JSON.stringify(user)
      );
    }

    /*
     * Legacy token MUST NOT remain
     * authoritative after Frappe cutover.
     */
    localStorage.removeItem(
      "RN_FRAPPE_SESSION_MARKER"
    );

    return user;

  } catch (err) {
    if (
      err.status === 401 ||
      err.status === 403
    ) {
      localStorage.removeItem(
        "RN_FRAPPE_SESSION_MARKER"
      );

      localStorage.removeItem(
        "RN_USER"
      );

      return null;
    }

    throw err;
  }
}

async function login(
  username,
  password
) {
  statusMsg(
    "Logging in to Frappe..."
  );

  const body =
    new URLSearchParams();

  body.set(
    "usr",
    String(username || "").trim()
  );

  body.set(
    "pwd",
    String(password || "")
  );

  await frappeRequest(
    "/api/method/login",
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/x-www-form-urlencoded"
      },

      body
    }
  );

  const user =
    await loadSession();

  if (!user) {
    throw new Error(
      "Login berhasil tetapi session " +
      "Frappe tidak terbentuk."
    );
  }

  window.dispatchEvent(
    new CustomEvent(
      "rn:session-changed",
      {
        detail: {
          user
        }
      }
    )
  );

  statusMsg(
    "Logged in as " +
    safe(user.display_name)
  );

  renderUser({
    user
  });

  return user;
}

async function logout() {
  try {
    await frappeRequest(
      "/api/method/logout",
      {
        method: "GET"
      }
    );
  } catch (err) {
    console.warn(
      "[RN Auth] Frappe logout:",
      err
    );
  }

  localStorage.removeItem(
    "RN_FRAPPE_SESSION_MARKER"
  );

  localStorage.removeItem(
    "RN_USER"
  );

  window.dispatchEvent(
    new CustomEvent(
      "rn:session-changed"
    )
  );

  renderUser(null);

  statusMsg(
    "Logged out."
  );
}

function renderUser(data) {
  const el =
    document.getElementById(
      "currentUser"
    );

  if (!el) {
    return;
  }

  if (
    !data ||
    !data.user
  ) {
    el.innerHTML = `
      <div>
        <span>Status</span>
        <b>Not logged in</b>
      </div>
    `;

    return;
  }

  const u = data.user;

  el.innerHTML = `
    <div>
      <span>User</span>
      <b>${safe(u.display_name)}</b>
    </div>

    <div>
      <span>Username</span>
      <b>${safe(u.username)}</b>
    </div>

    <div>
      <span>Role</span>
      <b>${safe(u.role)}</b>
    </div>

    <div>
      <span>Organization</span>
      <b>${safe(u.organization_id)}</b>
    </div>

    <div>
      <span>Posko</span>
      <b>${safe(u.posko_id)}</b>
    </div>

    <div>
      <span>Email</span>
      <b>${safe(u.email)}</b>
    </div>
  `;
}

function renderRoles(data) {
  const el =
    document.getElementById(
      "roleList"
    );

  if (!el) {
    return;
  }

  const roles =
    data?.roles || [];

  el.innerHTML =
    roles.map(r => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>
              ${safe(
                r.label || r.role
              )}
            </h4>

            <p>
              Role:
              ${safe(r.role)}
              <br>

              Scope:
              ${safe(r.scope)}
              <br>

              Can verify:
              ${safe(r.can_verify)}
              <br>

              Can view sensitive:
              ${safe(
                r.can_view_sensitive
              )}
            </p>
          </div>

          <div class="chips">
            <span class="chip warning">
              ${safe(r.role)}
            </span>
          </div>
        </div>
      </article>
    `).join("");
}

async function loadRoles() {
  const data =
    await frappeRequest(
      "/api/method/" +
      "rescue_net.api_auth.roles"
    );

  renderRoles(data || {});
}

function installFrappeLoginForm() {
  if (
    document.getElementById(
      "rnFrappeLoginForm"
    )
  ) {
    return;
  }

  const currentUser =
    document.getElementById(
      "currentUser"
    );

  if (!currentUser) {
    return;
  }

  const form =
    document.createElement(
      "form"
    );

  form.id =
    "rnFrappeLoginForm";

  form.className =
    "event-card";

  form.innerHTML = `
    <div class="event-main">
      <div style="
        width:100%;
        display:grid;
        gap:10px;
      ">
        <h4>
          Rescue-Net Login
        </h4>

        <label>
          Email / Username
          <input
            id="rnFrappeUsername"
            name="username"
            type="text"
            autocomplete="username"
            required
            style="width:100%;"
          >
        </label>

        <label>
          Password
          <input
            id="rnFrappePassword"
            name="password"
            type="password"
            autocomplete="current-password"
            required
            style="width:100%;"
          >
        </label>

        <button
          type="submit"
          class="btn primary"
        >
          Login
        </button>
      </div>
    </div>
  `;

  currentUser.parentNode.insertBefore(
    form,
    currentUser
  );

  form.addEventListener(
    "submit",
    async event => {
      event.preventDefault();

      const username =
        form.elements.username.value.trim();

      const password =
        form.elements.password.value;

      if (
        !username ||
        !password
      ) {
        statusMsg(
          "Username dan password wajib diisi."
        );

        return;
      }

      try {
        await login(
          username,
          password
        );

        form.elements.password.value =
          "";

        await loadRoles();

      } catch (err) {
        statusMsg(
          err.message
        );
      }
    }
  );

  /*
   * Existing demo buttons are retained
   * only as username shortcuts.
   *
   * They NO LONGER perform demo-login
   * against the legacy FastAPI.
   */
  document
    .querySelectorAll(
      "[data-demo-login]"
    )
    .forEach(btn => {
      btn.addEventListener(
        "click",
        event => {
          event.preventDefault();

          form.elements.username.value =
            btn.dataset.demoLogin || "";

          form.elements.password.focus();

          statusMsg(
            "Masukkan password Frappe."
          );
        }
      );
    });
}

async function initializeAuthPage() {
  installFrappeLoginForm();

  try {
    const user =
      await loadSession();

    if (user) {
      renderUser({
        user
      });

      statusMsg(
        "Active Frappe session."
      );

      await loadRoles();

    } else {
      renderUser(null);

      statusMsg(
        "Login menggunakan akun Frappe."
      );
    }

  } catch (err) {
    renderUser(null);

    statusMsg(
      err.message
    );
  }
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    initializeAuthPage();

    const logoutBtn =
      document.getElementById(
        "logoutBtn"
      );

    if (logoutBtn) {
      logoutBtn.addEventListener(
        "click",
        () => {
          logout().catch(
            err => statusMsg(
              err.message
            )
          );
        }
      );
    }
  }
);
