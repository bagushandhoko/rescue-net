import frappe
from frappe.utils import cint, now_datetime

from rescue_net.access_policy import (
    approved_member,
    is_system_manager,
    rn_actor,
)
from rescue_net.intelligence.freshness import freshness


VERIFY_ROLES = {
    "posko_operator",
    "medical_operator",
    "shelter_operator",
}


def _can_verify(actor):
    return (
        is_system_manager()
        or (
            actor
            and actor.role in VERIFY_ROLES
        )
    )


def _linked_community_owner(report):
    return frappe.db.get_value(
        "RN Community Need",
        {"source_report": report},
        "community_owner",
    )


def _can_view_report(actor, report):
    if _can_verify(actor):
        return True

    if not actor or not actor.name:
        return False

    reporter = frappe.db.get_value(
        "RN Community Report",
        report,
        "reporter_user",
    )

    if reporter == actor.name:
        return True

    owner = _linked_community_owner(report)

    return approved_member(
        actor.name,
        owner,
    )


def _serialize_report(row):
    evidence_count = frappe.db.count(
        "RN Community Report Evidence",
        {"report": row.name},
    )

    latest = frappe.get_all(
        "RN Community Report Verification",
        filters={"report": row.name},
        fields=[
            "action",
            "after_status",
            "event_created_at",
            "verifier_role",
        ],
        order_by="event_created_at desc",
        limit_page_length=1,
    )

    age = freshness(
        row.source_updated_at,
        row.observed_at,
        row.modified,
        row.freshness_policy_minutes,
        "report",
    )

    return {
        "name": row.name,
        "title": row.title,
        "report_type": row.report_type,
        "description": row.description,
        "priority": row.priority,
        "urgent_needs": row.urgent_needs,
        "location_text": row.location_text,
        "province_name": row.province_name,
        "city_name": row.city_name,
        "district_name": row.district_name,
        "village_name": row.village_name,
        "status": row.status,
        "trust_score": row.trust_score,
        "verification_status": (
            "verified"
            if row.status == "verified"
            else row.status
        ),
        "verified_by": row.verified_by,
        "verified_at": row.verified_at,
        "evidence_count": evidence_count,
        "latest_action": latest[0] if latest else None,
        "freshness": age,
        "source_updated_at": row.source_updated_at,
        "observed_at": row.observed_at,
    }


@frappe.whitelist()
def dashboard():
    actor = rn_actor()

    fields = [
        "name", "title", "report_type", "description",
        "priority", "urgent_needs", "location_text",
        "province_name", "city_name",
        "district_name", "village_name",
        "status", "trust_score",
        "verified_by", "verified_at",
        "observed_at", "source_updated_at",
        "freshness_policy_minutes", "modified",
    ]

    if _can_verify(actor):
        rows = frappe.get_all(
            "RN Community Report",
            fields=fields,
            order_by="creation desc",
            limit_page_length=200,
        )
        mode = "verifier"
    else:
        rows = frappe.get_all(
            "RN Community Report",
            filters={"reporter_user": actor.name},
            fields=fields,
            order_by="creation desc",
            limit_page_length=200,
        )
        mode = "reporter"

    return {
        "mode": mode,
        "role": actor.role,
        "reports": [
            _serialize_report(row)
            for row in rows
        ],
    }


@frappe.whitelist()
def list_evidence(report):
    actor = rn_actor()

    if not _can_view_report(actor, report):
        frappe.throw(
            "Anda tidak memiliki akses ke laporan ini",
            frappe.PermissionError,
        )

    return frappe.get_all(
        "RN Community Report Evidence",
        filters={"report": report},
        fields=[
            "name", "file_url", "file_type",
            "evidence_type", "caption",
            "verification_status",
            "uploaded_at", "observed_at",
            "source_updated_at", "uploader_user",
        ],
        order_by="uploaded_at desc",
        limit_page_length=100,
    )


