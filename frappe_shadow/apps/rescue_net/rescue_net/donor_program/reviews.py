"""Ulasan publik untuk penyelenggara program donasi (owner 2026-11-02 22:40: "ada review dari publik untuk memantau
kerja atau respon dari penyelenggara"; dikerjakan 2026-11-09).

- Siapa pun (tamu juga) melihat nilai rata-rata + daftar ulasan yang tampil.
- Mengulas butuh login; satu akun = satu ulasan per program (mengirim lagi = memperbarui). Pengelola program tidak
  boleh mengulas programnya sendiri.
- Pengelola program menjawab ulasan; Control Centre / System Manager bisa menyembunyikan ulasan yang melanggar.
"""

import frappe
from frappe.utils import cint, now_datetime

from rescue_net.access_policy import rn_actor
from rescue_net.api_kitchen import _is_control
from rescue_net.donor_program.common import _program, _program_manager

MAX_COMMENT = 1000


def _actor_or_none():
    if frappe.session.user in (None, "", "Guest"):
        return None
    try:
        return rn_actor()
    except Exception:
        return None


def _visible_program(name):
    row = _program(name)
    if (row.get("status") or "") == "cancelled":
        frappe.throw("Program tidak ditemukan")
    return row


def _short_name(title):
    """'Budi Santoso' -> 'Budi S.' (tanda seperti '[SIMULASI]' dilewati)."""
    parts = [w for w in (title or "").split() if not (w.startswith("[") and w.endswith("]"))]
    if not parts:
        return "Pengguna"
    return parts[0] + (" " + parts[1][0] + "." if len(parts) > 1 else "")


@frappe.whitelist(allow_guest=True)
def program_reviews(donor_program, limit=30):
    row = _visible_program(donor_program)
    actor = _actor_or_none()
    can_moderate = bool(actor and _is_control(actor))
    is_manager = bool(actor and (can_moderate or _program_manager(actor, row)))
    filters = {"program": row.name}
    if not can_moderate:
        filters["status"] = "published"
    rows = frappe.get_all("RN Program Review", filters=filters,
                          fields=["name", "user_account", "reviewer_name", "anonymous", "rating", "comment",
                                  "status", "reply", "reply_at", "creation"],
                          order_by="creation desc", limit_page_length=min(cint(limit) or 30, 100))
    published = frappe.get_all("RN Program Review", filters={"program": row.name, "status": "published"},
                               fields=["rating"], limit_page_length=0)
    count = len(published)
    dist = {str(i): 0 for i in range(1, 6)}
    for p in published:
        dist[str(cint(p.rating))] = dist.get(str(cint(p.rating)), 0) + 1
    mine = None
    items = []
    for r in rows:
        own = bool(actor and r.user_account == actor.name)
        if own:
            mine = {"rating": r.rating, "comment": r.comment, "anonymous": cint(r.anonymous)}
        items.append({
            "name": r.name,
            "reviewer": "Anonim" if cint(r.anonymous) else (r.reviewer_name or "Pengguna"),
            "rating": cint(r.rating), "comment": r.comment or "", "date": str(r.creation)[:10],
            "reply": r.reply or "", "reply_date": str(r.reply_at or "")[:10] or None,
            "mine": own, "hidden": r.status == "hidden" if can_moderate else None,
        })
    return {
        "program": row.name,
        "count": count,
        "average": round(sum(cint(p.rating) for p in published) / count, 1) if count else None,
        "distribution": dist,
        "reviews": items,
        "mine": mine,
        "can_review": bool(actor) and not is_manager,
        "can_reply": is_manager,
        "can_moderate": can_moderate,
        "login_required": not actor,
    }


@frappe.whitelist(methods=["POST"])
def submit_review(donor_program, rating, comment=None, anonymous=0):
    actor = rn_actor()
    row = _visible_program(donor_program)
    if _program_manager(actor, row):
        frappe.throw("Pengelola program tidak bisa mengulas programnya sendiri.", frappe.PermissionError)
    rating = cint(rating)
    if not 1 <= rating <= 5:
        frappe.throw("Nilai harus 1 sampai 5 bintang.")
    comment = (comment or "").strip()[:MAX_COMMENT]
    title = frappe.db.get_value("RN User Account", actor.name, "title")
    existing = frappe.db.get_value("RN Program Review", {"program": row.name, "user_account": actor.name}, "name")
    if existing:
        doc = frappe.get_doc("RN Program Review", existing)
    else:
        doc = frappe.new_doc("RN Program Review")
        doc.program = row.name
        doc.user_account = actor.name
    doc.reviewer_name = _short_name(title)
    doc.anonymous = 1 if cint(anonymous) else 0
    doc.rating = rating
    doc.comment = comment
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
    if not existing:
        from rescue_net.services import inbox as _ib
        _msg = "Ulasan baru %s bintang untuk '%s'." % (rating, row.program_name)
        _link = "program-khusus.html?program=%s#ulasan" % row.name
        if row.get("created_by_user"):
            _ib.notify_account(row.created_by_user, _msg, _link)
        elif row.get("owner_type") == "organization":
            _ib.notify_org_managers(row.owner_id, _msg, _link, roles=("owner", "deputy"))
    return {"review": doc.name, "updated": bool(existing)}


@frappe.whitelist(methods=["POST"])
def reply_review(review, reply):
    actor = rn_actor()
    doc = frappe.get_doc("RN Program Review", review)
    row = _program(doc.program)
    if not (_is_control(actor) or _program_manager(actor, row)):
        frappe.throw("Hanya pengelola program yang boleh menjawab ulasan.", frappe.PermissionError)
    doc.reply = (reply or "").strip()[:MAX_COMMENT] or None
    doc.reply_by_user = frappe.session.user if doc.reply else None
    doc.reply_at = now_datetime() if doc.reply else None
    doc.save(ignore_permissions=True)
    if doc.reply:
        from rescue_net.services import inbox as _ib
        _ib.notify_account(doc.user_account, "Penyelenggara '%s' menjawab ulasan Anda." % row.program_name,
                           "program-khusus.html?program=%s#ulasan" % row.name)
    return {"review": doc.name, "reply": doc.reply}


@frappe.whitelist(methods=["POST"])
def moderate_review(review, status, reason=None):
    actor = rn_actor()
    if not _is_control(actor):
        frappe.throw("Hanya Control Centre yang boleh menyembunyikan ulasan.", frappe.PermissionError)
    if status not in ("published", "hidden"):
        frappe.throw("Status tidak dikenal.")
    if status == "hidden" and not (reason or "").strip():
        frappe.throw("Tulis alasan menyembunyikan ulasan.")
    frappe.db.set_value("RN Program Review", review, {"status": status,
                        "hidden_reason": (reason or "").strip()[:140] if status == "hidden" else None})
    return {"review": review, "status": status}
