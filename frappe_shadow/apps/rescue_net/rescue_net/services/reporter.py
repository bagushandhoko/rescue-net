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
