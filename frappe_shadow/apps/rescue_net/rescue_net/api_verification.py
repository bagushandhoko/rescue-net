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


# ============================================================
# Verification & Approval — pages/verification-approval.html
#
# A second, distinct concept from the "trusted verifier" identity/
# endorsement network above: a cross-doctype moderation queue over the
# verification_status (or role_request_status) that almost every
# self/community-submitted record in this app already carries. Real records,
# real actions (login required) — "Merge" from the mock-up is intentionally
# not implemented (deduplicating two records safely needs a target picker +
# data-reconciliation flow this pass doesn't have time to build correctly;
# a decorative Merge button would be worse than omitting it).
# ============================================================

PENDING_TERMS = {"pending", "self_reported", "", None}
URGENT_TERMS = {"critical", "urgent", "high", "tinggi", "darurat"}

_KIND_CONFIG = {
    "user": {
        "label": "User", "doctype": "RN User Account",
        "status_field": "role_request_status", "name_field": "title",
        "verified_value": "approved",
    },
    "organisasi": {
        "label": "Organisasi", "doctype": "RN Organization",
        "status_field": "verification_status", "name_field": "title",
        "verified_value": "official_verified",
    },
    "posko": {
        "label": "Posko", "doctype": "RN Posko",
        "status_field": "verification_status", "name_field": "title",
        "verified_value": "official_verified", "event_scoped": True,
    },
    "needs": {
        "label": "Needs", "doctype": "RN Logistic Need",
        "status_field": "verification_status", "name_field": "item_name",
        "verified_value": "verified", "event_scoped": True,
    },
    "expense": {
        "label": "Expense", "doctype": "RN Distribution Flow",
        "status_field": "verification_status", "name_field": "item_name",
        "verified_value": "verified", "event_scoped": True,
    },
}


def _row_owner(row):
    return row.get("owner") or "-"


def _queue_rows_for_kind(kind, event):
    cfg = _KIND_CONFIG[kind]
    fields = ["name", cfg["status_field"], cfg["name_field"], "owner", "creation", "modified"]
    filters = {}
    if cfg.get("event_scoped") and event:
        filters["disaster_event"] = event
    if kind == "needs":
        # also surface RN Shelter Need pending items under the same "needs" bucket
        rows = frappe.get_all(cfg["doctype"], filters=filters,
                               fields=[f for f in fields if f in _cols(cfg["doctype"])] + ["name"],
                               limit_page_length=500)
        rows = [r for r in rows if str(r.get(cfg["status_field"]) or "") in PENDING_TERMS]

        # RN Shelter Need has no disaster_event column of its own — scope via
        # its posko's event instead.
        shelter_filters = {}
        if event:
            posko_names = frappe.get_all("RN Posko", filters={"disaster_event": event}, pluck="name", limit_page_length=1000)
            if not posko_names:
                return rows
            shelter_filters = {"posko": ["in", posko_names]}
        sn_cols = _cols("RN Shelter Need")
        for r in frappe.get_all(
            "RN Shelter Need", filters=shelter_filters,
            fields=[f for f in ("name", "verification_status", "item_name", "owner", "creation", "modified") if f in sn_cols or f == "name"],
            limit_page_length=500,
        ):
            if str(r.get("verification_status") or "") in PENDING_TERMS:
                r["_doctype"] = "RN Shelter Need"
                rows.append(r)
        return rows

    if kind == "expense":
        rows = frappe.get_all(
            cfg["doctype"], filters=filters,
            fields=["name", "verification_status", "item_name", "owner", "creation", "modified",
                    "estimated_cost", "actual_cost"],
            limit_page_length=500,
        )
        return [r for r in rows
                if str(r.get("verification_status") or "") in PENDING_TERMS
                and (_f(r.get("estimated_cost")) or _f(r.get("actual_cost")))]

    rows = frappe.get_all(cfg["doctype"], filters=filters, fields=fields, limit_page_length=500)
    if kind == "user":
        # role_request_status is empty/None for the normal "never asked for
        # a role change" case — only "pending" literally means "awaiting
        # review", unlike the other kinds' verification_status where empty
        # means "self-reported, unverified".
        return [r for r in rows if r.get(cfg["status_field"]) == "pending"]
    return [r for r in rows if str(r.get(cfg["status_field"]) or "") in PENDING_TERMS]


