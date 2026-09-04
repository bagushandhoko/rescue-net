"""Masukan Masyarakat — forum diskusi / masukan warga per disaster event
(blueprint: "menyediakan forum diskusi/masukan masyarakat"). Warga bisa
posting tanpa akun; operator posko / koordinator memberi tanggapan resmi.
"""

import frappe
from frappe.utils import now_datetime, cint

from rescue_net.access_policy import rn_actor, is_system_manager
from rescue_net.reference_resolver import resolve_disaster_event

_CATS = ("usul", "keluhan", "informasi", "pertanyaan")
_RESPOND_ROLES = {"community_coordinator", "posko_operator", "command_center",
                  "system_manager"}


def _event(v):
    if not v:
        return None
    try:
        return resolve_disaster_event(v)
    except Exception:
        return v


def _event_or_filters(disaster_event, ev):
    vals = [x for x in {ev, disaster_event} if x]
    if not vals:
        return None
    return [
        ["disaster_event", "in", vals],
        ["disaster_event_legacy_id", "in", vals],
    ]


@frappe.whitelist(allow_guest=True)
def feedback_threads(disaster_event=None, category=None, limit=200):
    ev = _event(disaster_event)
    filters = {"parent_feedback": ["in", ["", None]], "status": ["!=", "hidden"]}
    if category in _CATS:
        filters["category"] = category
    orf = _event_or_filters(disaster_event, ev)

    roots = frappe.get_all(
        "RN Community Feedback", filters=filters, or_filters=orf,
        fields=["name", "topic", "category", "author_name", "body", "wilayah",
                "upvotes", "status", "official_response", "responded_by",
                "responded_at", "creation"],
        order_by="upvotes desc, creation desc", limit_page_length=cint(limit) or 200,
    )
    names = [r.name for r in roots]
    replies_by_parent = {}
    if names:
        for rp in frappe.get_all(
            "RN Community Feedback",
            filters={"parent_feedback": ["in", names], "status": ["!=", "hidden"]},
            fields=["name", "parent_feedback", "author_name", "body", "creation",
                    "official_response", "responded_by"],
            order_by="creation asc", limit_page_length=1000,
        ):
            replies_by_parent.setdefault(rp.parent_feedback, []).append(rp)

    for r in roots:
        r["replies"] = replies_by_parent.get(r.name, [])
        r["reply_count"] = len(r["replies"])

    counts = {}
    for c in _CATS:
        counts[c] = len(frappe.get_all(
            "RN Community Feedback",
            filters={"parent_feedback": ["in", ["", None]], "status": ["!=", "hidden"], "category": c},
            or_filters=orf, limit_page_length=0, pluck="name",
        ))

    return {"disaster_event": ev, "threads": roots, "category_counts": counts,
            "open_count": sum(1 for r in roots if r.status == "open")}


@frappe.whitelist(allow_guest=True)
def post_feedback(topic, body, disaster_event=None, category="usul",
                  author_name=None, author_contact=None, wilayah=None,
                  parent_feedback=None):
    topic = str(topic or "").strip()
    body = str(body or "").strip()
    if not topic or not body:
        frappe.throw("Topik dan isi wajib diisi.")
    if len(body) > 4000:
        frappe.throw("Isi terlalu panjang (maks 4000 karakter).")

    actor = rn_actor(required=False)
    ev = _event(disaster_event)

    doc = frappe.new_doc("RN Community Feedback")
    if ev and frappe.db.exists("RN Disaster Event", ev):
        doc.disaster_event = ev
    else:
        doc.disaster_event_legacy_id = disaster_event
    doc.topic = topic[:180]
    doc.category = category if category in _CATS else "usul"
    doc.author_name = (author_name or (actor.get("username") if actor else None) or "Warga")[:120]
    doc.author_contact = author_contact
    doc.author_user = actor.get("name") if actor else None
    doc.body = body
    doc.wilayah = wilayah
    if parent_feedback and frappe.db.exists("RN Community Feedback", parent_feedback):
        doc.parent_feedback = parent_feedback
    doc.status = "open"
    doc.insert(ignore_permissions=True)
    return {"feedback": doc.name, "status": doc.status}


@frappe.whitelist(allow_guest=True)
def upvote_feedback(feedback):
    if not frappe.db.exists("RN Community Feedback", feedback):
        frappe.throw("Masukan tidak ditemukan.")
    n = cint(frappe.db.get_value("RN Community Feedback", feedback, "upvotes")) + 1
    frappe.db.set_value("RN Community Feedback", feedback, "upvotes", n)
    return {"feedback": feedback, "upvotes": n}


@frappe.whitelist()
def respond_feedback(feedback, response=None, status=None):
    actor = rn_actor(required=True)
    if not (is_system_manager() or (actor.get("role") in _RESPOND_ROLES)):
        frappe.throw("Hanya operator / koordinator yang dapat menanggapi.", frappe.PermissionError)
    doc = frappe.get_doc("RN Community Feedback", feedback)
    if response is not None and str(response).strip():
        doc.official_response = str(response)[:2000]
        doc.responded_by = actor.get("username") or actor.get("name")
        doc.responded_at = now_datetime()
    if status in ("open", "noted", "resolved", "hidden"):
        doc.status = status
    doc.save(ignore_permissions=True)
    return {"feedback": doc.name, "status": doc.status}
