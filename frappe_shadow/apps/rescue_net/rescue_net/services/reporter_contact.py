"""Hubungi pelapor + level verifikasi pelapor (owner 2026-10-08).

Nomor HP / WhatsApp pelapor adalah data pribadi: tidak pernah ada di daftar laporan publik. Hanya
System Manager, pengelola posko tujuan laporan (can_manage_posko, termasuk koordinator organisasi dan
komando), atau verifikator aktif yang dapat membukanya lewat `api_reports.reporter_contact`, dan hanya bila
pelapor bersedia dihubungi (consent_to_contact). Setiap pembukaan dicatat di RN Verification Action.

Status verifikasi pelapor memakai kosakata yang SAMA dengan posko (RN Posko.verification_status) dan lencana
bersama RNVerifBadge — satu sistem dengan Jaringan Verifikator (RN Verifier Profile + RN Verification Endorsement):
  self_reported         — belum ada yang memverifikasi (lencana disembunyikan)
  organization_verified — anggota organisasi yang terverifikasi
  community_verified    — Pelapor Terverifikasi (disetujui) atau didukung 1 verifikator aktif
  official_verified     — didukung >= 2 verifikator aktif, atau 1 verifikator pemerintah (trust >= 2),
                          atau pelapor sendiri verifikator senior (trust >= 2)
Verifikator yang ditangguhkan / dicabut tidak dihitung. Nama + jabatan verifikator terlihat publik (seperti panel
posko); pernyataan mereka tentang pelapor hanya untuk yang berwenang (bisa memuat ciri pelapor).
"""

import frappe
from frappe.utils import cint

from rescue_net.services.reporter import is_google_login, normalize_phone

DONE_STATUSES = ("verified", "converted_to_action")
VERIFIED_ORG = ("verified", "approved", "trusted", "active_verified")
TYPE_LABEL = {
    "government": "Pemerintah / aparat",
    "community_leader": "Tokoh masyarakat / ketua organisasi",
    "religious_leader": "Tokoh agama",
    "professional": "Profesional",
    "public_figure": "Tokoh publik",
    "other": "Verifikator",
}
METHOD_LABEL = {"site_visit": "Kenal langsung / kunjungan", "network_vouch": "Rekomendasi jaringan",
                "document_review": "Cek dokumen"}


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


def _verifier_item(r, v, detail):
    item = {
        "verifier": v.title, "position": v.position_title, "role": v.verifier_type,
        "role_label": TYPE_LABEL.get(v.verifier_type, "Verifikator"),
        "method": r.method, "method_label": METHOD_LABEL.get(r.method, r.method),
        "verified_at": str(r.verified_at)[:10] if r.verified_at else None,
        "verifier_id": r.verifier,
    }
    if detail:
        item["endorsement"] = r.name
        item["vouched_via"] = r.vouched_via
        item["statement"] = r.statement
    return item


def endorsements(account_name, detail=False):
    """Active endorsements of a reporter by verifiers who are still active (the Jaringan Verifikator).
    `detail` (authorised viewers) adds the verifier's statement and who referred them."""
    if not account_name:
        return []
    rows = frappe.get_all(
        "RN Verification Endorsement",
        filters={"target_type": "reporter", "target_id": account_name, "status": "active"},
        fields=["name", "verifier", "method", "vouched_via", "statement", "verified_at", "expires_at"],
        order_by="verified_at desc", limit_page_length=50)
    now = frappe.utils.now_datetime()
    out = []
    for r in rows:
        if r.expires_at and frappe.utils.get_datetime(r.expires_at) < now:
            continue
        v = frappe.db.get_value("RN Verifier Profile", r.verifier,
                                ["title", "verifier_type", "position_title", "verifier_status", "trust_level"],
                                as_dict=True)
        if not v or v.verifier_status != "active":
            continue
        item = _verifier_item(r, v, detail)
        item["trust_level"] = cint(v.trust_level)
        out.append(item)
    return out