def _cols(doctype):
    return set(frappe.get_meta(doctype).get_valid_columns())


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


@frappe.whitelist(allow_guest=True)
def approval_queue(disaster_event=None, limit=300):
    """Cross-doctype approval queue (matches the DMS mock-up), guest
    read-only. One payload: KPI totals + the queue rows for every kind,
    ready for client-side tab-filter/search/pagination — same pattern as
    every other mockup-alignment dashboard.
    """
    from rescue_net.reference_resolver import resolve_disaster_event
    from rescue_net.api_control_centre import event_evidence

    event = resolve_disaster_event(disaster_event) if disaster_event else None

    queue = []
    for kind, cfg in _KIND_CONFIG.items():
        for r in _queue_rows_for_kind(kind, event):
            status = r.get(cfg["status_field"]) if kind not in ("needs", "expense") else r.get("verification_status")
            name_field = "item_name" if kind in ("needs", "expense") else cfg["name_field"]
            queue.append({
                "kind": kind, "label": cfg["label"],
                "doctype": r.get("_doctype") or cfg["doctype"],
                "name": r["name"],
                "title": r.get(name_field) or r["name"],
                "owner": _row_owner(r),
                "status": status or "self_reported",
                "creation": r.get("creation"),
                "modified": r.get("modified"),
                "urgency": None,
            })

    # Evidence pending — reuse the unified event_evidence() feed.
    evidence_pending = []
    if event:
        for row in event_evidence(event, limit=200):
            if str(row.get("status") or "").lower() == "pending":
                evidence_pending.append({
                    "kind": "evidence", "label": "Evidence",
                    "doctype": "RN Operational Evidence", "name": row.get("id"),
                    "title": row.get("title") or "Evidence",
                    "owner": row.get("uploader") or "-",
                    "status": "pending",
                    "creation": row.get("creation"), "modified": row.get("modified"),
                    "urgency": None, "evidence_url": row.get("evidence_url"),
                })
    queue.extend(evidence_pending)

    # Evidence counts per queue item (real, via event_evidence linkage).
    ev_by_linked = {}
    if event:
        for row in event_evidence(event, limit=300):
            k = row.get("linked_object_id")
            if k:
                ev_by_linked[k] = ev_by_linked.get(k, 0) + 1
    for item in queue:
        item["evidence_count"] = ev_by_linked.get(item["name"], 0)

    queue.sort(key=lambda r: str(r.get("modified") or r.get("creation") or ""), reverse=True)
    queue = queue[: int(limit)]

    counts = {"user": 0, "organisasi": 0, "posko": 0, "needs": 0, "expense": 0, "evidence": 0}
    for item in queue:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "user_pending": counts["user"],
            "organisasi_pending": counts["organisasi"],
            "posko_pending": counts["posko"],
            "needs_pending": counts["needs"],
            "expense_pending": counts["expense"],
            "evidence_pending": counts["evidence"],
        },
        "queue": queue,
    }


