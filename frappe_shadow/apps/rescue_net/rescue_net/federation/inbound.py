"""Validated inbox and explicitly addressed assistance decisions."""

import hashlib
import hmac
import json

import frappe
from frappe.utils import now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor
from rescue_net.federation import outbox, policy

INBOX = "RN Federation Inbox"
RESPONSE = "assistance.response"
ORG = "RN Organization"
ENVELOPE = {"event_id", "seq", "event_type", "schema_version", "payload", "payload_checksum"}
VISIBLE_FIELDS = ("event_id", "organization", "destination", "event_type", "schema_version",
                  "payload", "status", "rejection_reason", "decision", "creation")


def can_review(organization):
    if not policy.organization_key(organization) or frappe.session.user in ("Guest", None):
        return False
    if is_system_manager():
        return True
    actor = rn_actor()
    return bool(actor and frappe.db.exists("RN Organization Membership", {
        "user_account": actor.name, "organization": organization,
        "membership_role": "owner", "status": "approved",
    }))


def require_review(organization):
    if not can_review(organization):
        frappe.throw("Anda tidak dapat mengakses kotak masuk organisasi ini.", frappe.PermissionError)


def _error(event, node):
    if set(event) != ENVELOPE:
        return "invalid_event_fields"
    if type(event["schema_version"]) is not int or event["schema_version"] != outbox.SCHEMA_VERSION:
        return "unsupported_schema"
    event_type = event["event_type"]
    if not isinstance(event_type, str) or len(event_type) > 40:
        return "event_type_denied"
    payload = event["payload"]
    reason = policy.inbound_error(event_type, payload, node.operation_template)
    if reason:
        return reason
    checksum = event["payload_checksum"]
    expected = hashlib.sha256(outbox.encode(payload).encode()).hexdigest()
    if not isinstance(checksum, str) or not hmac.compare_digest(expected.encode(), checksum.encode("utf-8", "surrogatepass")):
        return "checksum_mismatch"
    if event_type == "assistance.request" and not frappe.db.exists(ORG, payload["destination"]):
        return "destination_unknown"
    return None


def _existing(event_id, node, event, existing):
    if existing.peer != node.name:
        return {"event_id": event_id, "status": "rejected", "reason": "event_id_conflict"}
    if existing.status == "rejected":
        return {"event_id": event_id, "status": "rejected", "reason": existing.rejection_reason}
    try:
        body = outbox.encode(event.get("payload"))
    except (ValueError, RecursionError):
        body = None
    if (set(event) != ENVELOPE or existing.source_seq != event.get("seq")
            or existing.event_type != event.get("event_type") or type(event.get("schema_version")) is not int
            or existing.schema_version != event.get("schema_version")
            or existing.payload_checksum != event.get("payload_checksum") or existing.payload != body):
        return {"event_id": event_id, "status": "rejected", "reason": "event_id_conflict"}
    return {"event_id": event_id, "status": "duplicate"}


def ingest_event(event, node):
    event_id = event.get("event_id") if isinstance(event, dict) else None
    seq = event.get("seq") if isinstance(event, dict) else None
    canonical_id = policy.uid(event_id)
    if not canonical_id or event_id != canonical_id or type(seq) is not int or not 0 < seq <= 2**63 - 1:
        return {"event_id": canonical_id, "status": "rejected", "reason": "invalid_event_identity"}

    existing = frappe.db.get_value(INBOX, event_id, "*", as_dict=True)
    if existing:
        return _existing(event_id, node, event, existing)
    reason = _error(event, node)
    values = dict(name=event_id, event_id=event_id, source_seq=seq, peer=node.name, organization=node.organization)
    if reason:
        kind, version = event.get("event_type"), event.get("schema_version")
        values.update(status="rejected", rejection_reason=reason,
                      event_type=kind if isinstance(kind, str) and kind in policy.INBOUND else None,
                      schema_version=version if type(version) is int and 0 < version < 2**31 else None)
    else:
        kind, payload = event["event_type"], event["payload"]
        values.update(event_type=kind, schema_version=event["schema_version"], payload=outbox.encode(payload),
                      payload_checksum=event["payload_checksum"], destination=payload.get("destination"),
                      status="applied" if kind == "org.summary" else "received")
    # Direct insert avoids Frappe HTML rewriting signed payloads and records the
    # original verified JSON. A savepoint isolates a concurrent UUID collision.
    frappe.db.savepoint("federation_event")
    try:
        frappe.get_doc(doctype=INBOX, **values).db_insert()
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point="federation_event")
        existing = frappe.db.get_value(INBOX, event_id, "*", as_dict=True, for_update=True)
        if not existing:
            raise
        return _existing(event_id, node, event, existing)
    if reason:
        return {"event_id": event_id, "status": "rejected", "reason": reason}
    return {"event_id": event_id, "status": "accepted"}


def listing(organization, event_type=None):
    require_review(organization)
    if event_type is not None and (not isinstance(event_type, str) or event_type not in policy.INBOUND):
        frappe.throw("Jenis event kotak masuk tidak valid.")
    filters = {"event_type": event_type} if event_type else {}
    rows = frappe.get_all(INBOX, filters=filters, or_filters={"organization": organization, "destination": organization},
                          fields=VISIBLE_FIELDS, order_by="creation desc, name desc", limit_page_length=100)
    for row in rows:
        row.payload = json.loads(row.payload) if row.payload else None
    return rows


def latest_summary(organization):
    if not can_review(organization) or frappe.db.get_value(ORG, organization, "privacy_mode") != "closed":
        return None
    peer = frappe.db.get_value(outbox.NODE, {"active_organization": organization, "status": "approved"})
    if not peer:
        return None
    row = frappe.db.get_value(INBOX, {"peer": peer, "event_type": "org.summary", "status": "applied"},
                              ["payload", "creation"], order_by="source_seq desc, creation desc", as_dict=True)
    return {"counts": json.loads(row.payload), "received_at": row.creation} if row else None


def respond(event_id, decision):
    if decision not in ("accept", "decline"):
        frappe.throw("Keputusan harus accept atau decline.")
    if not isinstance(event_id, str) or policy.uid(event_id) != event_id:
        frappe.throw("ID permintaan bantuan tidak valid.")
    row = frappe.db.get_value(INBOX, event_id, "*", as_dict=True, for_update=True)
    if not row or row.event_type != "assistance.request":
        frappe.throw("Permintaan bantuan tidak ditemukan.", frappe.DoesNotExistError)
    require_review(row.destination)
    if row.decision and row.decision != decision:
        frappe.throw("Permintaan bantuan sudah diputuskan.")
    if not row.decision:
        payload = outbox.encode({"request_event_id": row.event_id, "decision": decision})
        response_id = outbox.new_id()
        frappe.get_doc(doctype=outbox.OUTBOX, name=response_id, event_id=response_id,
                       origin_server_id=outbox.local_id(), seq=outbox.reserve(1), object_type=RESPONSE,
                       object_uid=row.event_id, operation="status", actor_ref=outbox.actor_reference(), occurred_at=now_datetime(),
                       payload=payload, payload_checksum=hashlib.sha256(payload.encode()).hexdigest(),
                       classification=policy.FULL, schema_version=outbox.SCHEMA_VERSION,
                       recipient_peer=row.peer).db_insert()
        frappe.db.set_value(INBOX, row.name, {"decision": decision, "status": "applied"})
    return {"event_id": row.event_id, "decision": decision}
