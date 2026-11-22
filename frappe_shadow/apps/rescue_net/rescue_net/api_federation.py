"""Federation transport endpoints, independent from offline app synchronization."""

import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlsplit

import frappe

from rescue_net.access_policy import is_system_manager
from rescue_net.federation import inbound, outbox, policy

WINDOW = 300
MAX_LIMIT = 200
DOMAINS = {"pull": b"RN-FEDERATION/1 pull", "push": b"RN-FEDERATION/1 push"}
EVENT_FIELDS = (
    "event_id", "origin_server_id", "seq", "object_type", "object_uid", "operation", "actor_ref",
    "occurred_at", "payload", "payload_checksum", "classification", "schema_version",
)
NODE_FIELDS = ("server_id", "node_name", "url", "status", "key_fingerprint", "send_cursor", "receive_cursor", "scope",
               "organization")
HEX_256 = re.compile(r"[0-9a-f]{64}")


def _manager():
    if not is_system_manager():
        frappe.throw("Hanya System Manager yang dapat mengelola federasi.", frappe.PermissionError)


def _denied():
    frappe.throw("Permintaan federasi ditolak.", frappe.PermissionError)


def _scope(value):
    value = frappe.parse_json(value)
    if (not isinstance(value, list) or not value or
            any(not isinstance(item, str) or item not in policy.POLICIES for item in value)):
        frappe.throw("Scope harus berisi DocType yang diizinkan federasi.")
    return sorted(set(value))


def _peer(server_id):
    server_id = policy.uid(server_id)
    if not server_id:
        return None
    matches = frappe.db.sql(
        """SELECT name FROM `tabRN Federation Node` WHERE name=%s FOR UPDATE""", server_id,
    )
    return frappe.get_doc(outbox.NODE, matches[0][0], for_update=True) if matches else None


@frappe.whitelist(allow_guest=True, methods=["GET"])
def node_info():
    settings = frappe.get_single(outbox.SETTINGS)
    if not settings.server_id:
        frappe.throw("Identitas node belum tersedia.")
    return {"server_id": settings.server_id, "name": frappe.conf.get("federation_node_name") or settings.node_name,
            "schema_version": outbox.SCHEMA_VERSION,
            "fingerprint": outbox.secret_digest(outbox.local_secret())}


@frappe.whitelist(methods=["GET"])
def status():
    _manager()
    peers = frappe.get_all(outbox.NODE, fields=NODE_FIELDS, order_by="node_name asc")
    for peer in peers:
        peer["scope"] = json.loads(peer["scope"])
        if peer.organization:
            peer.operation_template = frappe.db.get_value("RN Organization", peer.organization, "operation_template") or "umum"
    return {"node": node_info(), "outbox_count": frappe.db.count(outbox.OUTBOX), "peer_count": len(peers),
            "last_seq": outbox.last_seq(), "peers": peers}


@frappe.whitelist(methods=["POST"])
def register_peer(server_id, name, url, key_fingerprint, shared_secret, scope, organization=None):
    _manager()
    server_id = policy.uid(server_id)
    if not server_id or server_id == outbox.local_id():
        frappe.throw("ID node peer harus UUID dan berbeda dari ID lokal.")
    if not isinstance(shared_secret, str) or not HEX_256.fullmatch(shared_secret):
        frappe.throw("Kunci peer harus 32 byte dalam format heksadesimal huruf kecil.")
    fingerprint = outbox.secret_digest(shared_secret)
    if not isinstance(key_fingerprint, str) or not hmac.compare_digest(fingerprint, key_fingerprint):
        frappe.throw("Fingerprint kunci peer berbeda.")
    try:
        endpoint = urlsplit(url)
        endpoint.port
    except (TypeError, ValueError):
        frappe.throw("URL peer tidak valid.")
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None
            or endpoint.query or endpoint.fragment or len(url) > 140):
        frappe.throw("URL peer harus HTTPS tanpa kredensial, query, atau fragmen.")
    if not isinstance(name, str) or not name.strip() or len(name) > 140:
        frappe.throw("Nama node tidak valid.")
    node = frappe.get_doc(doctype=outbox.NODE, server_id=server_id, node_name=name.strip(), url=url,
                          key_fingerprint=fingerprint, shared_secret=shared_secret, scope=outbox.encode(_scope(scope)),
                          status="pending", organization=organization)
    # Avoid putting the supplied secret into duplicate-insert error context.
    if _peer(server_id):
        frappe.throw("Node peer sudah terdaftar.")
    node.insert(ignore_permissions=True)
    return {"server_id": server_id, "status": node.status}