@frappe.whitelist(allow_guest=True)
def approval_item_detail(kind, name):
    """Real record detail + linked evidence + a lightweight status timeline
    for the mock-up's "Detail Item" / "Jejak Audit" panels. No fabricated
    numeric Trust/Risk score for kinds that don't carry one — Organisasi and
    Posko already have real `trust_level`/`trusted_verifier_count` fields,
    shown as-is; other kinds show a real signal checklist instead.
    """
    from rescue_net.api_control_centre import event_evidence

    if kind == "evidence":
        # name is the evidence "id" from event_evidence(); look it up fresh.
        doc = frappe.db.get_value(
            "RN Operational Evidence", name,
            ["name", "caption", "verification_status", "creation", "modified",
             "posko", "evidence_type", "file_url"],
            as_dict=True,
        )
        if not doc:
            frappe.throw("Evidence tidak ditemukan")
        return {
            "kind": kind, "name": doc.name, "title": doc.caption or doc.name,
            "status": doc.verification_status, "creation": doc.creation, "modified": doc.modified,
            "fields": {"Posko": doc.posko, "Tipe": doc.evidence_type},
            "evidence": [{"evidence_url": doc.file_url}],
            "trust": None,
            "timeline": _timeline(doc.creation, doc.modified, doc.verification_status),
        }

    if kind not in _KIND_CONFIG:
        frappe.throw("Kind tidak dikenal")

    cfg = _KIND_CONFIG[kind]
    doctype = cfg["doctype"]
    doc = frappe.get_doc(doctype, name)
    status_field = cfg["status_field"] if kind not in ("needs", "expense") else "verification_status"
    status = getattr(doc, status_field, None)

    fields = {}
    trust = None
    if kind == "organisasi":
        fields = {"Tipe": doc.organization_type, "Kontak": doc.contact_person}
        trust = {"trust_level": doc.trust_level, "trusted_verifier_count": doc.trusted_verifier_count}
    elif kind == "posko":
        fields = {"Tipe": doc.posko_type, "Alamat": doc.address, "PIC": doc.officer_in_charge_name}
        trust = {"trust_level": None, "trusted_verifier_count": getattr(doc, "trusted_verifier_count", None)}
    elif kind == "user":
        fields = {"Role Diminta": doc.requested_role, "Email": doc.email, "Phone": doc.phone}
    elif kind == "needs":
        fields = {"Item": doc.item_name, "Jumlah": doc.quantity, "Satuan": doc.unit, "Urgensi": doc.urgency}
    elif kind == "expense":
        fields = {"Item": doc.item_name, "Estimasi Biaya": doc.estimated_cost, "Biaya Aktual": doc.actual_cost}

    evidence = []
    event = getattr(doc, "disaster_event", None)
    if event:
        for row in event_evidence(event, limit=200):
            if row.get("linked_object_id") == name:
                evidence.append({"evidence_url": row.get("evidence_url"), "caption": row.get("caption")})

    return {
        "kind": kind, "name": name, "title": getattr(doc, cfg["name_field"], None) or name,
        "status": status, "creation": doc.creation, "modified": doc.modified,
        "fields": fields, "evidence": evidence, "trust": trust,
        "timeline": _timeline(doc.creation, doc.modified, status),
    }


def _timeline(creation, modified, status):
    out = [{"time": creation, "label": "Diajukan"}]
    if modified and str(modified) != str(creation):
        out.append({"time": modified, "label": "Status saat ini: " + str(status or "-")})
    return out


_STATUS_DONE = {"verified", "official_verified", "community_verified", "approved"}
_STATUS_CLOSED = _STATUS_DONE | {"rejected"}


@frappe.whitelist()
def approval_action(kind, name, action, note=None):
    """Real write action (login required — no guest write, matching every
    other create_*/act() endpoint in the app). action in
    {approve, reject, request_revision, escalate}.
    """
    actor = rn_actor()
    if not (is_system_manager() or getattr(actor, "role", None) in VERIFY_ROLES):
        frappe.throw("Hak verifikasi diperlukan", frappe.PermissionError)

    if action not in ("approve", "reject", "request_revision", "escalate"):
        frappe.throw("Aksi tidak dikenal")

    if kind == "evidence":
        doctype = "RN Operational Evidence"
    elif kind in _KIND_CONFIG:
        doctype = _KIND_CONFIG[kind]["doctype"]
    else:
        frappe.throw("Kind tidak dikenal")

    doc = frappe.get_doc(doctype, name)
    status_field = "role_request_status" if kind == "user" else "verification_status"

    new_status = {
        "approve": "approved" if kind == "user" else (
            "verified" if kind in ("needs", "expense", "evidence") else "official_verified"
        ),
        "reject": "rejected",
        "request_revision": "needs_correction",
        "escalate": "escalated",
    }[action]

    setattr(doc, status_field, new_status)

    if action == "approve" and kind == "user" and getattr(doc, "requested_role", None):
        doc.role = doc.requested_role
        if hasattr(doc, "status"):
            doc.status = "active"

    if action == "escalate" and hasattr(doc, "urgency"):
        doc.urgency = "critical"
    if action == "escalate" and hasattr(doc, "priority"):
        doc.priority = "critical"

    doc.save(ignore_permissions=True)

    return {
        "kind": kind, "name": name, "action": action,
        "status": new_status,
    }
