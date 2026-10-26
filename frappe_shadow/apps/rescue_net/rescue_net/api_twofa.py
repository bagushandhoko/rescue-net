"""Verifikasi dua langkah (2FA) tanpa email (2026-10-26, rencana pembenahan tahap 1).

Frappe's own "OTP App" method emails the QR code on first login, and this
server has no outgoing email account, so admins would be locked out. Here the
logged-in user sets the authenticator app up in Setting (QR shown on screen,
one code confirmed), using Frappe's own secret storage, so Frappe's login then
only asks for the 6-digit code. Enforcement for System Managers is a separate
switch that only a System Manager who has finished the setup can turn on."""

import frappe
import pyotp
from frappe.twofactor import get_default, get_otpsecret_for_, get_qr_svg_code, set_default

from rescue_net.access_policy import is_system_manager


def _user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Masuk dulu untuk mengatur verifikasi dua langkah.", frappe.PermissionError)
    return user


def _issuer():
    return frappe.db.get_single_value("System Settings", "otp_issuer_name") or "Rescue-Net"


def _setup_done(user):
    return bool(get_default(user + "_otplogin"))


def _enforced():
    return bool(int(frappe.db.get_single_value("System Settings", "enable_two_factor_auth") or 0)) and \
        bool(frappe.db.get_value("Role", "System Manager", "two_factor_auth"))


@frappe.whitelist()
def status():
    user = _user()
    return {"setup_done": _setup_done(user), "enforced_for_admin": _enforced(),
            "is_system_manager": is_system_manager(), "method": "Aplikasi authenticator (Google Authenticator, dsb.)"}


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
    frappe.db.commit()
    return status()


@frappe.whitelist()
def set_admin_enforcement(enable):
    """System Manager only, and only after finishing their own setup (no lock-out)."""
    if not is_system_manager():
        frappe.throw("Hanya System Manager.", frappe.PermissionError)
    on = str(enable).lower() in ("1", "true", "yes", "on")
    if on and not _setup_done(_user()):
        frappe.throw("Siapkan dulu aplikasi authenticator Anda sendiri sebelum mewajibkan 2FA.")
    frappe.db.set_single_value("System Settings", "two_factor_method", "OTP App")
    frappe.db.set_single_value("System Settings", "enable_two_factor_auth", 1 if on else 0)
    frappe.db.set_value("Role", "System Manager", "two_factor_auth", 1 if on else 0)
    frappe.clear_cache()
    return status()