def _status(active, approved_reporter, org_ok, ends, own_trust):
    """Same rule as api_verifier._recompute_posko_credibility, plus the reporter's own standing."""
    if not active:
        return "self_reported"
    n = len(ends)
    gov = any(e["role"] == "government" and e.get("trust_level", 0) >= 2 for e in ends)
    if n >= 2 or gov or (own_trust is not None and cint(own_trust) >= 2):
        return "official_verified"
    if n == 1 or approved_reporter or (own_trust is not None):
        return "community_verified"
    if org_ok:
        return "organization_verified"
    return "self_reported"


def _approver_item(acc):
    """The Pelapor Terverifikasi approval (system manager / senior verifier) as a 'verified by' line."""
    who = acc.reporter_verified_by
    prof = frappe.db.get_value("RN Verifier Profile", {"user": who}, ["title", "verifier_type", "position_title"],
                               as_dict=True) if who else None
    return {"verifier": (prof.title if prof else who) or "Admin Rescue-Net",
            "position": (prof.position_title if prof else None) or acc.reporter_position,
            "role": prof.verifier_type if prof else "other",
            "role_label": "Pelapor Terverifikasi (disetujui)", "method": "document_review",
            "method_label": "Persetujuan pendaftaran pelapor",
            "verified_at": str(acc.reporter_verified_at)[:10] if acc.reporter_verified_at else None,
            "verifier_id": None}


def verification_profile(account_name, detail=False):
    """Evidence + status of a reporter's account. `account_name` may be None (no account).
    `detail` adds contact-adjacent evidence (login method, phone) and the verifiers' statements — authorised only."""
    empty = {"status": "self_reported", "count": 0, "verifiers": [], "evidence": []}
    if not account_name:
        return empty
    acc = frappe.db.get_value(
        "RN User Account", account_name,
        ["name", "frappe_user", "role", "status", "phone", "creation", "reporter_verified_by",
         "reporter_verified_at", "reporter_agency", "reporter_position", "organization"],
        as_dict=True,
    )
    if not acc:
        return empty

    active = acc.status == "active"
    approved = acc.role == "verified_reporter" or bool(acc.reporter_verified_by)
    org_name = acc.organization or frappe.db.get_value(
        "RN Organization Membership", {"user_account": acc.name, "status": "approved"}, "organization")
    org = frappe.db.get_value("RN Organization", org_name,
                              ["title", "verification_status", "identity_verification_status"],
                              as_dict=True) if org_name else None
    org_ok = bool(org) and (str(org.verification_status or "").lower() in VERIFIED_ORG or
                            str(org.identity_verification_status or "").lower() in VERIFIED_ORG)
    ends = endorsements(account_name, detail=detail)
    verifier = frappe.db.get_value("RN Verifier Profile", {"user": acc.name, "verifier_status": "active"},
                                   ["verifier_type", "trust_level"], as_dict=True)
    status = _status(active, approved, org_ok, ends, verifier.trust_level if verifier else None)

    verifiers = ([_approver_item(acc)] if approved else []) + [
        {k: v for k, v in e.items() if k != "trust_level"} for e in ends]

    evidence = [{"key": "account", "ok": active, "label": "Akun Rescue-Net",
                 "detail": f"{'Aktif' if active else acc.status}, dibuat {str(acc.creation)[:10]}"}]
    if detail:
        has_phone = bool(normalize_phone(acc.phone))
        evidence.append({"key": "login", "ok": True, "label": "Cara masuk",
                         "detail": "Google" if is_google_login(acc.frappe_user) else "Kata sandi"})
        evidence.append({"key": "phone", "ok": has_phone, "label": "No HP",
                         "detail": "Terisi (belum dicek OTP)" if has_phone else "Belum diisi"})
    if org:
        evidence.append({"key": "org", "ok": org_ok, "label": "Organisasi",
                         "detail": f"{org.title} — {'terverifikasi' if org_ok else 'belum terverifikasi'}"})
    if verifier:
        evidence.append({"key": "verifier", "ok": cint(verifier.trust_level) >= 2, "label": "Anggota jaringan verifikator",
                         "detail": f"{TYPE_LABEL.get(verifier.verifier_type, verifier.verifier_type)}, trust {cint(verifier.trust_level)}"})
    rows = frappe.get_all("RN Community Report", filters={"reporter_user": acc.name}, fields=["status"],
                          limit_page_length=500)
    done = sum(1 for r in rows if r.status in DONE_STATUSES)
    rejected = sum(1 for r in rows if r.status == "rejected")
    evidence.append({"key": "history", "ok": done > 0 and rejected == 0, "label": "Riwayat laporan",
                     "detail": f"{len(rows)} laporan · {done} terverifikasi · {rejected} ditolak"})
    return {"status": status, "count": len(ends), "verifiers": verifiers, "evidence": evidence}


