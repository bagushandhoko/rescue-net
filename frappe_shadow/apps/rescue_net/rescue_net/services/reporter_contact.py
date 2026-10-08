"""Hubungi pelapor + level verifikasi pelapor (owner 2026-10-08).

Nomor HP / WhatsApp pelapor adalah data pribadi: tidak pernah ada di daftar laporan publik. Hanya
System Manager, pengelola posko tujuan laporan (can_manage_posko, termasuk koordinator organisasi dan
komando), atau verifikator aktif yang dapat membukanya lewat `api_reports.reporter_contact`, dan hanya bila
pelapor bersedia dihubungi (consent_to_contact). Setiap pembukaan dicatat di RN Verification Action.

Level verifikasi pelapor dihitung dari bukti yang ada (bukan angka buatan): ditampilkan beserta buktinya.
  0 Belum terverifikasi   — tidak ada akun Rescue-Net
  1 Akun terdaftar        — akun aktif (login Google / kata sandi)
  2 Kontak tersedia       — akun + no HP (belum dicek OTP)
  3 Terverifikasi         — Pelapor Terverifikasi (disetujui), anggota organisasi terverifikasi, atau didukung
                            minimal satu verifikator aktif (ketua organisasi, aparat, kepala desa, dst.)
  4 Verifikator           — profil verifikator aktif (trust >= 2)
Lencana centang biru = level >= 3. Daftar pendukung (siapa yang memverifikasi) hanya dengan nama untuk yang
berwenang; publik hanya melihat jenisnya (mis. "Pemerintah / aparat").
"""

import frappe
from frappe.utils import cint

from rescue_net.services.reporter import is_google_login, normalize_phone

LEVELS = {0: "Belum terverifikasi", 1: "Akun terdaftar", 2: "Kontak tersedia", 3: "Terverifikasi", 4: "Verifikator"}
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


def endorsements(account_name, names=False):
    """Active endorsements of a reporter by verifiers who are still active. Names, positions,
    organisations and statements only when `names` (authorised viewers); otherwise just the types."""
    if not account_name:
        return []
    rows = frappe.get_all(
        "RN Verification Endorsement",
        filters={"target_type": "reporter", "target_id": account_name, "status": "active"},
        fields=["name", "verifier", "method", "verification_level", "statement", "verified_at", "expires_at"],
        order_by="verified_at desc", limit_page_length=50)
    now = frappe.utils.now_datetime()
    out = []
    for r in rows:
        if r.expires_at and frappe.utils.get_datetime(r.expires_at) < now:
            continue
        v = frappe.db.get_value("RN Verifier Profile", r.verifier,
                                ["title", "verifier_type", "position_title", "organization", "verifier_status"],
                                as_dict=True)
        if not v or v.verifier_status != "active":
            continue
        item = {"type": v.verifier_type, "type_label": TYPE_LABEL.get(v.verifier_type, "Verifikator"),
                "method_label": METHOD_LABEL.get(r.method, r.method), "level": cint(r.verification_level),
                "verified_at": str(r.verified_at)[:10] if r.verified_at else None}
        if names:
            item.update({
                "endorsement": r.name, "verifier_name": v.title, "position": v.position_title,
                "organization": frappe.db.get_value("RN Organization", v.organization, "title") if v.organization else None,
                "statement": r.statement})
        out.append(item)
    return out


def _decide_level(active, has_phone, verified_flag, org_ok, endorsed, verifier_trust):
    level = 1 if active else 0
    if level and has_phone:
        level = 2
    if level >= 1 and (verified_flag or org_ok or endorsed):
        level = 3
    if verifier_trust is not None and cint(verifier_trust) >= 2:
        level = 4
    return level


def verification_profile(account_name, names=False):
    """Evidence-based level of a reporter's account. `account_name` may be None (no account)."""
    if not account_name:
        return {"level": 0, "label": LEVELS[0], "endorsements": [], "evidence": [
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

    verified_reporter = acc.role == "verified_reporter" or bool(acc.reporter_verified_by)
    if verified_reporter:
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

    ends = endorsements(account_name, names=names)
    evidence.append({"key": "endorsed", "ok": bool(ends), "label": "Didukung verifikator",
                     "detail": f"{len(ends)} verifikator" if ends else "Belum ada"})

    verifier = frappe.db.get_value("RN Verifier Profile", {"user": acc.name, "verifier_status": "active"},
                                   ["verifier_type", "trust_level"], as_dict=True)
    if verifier:
        evidence.append({"key": "verifier", "ok": cint(verifier.trust_level) >= 2, "label": "Verifikator",
                         "detail": f"{TYPE_LABEL.get(verifier.verifier_type, verifier.verifier_type)}, trust {cint(verifier.trust_level)}"})

    rows = frappe.get_all("RN Community Report", filters={"reporter_user": acc.name}, fields=["status"],
                          limit_page_length=500)
    done = sum(1 for r in rows if r.status in DONE_STATUSES)
    rejected = sum(1 for r in rows if r.status == "rejected")
    evidence.append({"key": "history", "ok": done > 0 and rejected == 0, "label": "Riwayat laporan",
                     "detail": f"{len(rows)} laporan · {done} terverifikasi · {rejected} ditolak"})

    level = _decide_level(active, has_phone, verified_reporter, org_ok, bool(ends),
                          verifier.trust_level if verifier else None)
    return {"level": level, "label": LEVELS[level], "endorsements": ends, "evidence": evidence}


def quick_levels(account_names):
    """Level + public endorsement types for many accounts in a handful of queries (the public report
    list). Same rule as verification_profile, without the evidence text."""
    accounts = sorted({a for a in account_names if a})
    if not accounts:
        return {}
    accs = {a.name: a for a in frappe.get_all(
        "RN User Account", filters={"name": ["in", accounts]},
        fields=["name", "role", "status", "phone", "reporter_verified_by", "organization"], limit_page_length=0)}
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
    types = {}
    for e in frappe.get_all("RN Verification Endorsement",
                            filters={"target_type": "reporter", "target_id": ["in", accounts], "status": "active"},
                            fields=["target_id", "verifier", "expires_at"], limit_page_length=0):
        v = frappe.db.get_value("RN Verifier Profile", e.verifier, ["verifier_type", "verifier_status"], as_dict=True)
        if not v or v.verifier_status != "active":
            continue
        if e.expires_at and frappe.utils.get_datetime(e.expires_at) < frappe.utils.now_datetime():
            continue
        types.setdefault(e.target_id, []).append(TYPE_LABEL.get(v.verifier_type, "Verifikator"))
    out = {}
    for name in accounts:
        a = accs.get(name)
        if not a:
            continue
        org = a.organization or member_org.get(name)
        v = verifiers.get(name)
        level = _decide_level(a.status == "active", bool(normalize_phone(a.phone)),
                              a.role == "verified_reporter" or bool(a.reporter_verified_by),
                              bool(org and org_ok.get(org)), bool(types.get(name)), v.trust_level if v else None)
        out[name] = {"level": level, "label": LEVELS[level], "types": sorted(set(types.get(name, [])))}
    return out
