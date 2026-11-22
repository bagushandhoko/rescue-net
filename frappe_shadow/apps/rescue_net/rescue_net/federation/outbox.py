"""Transactional outbox writer and persistent local identity."""

import hashlib
import hmac
import json
import secrets
import uuid

import frappe
from frappe.utils import cint, now_datetime

from rescue_net.access_policy import is_system_manager
from rescue_net.federation.policy import AREA, POLICIES, eligible, project

SETTINGS = "RN Federation Settings"
OUTBOX = "RN Event Outbox"
NODE = "RN Federation Node"
SCHEMA_VERSION = 1


def new_id():
    return str(getattr(uuid, "uuid7", uuid.uuid4)())


def initialize():
    settings = frappe.get_single(SETTINGS)
    if not settings.server_id:
        settings.server_id = new_id()
        settings.node_name = "Rescue-Net"
        settings.local_secret = secrets.token_hex(32)
        settings.last_seq = 0
        settings.save(ignore_permissions=True)
        # Single tables do not necessarily store default zero values.
        frappe.db.set_single_value(SETTINGS, "last_seq", "0")


def local_id():
    return frappe.db.get_single_value(SETTINGS, "server_id")


def secret_digest(secret):
    return hashlib.sha256(bytes.fromhex(secret)).hexdigest()


def local_secret():
    return frappe.get_single(SETTINGS).get_password("local_secret")


def before_validate(doc, method=None):
    if doc.doctype not in POLICIES:
        return
    before = doc.get_doc_before_save()
    if doc.doctype != AREA and not is_system_manager():
        doc.federation_share = cint(before.get("federation_share")) if before else 0
    doc.uid = (before.uid if before else None) or new_id()
    doc.origin_server_id = (before.origin_server_id if before else None) or local_id()


def encode(payload):
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def last_seq():
    return int(frappe.db.get_single_value(SETTINGS, "last_seq", cache=False) or 0)


def reserve(count):
    rows = frappe.db.sql(
        "SELECT value FROM tabSingles WHERE doctype=%s AND field='last_seq' FOR UPDATE", SETTINGS,
    )
    if len(rows) != 1:
        frappe.throw("Kursor federasi lokal belum siap.")
    previous = int(rows[0][0] or 0)
    frappe.db.sql(
        "UPDATE tabSingles SET value=%s WHERE doctype=%s AND field='last_seq'",
        (str(previous + count), SETTINGS),
    )
    return previous + 1


def actor_reference():
    actor_seed = (frappe.session.user or "Guest").encode()
    return hmac.new(bytes.fromhex(local_secret()), b"rn-actor-v1\0" + actor_seed, "sha256").hexdigest()


def write_events(changes):
    if not changes:
        return
    origin = local_id()
    actor = actor_reference()
    seq = reserve(len(changes))
    now = now_datetime()
    fields = ("name", "creation", "modified", "owner", "modified_by", "event_id", "origin_server_id", "seq",
              "object_type", "object_uid", "operation", "actor_ref", "occurred_at", "payload",
              "payload_checksum", "classification", "schema_version")

    def rows():
        for offset, (doc, operation, payload) in enumerate(changes):
            event_id = new_id()
            body = encode(payload)
            yield (event_id, now, now, "Administrator", "Administrator", event_id, origin, seq + offset,
                   doc.doctype, doc.uid, operation, actor, now, body, hashlib.sha256(body.encode()).hexdigest(),
                   POLICIES[doc.doctype].classification, SCHEMA_VERSION)

    frappe.db.bulk_insert(OUTBOX, fields, rows())


def record(doc, method=None):
    before = doc.get_doc_before_save()
    if method == "on_update" and not before:
        return
    record_change(doc, before)


def record_change(doc, before):
    if doc.doctype not in POLICIES or not doc.uid or doc.origin_server_id != local_id() or not eligible(doc):
        return
    payload = project(doc)
    was_eligible = before and eligible(before)
    previous = project(before) if was_eligible else {}
    if not payload or (was_eligible and previous == payload):
        return
    operation = "update" if was_eligible else "create"
    status = POLICIES[doc.doctype].status_field
    if operation == "update" and status and previous.get(status) != payload.get(status):
        operation = "status"
    write_events([(doc, operation, payload)])


def update_fields(doctype, name, values, **kwargs):
    """Mirror the outbox hook for existing status cascades that must bypass controllers."""
    if doctype not in POLICIES or not POLICIES[doctype].fields.keys() & values.keys():
        return frappe.db.set_value(doctype, name, values, **kwargs)
    before = frappe.db.get_value(doctype, name, "*", as_dict=True, for_update=True)
    if not before:
        return frappe.db.set_value(doctype, name, values, **kwargs)
    before.doctype = doctype
    result = frappe.db.set_value(doctype, name, values, **kwargs)
    doc = frappe.get_doc(doctype, name)
    record_change(doc, before)
    return result
