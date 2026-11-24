"""Verifikasi dua langkah (2FA) tanpa email (2026-10-26, rencana pembenahan tahap 1).

Frappe's own "OTP App" method emails the QR code on first login, and this
server has no outgoing email account, so admins would be locked out. Here the
logged-in user sets the authenticator app up in Setting (QR shown on screen,
one code confirmed), using Frappe's own secret storage, so Frappe's login then
only asks for the 6-digit code. Enforcement for System Managers is a separate
switch that only a System Manager who has finished the setup can turn on.

2026-11-24 (owner: "2FA wajib hanya pemilik" organisasi tertutup): pemilik organisasi tertutup (bukan akun demo)
WAJIB 2FA. Tanpa risiko terkunci: selama belum memasang aplikasi, login tetap bisa tetapi API Rescue-Net lain
ditahan (before_request) sampai pemasangan selesai di Pengaturan Akun. Sesudah pasang, peran OWNER_ROLE
(two_factor_auth) membuat login sandi Frappe meminta kode. Login Google tidak melewati 2FA Frappe, jadi tiap
sesi tanpa kode dari login sandi diminta kode sekali di aplikasi (verify_session)."""

import frappe
import pyotp
from frappe.rate_limiter import rate_limit
from frappe.twofactor import get_default, get_otpsecret_for_, get_qr_svg_code, set_default

from rescue_net.access_policy import is_system_manager

OWNER_ROLE = "RN 2FA Pemilik"
REQUIRED_MSG = "RN_2FA_WAJIB: Pemilik organisasi tertutup wajib verifikasi dua langkah. Buka Pengaturan Akun."
SESSION_TTL = 24 * 3600
# API yang tetap boleh dipanggil sebelum 2FA beres (status, pasang, verifikasi, sesi, logout, privasi)
ALLOWED_PREFIXES = ("rescue_net.api_twofa.", "rescue_net.api_auth.")


def _user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Masuk dulu untuk mengatur verifikasi dua langkah.", frappe.PermissionError)
    return user


def _issuer():
    return frappe.db.get_single_value("System Settings", "otp_issuer_name") or "Rescue-Net"


def _setup_done(user):
    return bool(get_default(user + "_otplogin"))


def _sid():
    return getattr(frappe.session, "sid", None) or ""


def _session_key(sid=None):
    return "rn_2fa_ok:" + (sid or _sid())


def mark_session_verified(sid=None):
    sid = sid or _sid()
    if sid and sid != "Guest":
        frappe.cache.set_value(_session_key(sid), 1, expires_in_sec=SESSION_TTL)


def session_verified():
    sid = _sid()
    return bool(sid) and bool(frappe.cache.get_value(_session_key(sid), expires=True))


def closed_org_owner(user, use_cache=True):
    """Pemilik (keanggotaan owner disetujui) organisasi berstatus tertutup; akun demo dikecualikan."""
    from rescue_net.services.drill import is_demo_user
    if not user or user in ("Guest", "Administrator") or is_demo_user(user):
        return False
    key = "rn_2fa_owner:" + user
    if use_cache:
        hit = frappe.cache.get_value(key, expires=True)
        if hit is not None:
            return bool(int(hit))
    accounts = frappe.get_all("RN User Account", filters={"frappe_user": user}, pluck="name")
    owner = False
    if accounts:
        orgs = frappe.get_all("RN Organization Membership", filters={
            "user_account": ["in", accounts], "membership_role": "owner", "status": "approved"}, pluck="organization")
        owner = bool(orgs) and bool(frappe.db.exists("RN Organization", {"name": ["in", orgs], "privacy_mode": "closed"}))
    frappe.cache.set_value(key, 1 if owner else 0, expires_in_sec=300)
    return owner


def _ensure_owner_role():
    if not frappe.db.exists("Role", OWNER_ROLE):
        frappe.get_doc({"doctype": "Role", "role_name": OWNER_ROLE, "desk_access": 0,
                        "two_factor_auth": 1}).insert(ignore_permissions=True)
    elif not frappe.db.get_value("Role", OWNER_ROLE, "two_factor_auth"):
        frappe.db.set_value("Role", OWNER_ROLE, "two_factor_auth", 1)


def _owner_role_users():
    return frappe.get_all("Has Role", filters={"role": OWNER_ROLE, "parenttype": "User"}, pluck="parent")


def _sync_global_flag():
    """2FA Frappe menyala bila admin diwajibkan ATAU ada pemilik berperan OWNER_ROLE."""
    on = bool(frappe.db.get_value("Role", "System Manager", "two_factor_auth")) or bool(
        frappe.db.exists("Role", OWNER_ROLE) and _owner_role_users())
    if on:
        frappe.db.set_single_value("System Settings", "two_factor_method", "OTP App")
    if bool(int(frappe.db.get_single_value("System Settings", "enable_two_factor_auth") or 0)) != on:
        frappe.db.set_single_value("System Settings", "enable_two_factor_auth", 1 if on else 0)


