"""Pelapor Terverifikasi (owner 2026-10-01).

A verified person outside the posko — BNPB/BPBD officer, police chief, TNI,
village official or a citizen dedicated to watching their surroundings — who
may ONLY report needs ("Kebutuhan") at ANY posko. The need is added to that
same posko's list straight away, labelled with the reporter and marked
"belum dikonfirmasi" until a posko operator confirms or rejects it.

Nothing here widens _can_operate / can_manage_posko / _POSKO_OWNER_REASONS:
a reporter never edits stock, other needs, the posko itself or its contacts.

Account flow: signup role key "pelapor" (+ instansi, jabatan, wilayah) →
pending → approved by a System Manager (approval queue) or by a senior
verifier of the verifier network (trust_level >= 2, api_verifier) → role
"verified_reporter", status active.
"""

import frappe
from frappe.utils import add_to_date, now_datetime

SIGNUP_KEY = "pelapor"
ROLE = "verified_reporter"
CHANNEL = "verified_reporter"
HOURLY_LIMIT = 30


def is_verified_reporter(actor):
    return bool(actor) and getattr(actor, "role", None) == ROLE


def reporter_label(account_name):
    a = frappe.db.get_value(
        "RN User Account", account_name,
        ["title", "reporter_position", "reporter_agency"], as_dict=True,
    ) or {}
    who = a.get("title") or account_name
    role = ", ".join(x for x in (a.get("reporter_position"), a.get("reporter_agency")) if x)
    return f"{who} · {role}" if role else who


def activate(doc, decided_by):
    """Grant the reporter role on an RN User Account doc (caller saves)."""
    doc.role = ROLE
    doc.flags.rn_reporter_activation = True  # narrow exception to the SM-only role rule
    doc.role_request_status = "approved"
    doc.status = "active"
    doc.reporter_verified_by = decided_by
    doc.reporter_verified_at = now_datetime()


def check_rate(account_name):
    since = add_to_date(now_datetime(), hours=-1)
    n = frappe.db.count("RN Logistic Need", {
        "created_by_user": account_name, "report_channel": CHANNEL, "creation": [">", since],
    })
    if n >= HOURLY_LIMIT:
        frappe.throw(f"Batas {HOURLY_LIMIT} laporan per jam tercapai. Coba lagi nanti.")


def mark_need(doc, actor):
    """Label a need created through the reporter path."""
    doc.report_channel = CHANNEL
    doc.reporter_confirmation = "pending"
    doc.reporter_label = reporter_label(actor.name)
    doc.verification_status = "reporter_reported"


# ---- Nomor HP pelapor (owner 2026-10-08: wajib bila masuk dengan Google) ----

import re as _re


def normalize_phone(raw):
    """Indonesian mobile number -> '08…' digits only, or None when it cannot be one.
    Accepts 08…, +62 8…, 62 8…, spaces/dashes/dots/brackets; 9-13 digits after the leading 0."""
    digits = _re.sub(r"[\s\-\.\(\)]", "", str(raw or ""))
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit():
        return None
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    if not digits.startswith("08") or not 10 <= len(digits) <= 14:
        return None
    return digits


def is_google_login(user=None):
    """True when the Frappe user is linked to a Google social login."""
    user = user or frappe.session.user
    if user in (None, "", "Guest", "Administrator"):
        return False
    return bool(frappe.db.exists("User Social Login", {"parent": user, "provider": "google"}))


def account_phone(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("RN User Account", {"frappe_user": user, "status": "active"}, "phone") or None


def resolve_reporter_phone(phone, user=None):
    """The number to store on a report. A Google login MUST have one (typed now or saved on the
    account); other logins may leave it empty. A valid typed number is remembered on the account
    when the account has none, so the next report is prefilled."""
    user = user or frappe.session.user
    typed = (phone or "").strip()
    number = normalize_phone(typed) if typed else None
    if typed and not number:
        frappe.throw("Nomor HP tidak valid. Contoh: 081234567890 atau +6281234567890.")
    saved = normalize_phone(account_phone(user))
    number = number or saved
    if not number and is_google_login(user):
        frappe.throw("Nomor HP wajib diisi agar verifikator dapat menghubungi Anda (Anda masuk dengan Google).")
    if number and not saved:
        name = frappe.db.get_value("RN User Account", {"frappe_user": user, "status": "active"}, "name")
        if name:
            frappe.db.set_value("RN User Account", name, "phone", number, update_modified=False)
    return number
