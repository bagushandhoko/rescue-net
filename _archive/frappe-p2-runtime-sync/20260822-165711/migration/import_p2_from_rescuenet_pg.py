import hashlib
import json
from decimal import Decimal

import frappe

from rescue_net.migration.import_from_rescuenet_pg import get_rescuenet_pg_dsn


P2_TABLES = {
    "RN User Account": ["user_accounts"],
    "RN User Session": ["user_sessions"],
    "RN Device": ["devices"],
    "RN Verification Request": ["verification_requests"],
    "RN Verifier Profile": ["verifier_profiles"],
    "RN Verification Endorsement": ["verification_endorsements"],
    "RN Verification Action": ["verification_actions"],
    "RN Trusted Verification Request": ["trusted_verification_requests"],
}

SOURCE_COUNTS_SQL_P2 = {
    "user_accounts": "select count(*) from user_accounts",
    "user_sessions": "select count(*) from user_sessions",
    "devices": "select count(*) from devices",
    "verification_requests": "select count(*) from verification_requests",
    "verifier_profiles": "select count(*) from verifier_profiles",
    "verification_endorsements": "select count(*) from verification_endorsements",
    "verification_actions": "select count(*) from verification_actions",
    "trusted_verification_requests": "select count(*) from trusted_verification_requests",
}

# Fields that must never be copied into the shadow app in cleartext, per table.
# session_token is a live bearer credential (not a one-way hash like edit_code_hash
# or token_hash), so only a non-reversible fingerprint is kept for correlation.
SECRET_FIELDS = {
    "user_sessions": ["session_token"],
}


def shadow_status_p2():
    return {
        "mode": "shadow-only",
        "source": "rescue-net FastAPI/PostgreSQL",
        "target_app": "rescue_net",
        "p2_doctypes": list(P2_TABLES),
        "has_pg_dsn": bool(get_rescuenet_pg_dsn()),
    }


def compare_doctype_counts_p2():
    result = {}
    for doctype in P2_TABLES:
        if frappe.db.exists("DocType", doctype):
            result[doctype] = frappe.db.count(doctype)
        else:
            result[doctype] = None
    return result