def sync_owner_role(user):
    """Peran OWNER_ROLE hanya untuk pemilik org tertutup yang SUDAH memasang aplikasi (tidak pernah mengunci)."""
    want = closed_org_owner(user, use_cache=False) and _setup_done(user)
    has = OWNER_ROLE in frappe.get_roles(user)
    if want == has:
        return want
    _ensure_owner_role()
    doc = frappe.get_doc("User", user)
    if want:
        doc.append("roles", {"role": OWNER_ROLE})
    else:
        doc.set("roles", [r for r in doc.roles if r.role != OWNER_ROLE])
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    _sync_global_flag()
    return want


def required_state(user=None):
    """None = tidak wajib / sudah beres; "setup" = belum pasang aplikasi; "verify" = sesi ini belum dikodekan."""
    user = user or frappe.session.user
    if not closed_org_owner(user):
        return None
    if not _setup_done(user):
        return "setup"
    if not session_verified():
        return "verify"
    return None


def before_request():
    """Tahan API Rescue-Net untuk pemilik org tertutup yang 2FA-nya belum beres (selain API izin di atas)."""
    try:
        req = getattr(frappe.local, "request", None)
        path = (req.path or "") if req else ""
        if not path.startswith("/api/method/rescue_net."):
            return
        if path[len("/api/method/"):].startswith(ALLOWED_PREFIXES):
            return
        user = frappe.session.user
        if not user or user == "Guest":
            return
        state = required_state(user)
    except Exception:
        return
    if state:
        frappe.throw(REQUIRED_MSG, frappe.PermissionError)


def on_session_creation(login_manager=None):
    """Login sandi yang melewati kode 2FA Frappe = sesi sudah terverifikasi."""
    try:
        if frappe.form_dict.get("otp") and frappe.form_dict.get("tmp_id"):
            mark_session_verified()
    except Exception:
        pass


def _enforced():
    return bool(int(frappe.db.get_single_value("System Settings", "enable_two_factor_auth") or 0)) and \
        bool(frappe.db.get_value("Role", "System Manager", "two_factor_auth"))


@frappe.whitelist()
def status():
    user = _user()
    return {"setup_done": _setup_done(user), "enforced_for_admin": _enforced(),
            "is_system_manager": is_system_manager(), "method": "Aplikasi authenticator (Google Authenticator, dsb.)",
            "required_for_owner": closed_org_owner(user), "required_state": required_state(user),
            "session_verified": session_verified()}


@frappe.whitelist()
def setup_start():
    """Secret (Frappe storage) + QR to scan. Not active until setup_verify."""
    user = _user()
    secret = get_otpsecret_for_(user)
    uri = pyotp.TOTP(secret).provisioning_uri(user, issuer_name=_issuer())
    svg = get_qr_svg_code(uri)
    return {"qr_svg_base64": svg.decode() if isinstance(svg, bytes) else svg,
            "secret": secret, "account": user, "issuer": _issuer()}


@frappe.whitelist()
def setup_verify(code):
    user = _user()
    secret = get_otpsecret_for_(user)
    if not pyotp.TOTP(secret).verify(str(code or "").strip().replace(" ", ""), valid_window=1):
        frappe.throw("Kode tidak cocok. Pastikan jam HP benar, lalu masukkan kode terbaru dari aplikasi.")
    set_default(user + "_otplogin", 1)
    mark_session_verified()
    sync_owner_role(user)
    frappe.db.commit()
    return status()


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=600)
def verify_session(code):
    """Kode dari aplikasi untuk sesi ini (login Google / sesi lama) setelah aplikasi terpasang."""
    user = _user()
    if not _setup_done(user):
        frappe.throw("Pasang aplikasi authenticator dulu.")
    secret = get_otpsecret_for_(user)
    if not pyotp.TOTP(secret).verify(str(code or "").strip().replace(" ", ""), valid_window=1):
        frappe.throw("Kode tidak cocok. Pastikan jam HP benar, lalu masukkan kode terbaru dari aplikasi.")
    mark_session_verified()
    sync_owner_role(user)
    return status()


@frappe.whitelist(methods=["POST"])
def reset_user(user):
    """System Manager: hapus 2FA akun yang kehilangan HP (akun lalu wajib memasang ulang)."""
    if not is_system_manager():
        frappe.throw("Hanya System Manager.", frappe.PermissionError)
    if not frappe.db.exists("User", user):
        frappe.throw("Akun tidak ditemukan.")
    from frappe.twofactor import clear_default, delete_qrimage
    for key in (user + "_otplogin", user + "_otpsecret"):
        clear_default(key)
    try:
        delete_qrimage(user)
    except Exception:
        pass
    sync_owner_role(user)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def set_admin_enforcement(enable):
    """System Manager only, and only after finishing their own setup (no lock-out)."""
    if not is_system_manager():
        frappe.throw("Hanya System Manager.", frappe.PermissionError)
    on = str(enable).lower() in ("1", "true", "yes", "on")
    if on and not _setup_done(_user()):
        frappe.throw("Siapkan dulu aplikasi authenticator Anda sendiri sebelum mewajibkan 2FA.")
    frappe.db.set_value("Role", "System Manager", "two_factor_auth", 1 if on else 0)
    _sync_global_flag()  # global tetap menyala bila pemilik org tertutup memakai 2FA
    frappe.clear_cache()
    return status()