def quick_status(account_names):
    """Status, count and the public 'verified by' list for many accounts in a handful of queries
    (the public report list). Same rule as verification_profile."""
    accounts = sorted({a for a in account_names if a})
    if not accounts:
        return {}
    accs = {a.name: a for a in frappe.get_all(
        "RN User Account", filters={"name": ["in", accounts]},
        fields=["name", "role", "status", "reporter_verified_by", "reporter_verified_at", "reporter_position",
                "organization"], limit_page_length=0)}
    member_org = {}
    for m in frappe.get_all("RN Organization Membership", filters={"user_account": ["in", accounts], "status": "approved"},
                            fields=["user_account", "organization"], order_by="creation asc", limit_page_length=0):
        member_org.setdefault(m.user_account, m.organization)
    orgs = set(filter(None, [a.organization for a in accs.values()] + list(member_org.values())))
    org_ok = {o.name: (str(o.verification_status or "").lower() in VERIFIED_ORG or
                       str(o.identity_verification_status or "").lower() in VERIFIED_ORG)
              for o in frappe.get_all("RN Organization", filters={"name": ["in", list(orgs)]},
                                      fields=["name", "verification_status", "identity_verification_status"],
                                      limit_page_length=0)} if orgs else {}
    verifiers = {v.user: v for v in frappe.get_all(
        "RN Verifier Profile", filters={"user": ["in", accounts], "verifier_status": "active"},
        fields=["user", "trust_level"], limit_page_length=0)}
    ends = {}
    now = frappe.utils.now_datetime()
    for r in frappe.get_all("RN Verification Endorsement",
                            filters={"target_type": "reporter", "target_id": ["in", accounts], "status": "active"},
                            fields=["name", "target_id", "verifier", "method", "vouched_via", "statement", "verified_at",
                                    "expires_at"], order_by="verified_at desc", limit_page_length=0):
        if r.expires_at and frappe.utils.get_datetime(r.expires_at) < now:
            continue
        v = frappe.db.get_value("RN Verifier Profile", r.verifier,
                                ["title", "verifier_type", "position_title", "verifier_status", "trust_level"],
                                as_dict=True)
        if not v or v.verifier_status != "active":
            continue
        item = _verifier_item(r, v, False)
        item["trust_level"] = cint(v.trust_level)
        ends.setdefault(r.target_id, []).append(item)
    out = {}
    for name in accounts:
        a = accs.get(name)
        if not a:
            continue
        org = a.organization or member_org.get(name)
        e = ends.get(name, [])
        approved = a.role == "verified_reporter" or bool(a.reporter_verified_by)
        v = verifiers.get(name)
        status = _status(a.status == "active", approved, bool(org and org_ok.get(org)), e,
                         v.trust_level if v else None)
        listing = ([_approver_item(a)] if approved else []) + [
            {k: x for k, x in i.items() if k != "trust_level"} for i in e]
        out[name] = {"status": status, "count": len(e), "verifiers": listing}
    return out