def source_counts_p2():
    import psycopg2
    import psycopg2.extras

    with psycopg2.connect(get_rescuenet_pg_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            counts = {}
            for table, sql in SOURCE_COUNTS_SQL_P2.items():
                cur.execute(sql)
                counts[table] = cur.fetchone()["count"]
            return counts


def import_from_pg_p2(dry_run=True, limit=None):
    import psycopg2
    import psycopg2.extras

    dry_run = _as_bool(dry_run)
    limit = int(limit) if limit else None
    summary = {"dry_run": dry_run, "tables": {}, "target_counts_before": compare_doctype_counts_p2()}

    with psycopg2.connect(get_rescuenet_pg_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _import_table(cur, summary, "user_accounts", "RN User Account", _map_user_account, dry_run, limit)
            _import_table(cur, summary, "user_sessions", "RN User Session", _map_user_session, dry_run, limit)
            _import_table(cur, summary, "devices", "RN Device", _map_device, dry_run, limit)
            _import_table(cur, summary, "verification_requests", "RN Verification Request", _map_verification_request, dry_run, limit)
            _import_table(cur, summary, "verifier_profiles", "RN Verifier Profile", _map_verifier_profile, dry_run, limit)
            _import_table(cur, summary, "verification_endorsements", "RN Verification Endorsement", _map_verification_endorsement, dry_run, limit)
            _import_table(cur, summary, "verification_actions", "RN Verification Action", _map_verification_action, dry_run, limit)
            _import_table(cur, summary, "trusted_verification_requests", "RN Trusted Verification Request", _map_trusted_verification_request, dry_run, limit)

    if not dry_run:
        frappe.db.commit()

    summary["target_counts_after"] = compare_doctype_counts_p2()
    return summary


def import_live_p2():
    return import_from_pg_p2(dry_run=False)


def _import_table(cur, summary, table, doctype, mapper, dry_run, limit):
    sql = f"select * from {table} order by created_at nulls last, id"
    if limit:
        sql += " limit %s"
        cur.execute(sql, (limit,))
    else:
        cur.execute(sql)

    rows = cur.fetchall()
    table_summary = {"source_rows": len(rows), "inserted": 0, "updated": 0, "skipped": 0}
    for row in rows:
        doc = mapper(row)
        if dry_run:
            table_summary["skipped"] += 1
            continue
        action = _upsert_doc(doctype, doc)
        table_summary[action] += 1
    summary["tables"][table] = table_summary


def _upsert_doc(doctype, fields):
    legacy_id = fields["legacy_id"]
    existing = frappe.db.exists(doctype, {"legacy_id": legacy_id})
    if existing:
        doc = frappe.get_doc(doctype, existing)
        action = "updated"
    else:
        doc = frappe.new_doc(doctype)
        action = "inserted"

    for key, value in fields.items():
        if key in doc.meta.get_valid_columns():
            doc.set(key, value)

    doc.flags.ignore_permissions = True
    doc.save()
    return action


def _common(row, source_table):
    redacted_row = _redact(row, source_table)
    return {
        "legacy_id": f"{source_table}:{row['id']}",
        "legacy_source": source_table,
        "migration_status": "Shadow Imported",
        "legacy_payload": _to_json(redacted_row),
    }


def _redact(row, source_table):
    secret_fields = SECRET_FIELDS.get(source_table, [])
    if not secret_fields:
        return row
    redacted = dict(row)
    for field in secret_fields:
        if redacted.get(field):
            redacted[field] = "[REDACTED - see *_fingerprint field]"
    return redacted


def _fingerprint(value):
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _map_user_account(row):
    data = _common(row, "user_accounts")
    data.update(
        {
            "title": row.get("display_name") or row["id"],
            "username": row.get("username"),
            "phone": row.get("phone"),
            "email": row.get("email"),
            "role": row.get("role"),
            "organization_legacy_id": _legacy_ref("organizations", row.get("organization_id")),
            "posko_legacy_id": _legacy_ref("posko_nodes", row.get("posko_id")),
            "status": row.get("status"),
        }
    )
    return data


def _map_user_session(row):
    data = _common(row, "user_sessions")
    data.update(
        {
            "title": f"session:{row['id']}",
            "user_legacy_id": _legacy_ref("user_accounts", row.get("user_id")),
            "status": row.get("status"),
            "session_token_fingerprint": _fingerprint(row.get("session_token")),
            "expires_at": row.get("expires_at"),
        }
    )
    return data


def _map_device(row):
    data = _common(row, "devices")
    data.update(
        {
            "title": row.get("device_name") or row["id"],
            "device_type": row.get("device_type"),
            "owner_user_legacy_id": _legacy_ref("user_accounts", row.get("owner_user_id")),
            "owner_organization_legacy_id": _legacy_ref("organizations", row.get("owner_organization_id")),
            "last_seen_at": row.get("last_seen_at"),
            "public_key": row.get("public_key"),
            "status": row.get("status"),
        }
    )
    return data


def _map_verification_request(row):
    data = _common(row, "verification_requests")
    data.update(
        {
            "title": f"{row.get('object_type') or 'object'}:{row.get('object_id') or row['id']}",
            "object_type": row.get("object_type"),
            "object_id": row.get("object_id"),
            "requested_by": row.get("requested_by"),
            "status": row.get("status"),
            "notes": row.get("notes"),
        }
    )
    return data


def _map_verifier_profile(row):
    data = _common(row, "verifier_profiles")
    data.update(
        {
            "title": row.get("display_name") or row["id"],
            "user_legacy_id": _legacy_ref("user_accounts", row.get("user_id")),
            "verifier_type": row.get("verifier_type"),
            "organization_legacy_id": _legacy_ref("organizations", row.get("organization_id")),
            "position_title": row.get("position_title"),
            "public_role_description": row.get("public_role_description"),
            "phone": row.get("phone"),
            "email": row.get("email"),
            "identity_verification_status": row.get("identity_verification_status"),
            "verifier_status": row.get("verifier_status"),
            "trust_level": row.get("trust_level"),
            "allowed_verification_scope_json": _to_json(row.get("allowed_verification_scope_json")),
            "suspicious_activity_count": row.get("suspicious_activity_count"),
            "approved_by": row.get("approved_by"),
            "approved_at": row.get("approved_at"),
            "notes": row.get("notes"),
        }
    )
    return data


def _map_verification_endorsement(row):
    data = _common(row, "verification_endorsements")
    data.update(
        {
            "title": f"{row.get('verifier_display_name') or 'verifier'} -> {row.get('target_type') or ''}:{row.get('target_id') or row['id']}",
            "request_legacy_id": _legacy_ref("trusted_verification_requests", row.get("request_id")),
            "target_type": row.get("target_type"),
            "target_id": row.get("target_id"),
            "verifier_legacy_id": _legacy_ref("verifier_profiles", row.get("verifier_id")),
            "verifier_display_name": row.get("verifier_display_name"),
            "verifier_role": row.get("verifier_role"),
            "verification_scope": row.get("verification_scope"),
            "verification_level": row.get("verification_level"),
            "statement": row.get("statement"),
            "status": row.get("status"),
            "visible_on_profile": row.get("visible_on_profile"),
            "verified_at": row.get("verified_at"),
            "expires_at": row.get("expires_at"),
            "revoked_at": row.get("revoked_at"),
            "revoked_by": row.get("revoked_by"),
            "revoke_reason": row.get("revoke_reason"),
        }
    )
    return data


def _map_verification_action(row):
    data = _common(row, "verification_actions")
    data.update(
        {
            "title": f"{row.get('action_type') or 'action'} - {row.get('object_type') or ''}:{row.get('object_id') or row['id']}",
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "object_type": row.get("object_type"),
            "object_id": row.get("object_id"),
            "action_type": row.get("action_type"),
            "verification_status": row.get("verification_status"),
            "trust_level": row.get("trust_level"),
            "reviewed_by": row.get("reviewed_by"),
            "reviewer_role": row.get("reviewer_role"),
            "review_notes": row.get("review_notes"),
        }
    )
    return data


def _map_trusted_verification_request(row):
    data = _common(row, "trusted_verification_requests")
    data.update(
        {
            "title": row.get("relationship_description") or row["id"],
            "requester_type": row.get("requester_type"),
            "requester_id": row.get("requester_id"),
            "target_type": row.get("target_type"),
            "target_id": row.get("target_id"),
            "requested_verifier_legacy_id": _legacy_ref("verifier_profiles", row.get("requested_verifier_id")),
            "requested_verifier_name": row.get("requested_verifier_name"),
            "requested_verifier_phone": row.get("requested_verifier_phone"),
            "requested_verifier_email": row.get("requested_verifier_email"),
            "relationship_description": row.get("relationship_description"),
            "verification_scope": row.get("verification_scope"),
            "message": row.get("message"),
            "status": row.get("status"),
            # token_hash is already a one-way hash at the source (same pattern as
            # aid_offers.edit_code_hash) - safe to carry over as-is.
            "token_hash": row.get("token_hash"),
            "expires_at": row.get("expires_at"),
            "decided_at": row.get("decided_at"),
            "correction_note": row.get("correction_note"),
        }
    )
    return data


def _legacy_ref(table, value):
    return f"{table}:{value}" if value else None


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() not in {"0", "false", "no"}


def _to_json(row):
    return json.dumps(row, default=_json_default, ensure_ascii=False, sort_keys=True)


def _json_default(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