def _change_status(server_id, desired, organization=None):
    _manager()
    node = _peer(server_id)
    if not node:
        frappe.throw("Node peer tidak ditemukan.", frappe.DoesNotExistError)
    if node.status == "revoked" and desired != "revoked":
        frappe.throw("Node yang sudah dicabut tidak dapat disetujui kembali.")
    if organization and node.organization and organization != node.organization:
        frappe.throw("Organisasi yang terhubung tidak dapat diganti.")
    if organization:
        node.organization = organization
    node.status = desired
    node.save(ignore_permissions=True)
    return {"server_id": node.server_id, "status": desired}


@frappe.whitelist(methods=["POST"])
def approve_peer(server_id, organization=None):
    return _change_status(server_id, "approved", organization)


@frappe.whitelist(methods=["POST"])
def revoke_peer(server_id):
    return _change_status(server_id, "revoked")


@frappe.whitelist(methods=["POST"])
def rotate_peer_key(server_id, key_fingerprint, shared_secret):
    _manager()
    node = _peer(server_id)
    if not node or node.status == "revoked":
        _denied()
    if not isinstance(shared_secret, str) or not HEX_256.fullmatch(shared_secret):
        frappe.throw("Format kunci peer tidak valid.")
    fingerprint = outbox.secret_digest(shared_secret)
    if not isinstance(key_fingerprint, str) or not hmac.compare_digest(fingerprint, key_fingerprint):
        frappe.throw("Fingerprint kunci peer berbeda.")
    node.shared_secret = shared_secret
    node.key_fingerprint = fingerprint
    node.save(ignore_permissions=True)
    return {"server_id": node.server_id, "key_fingerprint": fingerprint}


def signing_bytes(receiver_id, peer_id, timestamp, nonce, body, method="pull"):
    return b"\n".join((DOMAINS[method], receiver_id.encode(), peer_id.encode(), timestamp.encode(), nonce.encode(), body))


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("Non-finite JSON number")


def _authenticate(body, headers, method="pull"):
    peer_id = headers.get("X-RN-Peer", "")
    timestamp = headers.get("X-RN-Timestamp", "")
    nonce = headers.get("X-RN-Nonce", "")
    signature = headers.get("X-RN-Signature", "")
    if (policy.uid(peer_id) != peer_id or not re.fullmatch(r"[0-9]{10}", timestamp)
            or not re.fullmatch(r"[a-f0-9]{32}", nonce) or not HEX_256.fullmatch(signature)
            or abs(time.time() - int(timestamp)) > WINDOW):
        _denied()
    node = _peer(peer_id)
    if not node or node.status != "approved" or not node.organization:
        _denied()
    key = bytes.fromhex(node.get_password("shared_secret"))
    expected = hmac.new(key, signing_bytes(outbox.local_id(), peer_id, timestamp, nonce, body, method), hashlib.sha256)
    if not hmac.compare_digest(expected.hexdigest(), signature):
        _denied()
    # Redis SET NX is atomic across workers. The lifetime covers future timestamps too.
    cache = frappe.cache()
    if not cache.set(cache.make_key(f"rn:federation:nonce:{peer_id}:{nonce}"), b"1", nx=True, ex=2 * WINDOW + 1):
        _denied()
    org = frappe.db.get_value("RN Organization", node.organization, ["privacy_mode", "operation_template"],
                              as_dict=True, for_update=True)
    if not org or org.privacy_mode != "closed":
        _denied()
    node.flags.federation_template = org.operation_template or "umum"
    return node


def _current_public(doctype, object_uid, origin):
    name = frappe.db.get_value(doctype, {"uid": object_uid, "origin_server_id": origin})
    return bool(name and policy.eligible(frappe.get_doc(doctype, name)))


