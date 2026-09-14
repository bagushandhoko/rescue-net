(function () {
  function msg(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  /* ---- Ubah password sendiri (semua user) ---- */
  async function submitChangePassword(e) {
    e.preventDefault();
    const form = e.target;
    const old_password = form.old_password.value;
    const new_password = form.new_password.value;
    const confirm_password = form.confirm_password.value;

    if (new_password !== confirm_password) {
      msg("changePasswordMsg", "✗ Password baru dan konfirmasi tidak sama.");
      return;
    }

    msg("changePasswordMsg", "Menyimpan…");
    try {
      const r = await window.RN_FRAPPE.call(
        "rescue_net.api_auth.change_password",
        { old_password, new_password },
        { method: "POST" }
      );
      form.reset();
      msg("changePasswordMsg", "✓ " + (r.message || "Password berhasil diubah."));
    } catch (err) {
      msg("changePasswordMsg", "✗ " + err.message);
    }
  }

  /* ---- Reset password user lain (System Manager) ---- */
  let adminUsers = [];

  function renderUserOptions(filter) {
    const select = document.getElementById("adminResetUserSelect");
    if (!select) return;
    const f = (filter || "").trim().toLowerCase();
    const rows = f
      ? adminUsers.filter(u =>
          u.name.toLowerCase().includes(f) ||
          (u.full_name || "").toLowerCase().includes(f))
      : adminUsers;

    select.innerHTML = rows.length
      ? rows.map(u => `<option value="${u.name}">${u.full_name || u.name} (${u.name})</option>`).join("")
      : `<option value="">Tidak ada user cocok</option>`;
  }

  async function loadAdminUsers() {
    const data = await window.RN_FRAPPE.call("rescue_net.api_auth.admin_list_users");
    adminUsers = data.users || [];
    renderUserOptions("");
  }

  // Guarantee at least 1 uppercase + 1 digit so it always passes the
  // server-side strength check, then shuffle so they aren't always first.
  function generatePassword() {
    const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
    const lower = "abcdefghijkmnpqrstuvwxyz";
    const digits = "23456789";
    const all = upper + lower + digits;

    function randFrom(str, n) {
      const bytes = new Uint32Array(n);
      crypto.getRandomValues(bytes);
      let out = "";
      for (let i = 0; i < n; i++) out += str[bytes[i] % str.length];
      return out;
    }

    const raw = randFrom(upper, 2) + randFrom(digits, 2) + randFrom(all, 8);
    return raw.split("").sort(() => Math.random() - 0.5).join("");
  }

  async function submitAdminReset(e) {
    e.preventDefault();
    const form = e.target;
    const user = form.user.value;
    const new_password = form.new_password.value;

    if (!user) {
      msg("adminResetPasswordMsg", "✗ Pilih user dulu.");
      return;
    }
    if (!confirm(`Reset password untuk ${user}? User itu akan logout otomatis di semua device.`)) return;

    msg("adminResetPasswordMsg", "Memproses…");
    try {
      const r = await window.RN_FRAPPE.call(
        "rescue_net.api_auth.admin_reset_password",
        { user, new_password },
        { method: "POST" }
      );
      form.new_password.value = "";
      msg("adminResetPasswordMsg", "✓ " + (r.message || "Password direset.") + ` Password baru untuk ${user}: ${new_password}`);
    } catch (err) {
      msg("adminResetPasswordMsg", "✗ " + err.message);
    }
  }

  async function initAdminResetSection() {
    const section = document.getElementById("adminResetPasswordSection");
    if (!section) return;

    const user = window.RN_SESSION && window.RN_SESSION.getUser && window.RN_SESSION.getUser();
    if (!user || user.role !== "system_manager") {
      section.hidden = true;
      return;
    }
    section.hidden = false;

    try {
      await loadAdminUsers();
    } catch (err) {
      msg("adminResetPasswordMsg", "✗ " + err.message);
    }

    const search = document.getElementById("adminResetUserSearch");
    if (search && !search.dataset.wired) {
      search.dataset.wired = "1";
      search.addEventListener("input", () => renderUserOptions(search.value));
    }

    const genBtn = document.getElementById("adminGeneratePasswordBtn");
    const form = document.getElementById("adminResetPasswordForm");
    if (genBtn && !genBtn.dataset.wired) {
      genBtn.dataset.wired = "1";
      genBtn.addEventListener("click", () => {
        form.new_password.value = generatePassword();
        form.new_password.type = "text";
      });
    }
    if (form && !form.dataset.wired) {
      form.dataset.wired = "1";
      form.addEventListener("submit", e => {
        submitAdminReset(e).catch(err => msg("adminResetPasswordMsg", "✗ " + err.message));
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const cp = document.getElementById("changePasswordForm");
    if (cp) {
      cp.addEventListener("submit", e => {
        submitChangePassword(e).catch(err => msg("changePasswordMsg", "✗ " + err.message));
      });
    }

    initAdminResetSection().catch(() => {});
  });

  window.addEventListener("rn:frappe-session", () => {
    initAdminResetSection().catch(() => {});
  });
})();