@frappe.whitelist()
def add_evidence(
    report,
    file_url,
    evidence_type="photo",
    caption=None,
    observed_at=None,
):
    actor = rn_actor()

    if not _can_view_report(actor, report):
        frappe.throw(
            "Anda tidak memiliki akses ke laporan ini",
            frappe.PermissionError,
        )

    if not frappe.db.exists("RN Community Report", report):
        frappe.throw("Laporan tidak ditemukan")

    doc = frappe.new_doc(
        "RN Community Report Evidence"
    )
    doc.report = report
    doc.file_url = file_url
    doc.file_type = evidence_type
    doc.evidence_type = evidence_type
    doc.caption = caption
    doc.verification_status = "pending"
    doc.uploaded_at = now_datetime()
    doc.observed_at = observed_at or now_datetime()
    doc.source_updated_at = now_datetime()
    doc.uploader_user = actor.name
    doc.insert(ignore_permissions=True)

    return {
        "evidence": doc.name,
        "verification_status": doc.verification_status,
    }


@frappe.whitelist()
def set_evidence_status(evidence, status):
    actor = rn_actor()

    if not _can_verify(actor):
        frappe.throw(
            "Hanya verifier/operator yang dapat "
            "memverifikasi evidence",
            frappe.PermissionError,
        )

    if status not in ("pending", "verified", "rejected"):
        frappe.throw("Status evidence tidak valid")

    doc = frappe.get_doc(
        "RN Community Report Evidence",
        evidence,
    )

    doc.verification_status = status
    doc.save(ignore_permissions=True)

    return {
        "evidence": doc.name,
        "verification_status": status,
    }


@frappe.whitelist()
def act(
    report,
    action,
    notes=None,
    trust_score=None,
    decision_confidence=None,
):
    actor = rn_actor()

    if not _can_verify(actor):
        frappe.throw(
            "Hanya verifier/operator yang dapat "
            "mengubah status verifikasi",
            frappe.PermissionError,
        )

    action = (action or "").strip().lower()

    transitions = {
        "triage": "triaged",
        "verify": "verified",
        "reject": "rejected",
        "escalate": "escalated",
    }

    if action not in transitions:
        frappe.throw("Action verifikasi tidak valid")

    if action in ("reject", "escalate") and not (notes or "").strip():
        frappe.throw(
            "Catatan wajib untuk reject/escalate"
        )

    doc = frappe.get_doc(
        "RN Community Report",
        report,
    )

    before_status = doc.status or "none"
    before_trust = cint(doc.trust_score or 0)

    evidence_count = frappe.db.count(
        "RN Community Report Evidence",
        {"report": report},
    )

    if action == "verify" and evidence_count == 0 and not (notes or "").strip():
        frappe.throw(
            "Laporan tanpa evidence tetap dapat diverifikasi, "
            "tetapi verifier wajib memberi catatan dasar verifikasi"
        )

    if trust_score not in (None, ""):
        trust = cint(trust_score)
        if trust < 0 or trust > 100:
            frappe.throw("Trust score harus 0-100")
        doc.trust_score = trust

    doc.status = transitions[action]

    if action == "verify":
        doc.verified_by = actor.name
        doc.verified_at = now_datetime()

    doc.save(ignore_permissions=True)

    log = frappe.new_doc(
        "RN Community Report Verification"
    )
    log.report = report
    log.verifier_user = actor.name
    log.verifier_role = actor.role
    log.action = action
    log.notes = notes
    log.before_status = before_status
    log.after_status = doc.status
    log.event_created_at = now_datetime()
    log.trust_score_before = before_trust
    log.trust_score_after = cint(doc.trust_score or 0)
    log.evidence_count = evidence_count

    if decision_confidence not in (None, ""):
        confidence = cint(decision_confidence)
        if confidence < 0 or confidence > 100:
            frappe.throw(
                "Decision confidence harus 0-100"
            )
        log.decision_confidence = confidence

    log.insert(ignore_permissions=True)

    return {
        "report": doc.name,
        "action": action,
        "before_status": before_status,
        "after_status": doc.status,
        "trust_score": doc.trust_score,
        "evidence_count": evidence_count,
        "verification_log": log.name,
    }
