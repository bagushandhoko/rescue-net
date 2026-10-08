"""Hubungi pelapor + level verifikasi pelapor (owner 2026-10-08).

Nomor HP / WhatsApp pelapor adalah data pribadi: tidak pernah ada di daftar laporan publik. Hanya
System Manager, pengelola posko tujuan laporan (can_manage_posko, termasuk koordinator organisasi dan
komando), atau verifikator aktif yang dapat membukanya lewat `api_reports.reporter_contact`, dan hanya bila
pelapor bersedia dihubungi (consent_to_contact). Setiap pembukaan dicatat di RN Verification Action.

Level verifikasi pelapor dihitung dari bukti yang ada (bukan angka buatan): ditampilkan beserta buktinya.
  0 Belum terverifikasi   — tidak ada akun Rescue-Net
  1 Akun terdaftar        — akun aktif (login Google / kata sandi)
  2 Kontak tersedia       — akun + no HP (belum dicek OTP)
  3 Terverifikasi         — Pelapor Terverifikasi (disetujui) atau anggota organisasi terverifikasi
  4 Verifikator           — profil verifikator aktif (trust >= 2)
"""

import frappe
from frappe.utils import cint

from rescue_net.services.reporter import is_google_login, normalize_phone

LEVELS = {0: "Belum terverifikasi", 1: "Akun terdaftar", 2: "Kontak tersedia", 3: "Terverifikasi", 4: "Verifikator"}
DONE_STATUSES = ("verified", "converted_to_action")
VERIFIED_ORG = ("verified", "approved", "trusted", "active_verified")


def may_contact(actor, posko):
    """May this actor open the reporter's contact for a report routed to `posko`?"""
    from rescue_net.access_policy import can_manage_posko, is_system_manager

    if is_system_manager():
        return True
    if not actor or not actor.get("name"):
        return False
    if posko and can_manage_posko(actor, posko):
        return True
    return bool(frappe.db.exists("RN Verifier Profile", {"user": actor.name, "verifier_status": "active"}))


def whatsapp_url(phone, text=None):
    number = normalize_phone(phone)
    if not number:
        return None
    from urllib.parse import quote

    url = "https://wa.me/62" + number[1:]
    return url + ("?text=" + quote(text) if text else "")


def verification_profile(account_name):
    """Evidence-based level of a reporter's account. `account_name` may be None (no account)."""
    if not account_name:
        return {"level": 0, "label": LEVELS[0], "evidence": [
            {"key": "account", "ok": False, "label": "Akun Rescue-Net", "detail": "Pelapor tidak punya akun."}]}

    acc = frappe.db.get_value(
        "RN User Account", account_name,
        ["name", "frappe_user", "role", "status", "phone", "creation", "reporter_verified_by",
         "reporter_verified_at", "reporter_agency", "reporter_position", "organization"],
        as_dict=True,
    )
    if not acc:
        return verification_profile(None)

    evidence = []
    active = acc.status == "active"
    evidence.append({"key": "account", "ok": active, "label": "Akun Rescue-Net",
                     "detail": f"{'Aktif' if active else acc.status}, dibuat {str(acc.creation)[:10]}"})
    google = is_google_login(acc.frappe_user)
    evidence.append({"key": "login", "ok": True, "label": "Cara masuk", "detail": "Google" if google else "Kata sandi"})
    has_phone = bool(normalize_phone(acc.phone))
    evidence.append({"key": "phone", "ok": has_phone, "label": "No HP",
                     "detail": "Terisi (belum dicek OTP)" if has_phone else "Belum diisi"})

    verified_reporter = acc.role == "verified_reporter"
    if verified_reporter or acc.reporter_verified_by:
        who = acc.reporter_verified_by or "-"
        evidence.append({"key": "reporter", "ok": True, "label": "Pelapor Terverifikasi",
                         "detail": f"Disetujui oleh {who}" + (f" · {acc.reporter_agency}" if acc.reporter_agency else "")
                                   + (f", {acc.reporter_position}" if acc.reporter_position else "")})

    org_ok = False
    org_name = acc.organization or frappe.db.get_value(
        "RN Organization Membership", {"user_account": acc.name, "status": "approved"}, "organization")
    if org_name:
        org = frappe.db.get_value("RN Organization", org_name,
                                  ["title", "verification_status", "identity_verification_status"], as_dict=True)
        if org:
            org_ok = str(org.verification_status or "").lower() in VERIFIED_ORG or \
                str(org.identity_verification_status or "").lower() in VERIFIED_ORG
            evidence.append({"key": "org", "ok": org_ok, "label": "Organisasi",
                             "detail": f"{org.title} — {'terverifikasi' if org_ok else 'belum terverifikasi'}"})

    verifier = frappe.db.get_value("RN Verifier Profile", {"user": acc.name, "verifier_status": "active"},
                                   ["verifier_type", "trust_level"], as_dict=True)
    if verifier:
        evidence.append({"key": "verifier", "ok": cint(verifier.trust_level) >= 2, "label": "Verifikator",
                         "detail": f"{verifier.verifier_type}, trust {cint(verifier.trust_level)}"})

    rows = frappe.get_all("RN Community Report", filters={"reporter_user": acc.name}, fields=["status"],
                          limit_page_length=500)
    done = sum(1 for r in rows if r.status in DONE_STATUSES)
    rejected = sum(1 for r in rows if r.status == "rejected")
    evidence.append({"key": "history", "ok": done > 0 and rejected == 0, "label": "Riwayat laporan",
                     "detail": f"{len(rows)} laporan · {done} terverifikasi · {rejected} ditolak"})

    level = 1 if active else 0
    if level and has_phone:
        level = 2
    if level >= 1 and (verified_reporter or acc.reporter_verified_by or org_ok):
        level = 3
    if verifier and cint(verifier.trust_level) >= 2:
        level = 4
    return {"level": level, "label": LEVELS[level], "evidence": evidence}
