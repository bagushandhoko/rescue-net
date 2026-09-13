const RN_SYSADMIN_BASE = location.origin + "/rescue-net-frappe/api/method";
let RN_SYSADMIN_SESSION = null;
let RN_SYSADMIN_POLL = null;

async function sysAdminCall(method, args = {}, write = false) {
  let url = `${RN_SYSADMIN_BASE}/${method}`;
  const headers = { "Accept": "application/json" };
  const options = { credentials: "same-origin", headers };

  if (write) {
    if (!RN_SYSADMIN_SESSION?.csrf_token) {
      throw new Error("Sesi belum siap, coba lagi.");
    }
    headers["Content-Type"] = "application/json";
    headers["X-Frappe-CSRF-Token"] = RN_SYSADMIN_SESSION.csrf_token;
    options.method = "POST";
    options.body = JSON.stringify(args);
  } else {
    const query = new URLSearchParams();
    Object.entries(args).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== "") query.set(k, v);
    });
    if (query.toString()) url += "?" + query.toString();
  }

  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const clean = String(data.message || data.exception || `Error ${res.status}`)
      .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    const e = new Error(clean);
    e.status = res.status;
    throw e;
  }

  return Object.prototype.hasOwnProperty.call(data, "message") ? data.message : data;
}

function fmtBytes(n) {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(1)} ${units[i]}`;
}

function fmtTimestamp(ts) {
  // "20260913-070743" -> "13 Sep 2026 07:07:43"
  const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/.exec(ts);
  if (!m) return ts;
  const [, y, mo, d, h, mi, s] = m;
  return `${d}/${mo}/${y} ${h}:${mi}:${s}`;
}

function renderRestoreStatus(status) {
  const el = document.getElementById("restoreStatus");
  if (!el) return;
  if (!status || status.state === "idle") {
    el.innerHTML = "<div><span>Status</span><b>Idle</b></div>";
    return;
  }
  if (status.state === "running") {
    el.innerHTML =
      `<div><span>Status</span><b>⏳ Sedang restore dari ${status.restoring_from}</b></div>` +
      `<div><span>Dimulai</span><b>${status.started_at || "-"}</b></div>` +
      `<div><span>Oleh</span><b>${status.started_by || "-"}</b></div>`;
    return;
  }
  const ok = status.state === "done" && status.exit_code === 0;
  el.innerHTML =
    `<div><span>Status</span><b>${ok ? "✓ Selesai" : "✗ Gagal"} (${status.restoring_from})</b></div>` +
    `<div><span>Selesai</span><b>${status.finished_at || "-"}</b></div>` +
    `<div><span>Exit code</span><b>${status.exit_code}</b></div>`;
}

function renderBackups(payload) {
  const list = document.getElementById("backupList");
  const select = document.getElementById("restoreTimestamp");
  if (!list || !select) return;

  const rows = payload.backups || [];
  list.innerHTML = rows.length
    ? rows.map(r => `
      <article class="event-card">
        <div class="event-main">
          <div>
            <h4>${fmtTimestamp(r.timestamp)}</h4>
            <p>${fmtBytes(r.size_bytes)} — ${Object.keys(r.files).join(", ") || "kosong"}</p>
          </div>
          <div class="chips"><span class="chip ${r.has_database ? "neutral" : "warning"}">${r.has_database ? "database ok" : "no db file"}</span></div>
        </div>
      </article>`).join("")
    : "<p class='subtitle'>Belum ada backup.</p>";

  const prevValue = select.value;
  select.innerHTML = rows.filter(r => r.has_database).map(r =>
    `<option value="${r.timestamp}">${fmtTimestamp(r.timestamp)} (${fmtBytes(r.size_bytes)})</option>`
  ).join("");
  if (rows.some(r => r.timestamp === prevValue)) select.value = prevValue;

  document.getElementById("confirmSiteName").placeholder = payload.site || "";
  renderRestoreStatus(payload.restore_status);
}

async function loadBackups() {
  const payload = await sysAdminCall("rescue_net.api_system_admin.list_backups");
  renderBackups(payload);
  return payload;
}

async function pollRestoreStatus() {
  try {
    const status = await sysAdminCall("rescue_net.api_system_admin.restore_status");
    renderRestoreStatus(status);
    if (status.state !== "running") {
      clearInterval(RN_SYSADMIN_POLL);
      RN_SYSADMIN_POLL = null;
      loadBackups().catch(() => {});
    }
  } catch (_) {
    clearInterval(RN_SYSADMIN_POLL);
    RN_SYSADMIN_POLL = null;
  }
}

async function triggerBackup() {
  const msg = document.getElementById("backupStatusMsg");
  msg.textContent = "Membuat backup...";
  try {
    const payload = await sysAdminCall("rescue_net.api_system_admin.trigger_backup", {}, true);
    renderBackups(payload);
    msg.textContent = "✓ Backup selesai dibuat.";
  } catch (err) {
    msg.textContent = "✗ " + err.message;
  }
}

async function submitRestore(e) {
  e.preventDefault();
  const form = e.target;
  const backup_timestamp = form.backup_timestamp.value;
  const confirm_site_name = form.confirm_site_name.value.trim();
  const msg = document.getElementById("restoreMsg");

  if (!backup_timestamp) {
    msg.textContent = "Pilih snapshot dulu.";
    return;
  }

  const sure = confirm(
    `Yakin restore ke snapshot ${fmtTimestamp(backup_timestamp)}?\n\n` +
    `Ini akan MENIMPA seluruh data live saat ini. Safety-snapshot otomatis ` +
    `dibuat dulu sebelum restore, tapi proses restore sendiri tidak bisa dibatalkan.`
  );
  if (!sure) return;

  msg.textContent = "Memulai restore (safety-snapshot dibuat dulu)...";
  try {
    await sysAdminCall("rescue_net.api_system_admin.restore_backup", {
      backup_timestamp,
      confirm_site_name,
    }, true);
    msg.textContent = "⏳ Restore berjalan di background. Status akan ter-update otomatis.";
    if (!RN_SYSADMIN_POLL) RN_SYSADMIN_POLL = setInterval(pollRestoreStatus, 4000);
  } catch (err) {
    msg.textContent = "✗ " + err.message;
  }
}

async function initSystemAdmin() {
  const section = document.getElementById("systemAdminSection");
  if (!section) return;

  const user = window.RN_SESSION?.getUser?.();
  if (!user || user.role !== "system_manager") {
    section.hidden = true;
    return;
  }

  section.hidden = false;

  try {
    RN_SYSADMIN_SESSION = await sysAdminCall("rescue_net.api_ai.session_info");
  } catch (_) {
    section.hidden = true;
    return;
  }

  document.getElementById("triggerBackupBtn").addEventListener("click", () => {
    triggerBackup().catch(() => {});
  });
  document.getElementById("restoreForm").addEventListener("submit", submitRestore);

  loadBackups().catch(err => {
    document.getElementById("backupStatusMsg").textContent = "✗ " + err.message;
  });

  const status = await sysAdminCall("rescue_net.api_system_admin.restore_status").catch(() => null);
  if (status && status.state === "running" && !RN_SYSADMIN_POLL) {
    RN_SYSADMIN_POLL = setInterval(pollRestoreStatus, 4000);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initSystemAdmin().catch(() => {});
});
window.addEventListener("rn:frappe-session", () => {
  initSystemAdmin().catch(() => {});
});
