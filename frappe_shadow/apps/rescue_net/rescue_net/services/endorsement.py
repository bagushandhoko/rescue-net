"""Masa berlaku endorsement verifikator (owner 2026-11-20).

Satu aturan untuk semua tempat yang menghitung / memakai RN Verification Endorsement (posko maupun pelapor):
- endorsement baru otomatis diberi `expires_at` = waktu verifikasi + ENDORSEMENT_VALID_DAYS (bila tidak diisi);
- endorsement yang `expires_at`-nya sudah lewat tidak dihitung lagi, walau statusnya masih "active";
- tugas harian menandai yang sudah lewat menjadi "expired" dan menghitung ulang status posko.
Endorsement lama tanpa `expires_at` tetap berlaku sampai dicabut (tidak diberi tanggal mundur).
"""

import frappe
from frappe.utils import add_days, get_datetime, now_datetime

ENDORSEMENT_VALID_DAYS = 365


def default_expiry(verified_at=None):
    """Tanggal berakhir bawaan: 1 tahun setelah verifikasi."""
    return add_days(get_datetime(verified_at) if verified_at else now_datetime(), ENDORSEMENT_VALID_DAYS)


def is_expired(row, now=None):
    exp = row.get("expires_at") if hasattr(row, "get") else getattr(row, "expires_at", None)
    return bool(exp) and get_datetime(exp) < (now or now_datetime())


def drop_expired(rows, now=None):
    """Baris endorsement yang masih berlaku (yang tanpa tanggal berakhir ikut berlaku)."""
    now = now or now_datetime()
    return [r for r in rows if not is_expired(r, now)]


def has_valid(target_type, target_id, verifier):
    """Verifikator ini masih punya endorsement aktif + belum lewat masa berlaku untuk sasaran ini?
    (Yang sudah lewat boleh diperbarui dengan endorsement baru.)"""
    rows = frappe.get_all("RN Verification Endorsement",
                          filters={"target_type": target_type, "target_id": target_id,
                                   "verifier": verifier, "status": "active"},
                          fields=["name", "expires_at"], limit_page_length=0)
    return bool(drop_expired(rows))


def expire_overdue():
    """Tugas harian: endorsement aktif yang lewat masa berlaku → status "expired"; status posko dihitung ulang."""
    rows = frappe.get_all("RN Verification Endorsement",
                          filters={"status": "active", "expires_at": ["<", now_datetime()]},
                          fields=["name", "target_type", "target_id"], limit_page_length=0)
    poskos = set()
    for r in rows:
        frappe.db.set_value("RN Verification Endorsement", r.name, "status", "expired", update_modified=False)
        if r.target_type == "posko" and r.target_id:
            poskos.add(r.target_id)
    if poskos:
        from rescue_net.api_verifier import _recompute_posko_credibility
        for p in poskos:
            if frappe.db.exists("RN Posko", p):
                _recompute_posko_credibility(p)
    return {"expired": len(rows), "poskos": sorted(poskos)}