def _can_send(row, payload, node):
    if row.object_type == inbound.RESPONSE:
        return row.recipient_peer == node.name
    registry = policy.POLICIES.get(row.object_type)
    if not registry or registry.classification != row.classification or row.classification != policy.FULL:
        return False
    if set(payload) - registry.fields.keys() or not _current_public(row.object_type, row.object_uid, row.origin_server_id):
        return False
    references = {"disaster_event": policy.EVENT, "posko": policy.POSKO, "target_posko": policy.POSKO,
                  "source_posko": policy.POSKO, "destination_posko": policy.POSKO}
    return all(_current_public(doctype, payload[field], row.origin_server_id)
               for field, doctype in references.items() if field in payload)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def pull(since_seq=0, limit=100):
    request = getattr(frappe.local, "request", None)
    if not request or request.mimetype != "application/json" or not (0 < (request.content_length or 0) <= 256):
        _denied()
    body = request.get_data()
    node = _authenticate(body, request.headers)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        frappe.throw("Body pull harus berupa objek JSON.")
    if (not isinstance(data, dict) or set(data) != {"since_seq", "limit"}
            or type(data["since_seq"]) is not int or type(data["limit"]) is not int):
        frappe.throw("Body pull harus memuat since_seq dan limit berupa bilangan bulat.")
    since_seq, limit = data["since_seq"], data["limit"]
    last_seq = outbox.last_seq()
    if not 0 <= since_seq <= last_seq or not 1 <= limit <= MAX_LIMIT:
        frappe.throw("Kursor atau batas pull di luar rentang.")

    rows = frappe.get_all(
        outbox.OUTBOX, fields=(*EVENT_FIELDS, "recipient_peer"), order_by="seq asc", limit_page_length=limit + 1,
        filters=[["origin_server_id", "=", outbox.local_id()], ["seq", ">", since_seq], ["seq", "<=", last_seq],
                 ["object_type", "in", [*_scope(node.scope), inbound.RESPONSE]]],
        or_filters=[["recipient_peer", "is", "not set"], ["recipient_peer", "=", node.name]],
    )
    more = len(rows) > limit
    scanned = rows[:limit]
    events = []
    for row in scanned:
        payload = json.loads(row["payload"])
        can_send = _can_send(row, payload, node)
        row.pop("recipient_peer", None)
        if can_send:
            row["payload"] = payload
            row["occurred_at"] = str(row["occurred_at"])
            events.append(row)
    if since_seq > int(node.send_cursor or 0):
        frappe.db.set_value(outbox.NODE, node.name, "send_cursor", since_seq)
    next_seq = scanned[-1].seq if more else last_seq
    return {"events": events, "next_seq": next_seq, "has_more": more, "schema_version": outbox.SCHEMA_VERSION}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def push(events=None):
    request = getattr(frappe.local, "request", None)
    if not request or request.mimetype != "application/json" or not (0 < (request.content_length or 0) <= 512 * 1024):
        _denied()
    body = request.get_data()
    node = _authenticate(body, request.headers, "push")
    try:
        data = json.loads(body.decode("utf-8"), object_pairs_hook=_json_object, parse_constant=_nonfinite)
    except (ValueError, RecursionError):
        frappe.throw("Body push harus berupa objek JSON.")
    if not isinstance(data, dict) or set(data) != {"events"} or not isinstance(data["events"], list):
        frappe.throw("Body push harus memuat daftar events.")
    if not 1 <= len(data["events"]) <= MAX_LIMIT:
        frappe.throw("Jumlah event di luar rentang 1–200.")
    results = [inbound.ingest_event(event, node) for event in data["events"]]
    cursor = int(node.receive_cursor or 0)
    for event, result in zip(data["events"], results):
        if result["status"] in ("accepted", "duplicate"):
            cursor = max(cursor, event["seq"])
    if cursor != int(node.receive_cursor or 0):
        frappe.db.set_value(outbox.NODE, node.name, "receive_cursor", cursor)
    return {"results": results, "receive_cursor": cursor, "schema_version": outbox.SCHEMA_VERSION}


@frappe.whitelist(methods=["GET"])
def inbox(organization, event_type=None):
    return {"events": inbound.listing(organization, event_type)}


@frappe.whitelist(methods=["POST"])
def respond_assistance(event_id, decision):
    return inbound.respond(event_id, decision)
