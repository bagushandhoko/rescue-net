"""Verifikasi pengelola donasi untuk super admin (owner 24 Nov 2026: "verifikasi pengelola donasi gimana? sebagai
super admin harusnya ada di Pengaturan").

Rekening/QRIS program hanya tampil ke publik bila pemrakarsanya terverifikasi (documents.initiator_verified). Halaman
ini mendaftar program yang SUDAH mengisi rekening/QRIS tetapi masih tersembunyi, dengan alasan dan tindakannya:
- organisasi/posko belum terverifikasi -> setujui lewat api_verification.approval_action (jalur & log yang sama dengan
  antrean Sistem Verifikasi);
- organisasi sudah terverifikasi tetapi pembuat program anggota biasa yang belum dijamin -> "jamin anggota"
  (member_verified=1, dicatat di RN Approval Log).
"""

import frappe
from frappe.utils import now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor
from rescue_net.donor_program.common import _owner_verified
from rescue_net.donor_program.documents import _of_kind, _org_creator_trusted, initiator_verified


def _assert_super_admin():
    if not is_system_manager():
        frappe.throw("Khusus super admin.", frappe.PermissionError)


def _title(doctype, name):
    return (frappe.db.get_value(doctype, name, "title") if name and frappe.db.exists(doctype, name) else None) or name


@frappe.whitelist()
def initiator_queue(include_verified=0):
    _assert_super_admin()
    from rescue_net.services.drill import is_simulation_event
    rows = frappe.get_all("RN Donor Program", filters={"status": ["not in", ["cancelled", "completed"]]},
                          fields=["name", "program_name", "disaster_event", "owner_type", "owner_id", "created_by_user",
                                  "bank_account_number", "work_drawings", "status", "modified"],
                          order_by="modified desc", limit_page_length=1000)
    out = []
    for r in rows:
        has_bank, has_qris = bool(r.bank_account_number), bool(_of_kind(r.work_drawings, "qris"))
        verified = initiator_verified(r)
        if verified and not int(include_verified or 0):
            continue
        owner_doctype = {"organization": "RN Organization", "posko": "RN Posko"}.get(r.owner_type)
        owner_ok = _owner_verified(r.owner_type, r.owner_id)
        action, reason = None, None
        if not verified:
            if r.owner_type in ("organization", "posko") and not owner_ok:
                action = {"type": "approve", "kind": "organisasi" if r.owner_type == "organization" else "posko", "name": r.owner_id}
                reason = ("Organisasi" if r.owner_type == "organization" else "Posko") + " pemrakarsa belum terverifikasi"
            elif r.owner_type == "organization" and not _org_creator_trusted(r):
                action = {"type": "vouch", "program": r.name}
                reason = "Pembuat program anggota biasa yang belum dijamin organisasinya"
            else:
                reason = "Pemrakarsa belum terverifikasi"
        out.append({
            "program": r.name, "program_name": r.program_name, "disaster_event": r.disaster_event,
            "event_title": _title("RN Disaster Event", r.disaster_event), "simulation": bool(is_simulation_event(r.disaster_event)),
            "owner_type": r.owner_type, "owner_id": r.owner_id, "owner_title": _title(owner_doctype, r.owner_id) if owner_doctype else r.owner_id,
            "owner_status": frappe.db.get_value(owner_doctype, r.owner_id, "verification_status") if owner_doctype and r.owner_id else None,
            "creator": frappe.db.get_value("RN User Account", r.created_by_user, "title") if r.created_by_user else None,
            "has_bank": has_bank, "has_qris": has_qris, "verified": bool(verified), "reason": reason, "action": action,
            "pending_donations": frappe.db.count("RN Cash Donation", {"donor_program": r.name, "status": "pending"}),
        })
    # yang sudah mengisi rekening/QRIS (siap tampil) di atas
    out.sort(key=lambda x: (x["verified"], not (x["has_bank"] or x["has_qris"])))
    return {"rows": out, "waiting": sum(1 for x in out if not x["verified"])}


@frappe.whitelist(methods=["POST"])
def verify_initiator(program, note=None):
    """Satu tombol: jalankan tindakan yang dibutuhkan agar pemrakarsa program ini terverifikasi."""
    _assert_super_admin()
    row = frappe.db.get_value("RN Donor Program", program, ["name", "owner_type", "owner_id", "created_by_user"], as_dict=True)
    if not row:
        frappe.throw("Program tidak ditemukan.", frappe.DoesNotExistError)
    item = next((x for x in initiator_queue(include_verified=1)["rows"] if x["program"] == program), None)
    act = (item or {}).get("action")
    if not act:
        return {"program": program, "verified": bool(item and item["verified"]), "done": None}
    if act["type"] == "approve":
        from rescue_net.api_verification import approval_action
        approval_action(act["kind"], act["name"], "approve", note or "Verifikasi pengelola donasi (Pengaturan Sistem RN)")
    else:
        m = frappe.db.get_value("RN Organization Membership", {"user_account": row.created_by_user, "organization": row.owner_id,
                                                               "status": "approved"}, "name")
        if not m:
            frappe.throw("Keanggotaan pembuat program tidak ditemukan.")
        frappe.db.set_value("RN Organization Membership", m, "member_verified", 1)
        actor = rn_actor(required=False)
        frappe.get_doc({"doctype": "RN Approval Log", "kind": "user", "target_doctype": "RN Organization Membership",
                        "target_name": m, "action": "approve", "before_status": "member", "after_status": "member_verified",
                        "actor_account": getattr(actor, "name", None), "actor_name": frappe.session.user,
                        "actor_role": "System Manager", "note": (note or "Jamin anggota pembuat program %s" % program)[:500],
                        "decided_at": now_datetime()}).insert(ignore_permissions=True)
    row2 = frappe.db.get_value("RN Donor Program", program, ["name", "owner_type", "owner_id", "created_by_user"], as_dict=True)
    return {"program": program, "verified": bool(initiator_verified(row2)), "done": act["type"]}
