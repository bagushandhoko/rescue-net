const RN_API_BASE = "http://192.168.100.32:8092";

function statusMsg(msg) {
  const el = document.getElementById("authStatus");
  if (el) el.textContent = msg;
}

function safe(v) {
  return v === null || v === undefined || v === "" ? "n/a" : v;
}

async function api(path, options = {}) {
  const res = await fetch(RN_API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function renderUser(data) {
  const el = document.getElementById("currentUser");
  if (!el) return;

  if (!data || !data.user) {
    el.innerHTML = `<div><span>Status</span><b>Not logged in</b></div>`;
    return;
  }

  const u = data.user;

  el.innerHTML = `
    <div><span>User</span><b>${safe(u.display_name)}</b></div>
    <div><span>Username</span><b>${safe(u.username)}</b></div>
    <div><span>Role</span><b>${safe(u.role)}</b></div>
    <div><span>Organization</span><b>${safe(u.organization_id)}</b></div>
    <div><span>Posko</span><b>${safe(u.posko_id)}</b></div>
    <div><span>Phone</span><b>${safe(u.phone)}</b></div>
    <div><span>Email</span><b>${safe(u.email)}</b></div>
  `;
}

function renderRoles(data) {
  const el = document.getElementById("roleList");
  if (!el) return;

  const roles = data.roles || [];
  el.innerHTML = roles.map(r => `
    <article class="event-card">
      <div class="event-main">
        <div>
          <h4>${safe(r.label)}</h4>
          <p>Role: ${safe(r.role)}<br>Scope: ${safe(r.scope)}<br>Can verify: ${safe(r.can_verify)}<br>Can view sensitive: ${safe(r.can_view_sensitive)}</p>
        </div>
        <div class="chips"><span class="chip warning">${safe(r.role)}</span></div>
      </div>
    </article>
  `).join("");
}

async function loadRoles() {
  const roles = await api("/auth/roles");
  renderRoles(roles);
}

async function login(username) {
  statusMsg("Logging in...");
  const data = await api("/auth/demo-login", {
    method: "POST",
    body: JSON.stringify({ username })
  });

  localStorage.setItem("RN_SESSION_TOKEN", data.session_token);
  localStorage.setItem("RN_USER", JSON.stringify(data.user));

  renderUser(data);
  statusMsg("Logged in as " + data.user.display_name);
}

async function loadMe() {
  const token = localStorage.getItem("RN_SESSION_TOKEN");
  if (!token) {
    renderUser(null);
    statusMsg("No local session.");
    return;
  }

  const data = await api(`/auth/me/${encodeURIComponent(token)}`);
  renderUser(data);
  statusMsg("Session loaded.");
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-demo-login]").forEach(btn => {
    btn.addEventListener("click", () => {
      login(btn.dataset.demoLogin).catch(err => statusMsg(err.message));
    });
  });

  const logout = document.getElementById("logoutBtn");
  if (logout) {
    logout.addEventListener("click", () => {
      localStorage.removeItem("RN_SESSION_TOKEN");
      localStorage.removeItem("RN_USER");
      renderUser(null);
      statusMsg("Logged out locally.");
    });
  }

  loadRoles().catch(err => statusMsg(err.message));
  loadMe().catch(err => statusMsg(err.message));
});
