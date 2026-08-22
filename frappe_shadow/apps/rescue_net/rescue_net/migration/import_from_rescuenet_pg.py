import json
import os
from decimal import Decimal

import frappe


P0_TABLES = {
    "RN Disaster Event": ["disaster_events"],
    "RN Organization": ["organizations"],
    "RN Posko": ["posko_nodes"],
    "RN Logistic Need": ["logistic_needs", "consolidated_needs"],
    "RN Aid Offer": ["aid_offers"],
    "RN Distribution Flow": ["distribution_flows"],
    "RN War Room Snapshot": [],
}

# Phase 2 (FRAPPE_MIGRATION_MAP.md import order items 9-11). DocTypes already
# scaffolded; only the import mapping was missing. Community Report has no
# DocType yet, so it is not listed here until that scaffolding exists.
P1_TABLES = {
    "RN Volunteer": ["volunteers"],
    "RN Evidence File": ["evidence_files"],
    "RN Trusted Verification Request": ["trusted_verification_requests"],
    "RN Community Report": ["community_reports"],
}

SOURCE_COUNTS_SQL = {
    "disaster_events": "select count(*) from disaster_events",
    "organizations": "select count(*) from organizations",
    "posko_nodes": "select count(*) from posko_nodes",
    "logistic_needs": "select count(*) from logistic_needs",
    "consolidated_needs": "select count(*) from consolidated_needs",
    "aid_offers": "select count(*) from aid_offers",
    "distribution_flows": "select count(*) from distribution_flows",
    "stock_opnames": "select count(*) from stock_opnames",
    "evacuee_registrations": "select count(*) from evacuee_registrations",
    "donation_tenders": "select count(*) from donation_tenders",
    "donation_bids": "select count(*) from donation_bids",
    "action_plans": "select count(*) from action_plans",
    "action_plan_updates": "select count(*) from action_plan_updates",
    "volunteers": "select count(*) from volunteers",
    "evidence_files": "select count(*) from evidence_files",
    "trusted_verification_requests": "select count(*) from trusted_verification_requests",
    "community_reports": "select count(*) from community_reports",
}


def get_rescuenet_pg_dsn():
    return (
        os.environ.get("RESCUENET_PG_DSN")
        or os.environ.get("DATABASE_URL")
        or "dbname=rescuenet_db user=postgres password=postgres_master_password_ganti_nanti host=postgres-main port=5432"
    )


def shadow_status():
    return {
        "mode": "shadow-only",
        "source": "rescue-net FastAPI/PostgreSQL",
        "target_app": "rescue_net",
        "p0_doctypes": list(P0_TABLES),
        "p1_doctypes": list(P1_TABLES),
        "has_pg_dsn": bool(get_rescuenet_pg_dsn()),
    }


def compare_doctype_counts():
    result = {}
    for doctype in list(P0_TABLES) + list(P1_TABLES):
        if frappe.db.exists("DocType", doctype):
            result[doctype] = frappe.db.count(doctype)
        else:
            result[doctype] = None
    return result


def source_counts():
    import psycopg2
    import psycopg2.extras

    with psycopg2.connect(get_rescuenet_pg_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            counts = {}
            for table, sql in SOURCE_COUNTS_SQL.items():
                cur.execute(sql)
                counts[table] = cur.fetchone()["count"]
            return counts


def import_from_pg(dry_run=True, limit=None):
    import psycopg2
    import psycopg2.extras

    dry_run = _as_bool(dry_run)
    limit = int(limit) if limit else None
    summary = {"dry_run": dry_run, "tables": {}, "target_counts_before": compare_doctype_counts()}

    with psycopg2.connect(get_rescuenet_pg_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _import_table(cur, summary, "disaster_events", "RN Disaster Event", _map_disaster_event, dry_run, limit)
            _import_table(cur, summary, "organizations", "RN Organization", _map_organization, dry_run, limit)
            _import_table(cur, summary, "posko_nodes", "RN Posko", _map_posko, dry_run, limit)
            _import_table(cur, summary, "logistic_needs", "RN Logistic Need", _map_logistic_need, dry_run, limit)
            _import_table(cur, summary, "consolidated_needs", "RN Logistic Need", _map_consolidated_need, dry_run, limit)
            _import_table(cur, summary, "aid_offers", "RN Aid Offer", _map_aid_offer, dry_run, limit)
            _import_table(cur, summary, "distribution_flows", "RN Distribution Flow", _map_distribution_flow, dry_run, limit)
            _import_table(cur, summary, "volunteers", "RN Volunteer", _map_volunteer, dry_run, limit)
            _import_table(cur, summary, "evidence_files", "RN Evidence File", _map_evidence_file, dry_run, limit)
            _import_table(cur, summary, "trusted_verification_requests", "RN Trusted Verification Request", _map_trusted_verification_request, dry_run, limit)
            _import_table(cur, summary, "community_reports", "RN Community Report", _map_community_report, dry_run, limit)

    if not dry_run:
        frappe.db.commit()

    summary["target_counts_after"] = compare_doctype_counts()
    return summary


def import_live():
    return import_from_pg(dry_run=False)


def import_community_reports(dry_run=True, limit=None):
    import psycopg2
    import psycopg2.extras

    dry_run = _as_bool(dry_run)
    limit = int(limit) if limit else None

    summary = {
        "dry_run": dry_run,
        "tables": {},
        "target_count_before": (
            frappe.db.count("RN Community Report")
            if frappe.db.exists("DocType", "RN Community Report")
            else None
        ),
    }

    with psycopg2.connect(get_rescuenet_pg_dsn()) as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            _import_table(
                cur,
                summary,
                "community_reports",
                "RN Community Report",
                _map_community_report,
                dry_run,
                limit,
            )

    if not dry_run:
        frappe.db.commit()

    summary["target_count_after"] = (
        frappe.db.count("RN Community Report")
        if frappe.db.exists("DocType", "RN Community Report")
        else None
    )

    return summary


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
    return {
        "legacy_id": f"{source_table}:{row['id']}",
        "legacy_source": source_table,
        "migration_status": "Shadow Imported",
        "legacy_payload": _to_json(row),
    }


def _map_disaster_event(row):
    data = _common(row, "disaster_events")
    data.update(
        {
            "title": row.get("name") or row["id"],
            "event_status": row.get("status"),
            "severity": row.get("severity"),
            "location_summary": row.get("location"),
            "started_at": row.get("created_at"),
        }
    )
    return data


def _map_organization(row):
    data = _common(row, "organizations")
    data.update(
        {
            "title": row.get("name") or row["id"],
            "organization_type": row.get("organization_type"),
            "verification_status": row.get("identity_verification_status") or row.get("trust_level"),
            "contact_summary": row.get("contact_person") or row.get("notes"),
        }
    )
    return data


def _map_posko(row):
    data = _common(row, "posko_nodes")
    data.update(
        {
            "title": row.get("name") or row["id"],
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "organization_legacy_id": _legacy_ref("organizations", row.get("organization_id")),
            "posko_type": row.get("node_type"),
            "address": row.get("location"),
            "operational_status": row.get("operational_status"),
            "verification_status": row.get("verification_status"),
            "latitude": row.get("lat"),
            "longitude": row.get("lng"),
        }
    )
    return data


def _map_logistic_need(row):
    data = _common(row, "logistic_needs")
    data.update(
        {
            "title": row.get("item_name") or row["id"],
            "item_name": row.get("item_name") or row["id"],
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "posko_legacy_id": _legacy_ref("posko_nodes", row.get("node_id")),
            "quantity": row.get("quantity_needed"),
            "unit": row.get("unit"),
            "urgency": row.get("priority"),
            "need_status": row.get("status"),
            "source_table": "logistic_needs",
        }
    )
    return data


def _map_consolidated_need(row):
    data = _common(row, "consolidated_needs")
    data.update(
        {
            "title": row.get("item_name") or row["id"],
            "item_name": row.get("item_name") or row["id"],
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "posko_legacy_id": _legacy_ref("posko_nodes", row.get("canonical_posko_id")),
            "quantity": row.get("quantity_final"),
            "unit": row.get("quantity_unit"),
            "urgency": row.get("confidence_level"),
            "need_status": row.get("status"),
            "source_table": "consolidated_needs",
        }
    )
    return data


def _map_aid_offer(row):
    data = _common(row, "aid_offers")
    data.update(
        {
            "title": f"{row.get('donor_name') or row['id']} - {row.get('item_name') or 'Aid Offer'}",
            "donor_name": row.get("donor_name") or row["id"],
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "target_posko_legacy_id": _legacy_ref("posko_nodes", row.get("target_node_id")),
            "item_name": row.get("item_name"),
            "quantity": row.get("quantity"),
            "unit": row.get("unit"),
            "pickup_location": row.get("pickup_location"),
            "offer_status": row.get("status"),
            "donor_contact": row.get("donor_contact"),
            "notes": row.get("notes"),
        }
    )
    return data


def _map_distribution_flow(row):
    data = _common(row, "distribution_flows")
    data.update(
        {
            "title": row["id"],
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "need_legacy_id": _legacy_ref("logistic_needs", row.get("need_id")),
            "aid_offer_legacy_id": _legacy_ref("aid_offers", row.get("aid_offer_id")),
            "destination_posko_legacy_id": _legacy_ref("posko_nodes", row.get("destination_node_id")),
            "eta_final": row.get("eta_final"),
            "flow_status": row.get("status"),
        }
    )
    return data


def _map_volunteer(row):
    data = _common(row, "volunteers")
    data.update(
        {
            "title": row.get("name") or row["id"],
            "phone": row.get("phone"),
            "email": row.get("email"),
            "main_skill": row.get("main_skill"),
            "location": row.get("location"),
            "availability": row.get("availability"),
            "duration_available": row.get("duration_available"),
            "verification_status": row.get("verification_status"),
        }
    )
    return data


def _map_evidence_file(row):
    data = _common(row, "evidence_files")
    data.update(
        {
            "title": row.get("filename") or row["id"],
            "disaster_event_legacy_id": _legacy_ref("disaster_events", row.get("disaster_event_id")),
            "posko_legacy_id": _legacy_ref("posko_nodes", row.get("node_id")),
            "linked_object_type": row.get("linked_object_type"),
            "linked_object_id": row.get("linked_object_id"),
            "evidence_type": row.get("evidence_type"),
            "filename": row.get("filename"),
            "file_path": row.get("file_path"),
            "mime_type": row.get("mime_type"),
            "size_bytes": row.get("size_bytes") or 0,
            "uploaded_by": row.get("uploaded_by"),
            "verification_status": row.get("verification_status"),
        }
    )
    return data


def _map_trusted_verification_request(row):
    data = _common(row, "trusted_verification_requests")
    data.update(
        {
            "title": row.get("requested_verifier_name") or row["id"],
            "requester_type": row.get("requester_type"),
            "requester_id": row.get("requester_id"),
            "target_type": row.get("target_type"),
            "target_id": row.get("target_id"),
            "requested_verifier_legacy_id": _legacy_ref("organizations", row.get("requested_verifier_id")),
            "requested_verifier_name": row.get("requested_verifier_name"),
            "requested_verifier_phone": row.get("requested_verifier_phone"),
            "requested_verifier_email": row.get("requested_verifier_email"),
            "relationship_description": row.get("relationship_description"),
            "verification_scope": row.get("verification_scope"),
            "message": row.get("message"),
            "status": row.get("status"),
            "expires_at": row.get("expires_at"),
            "decided_at": row.get("decided_at"),
            "correction_note": row.get("correction_note"),
        }
    )
    return data



def _map_community_report(row):
    data = _common(row, "community_reports")
    data.update(
        {
            "title": row.get("title") or row["id"],
            "disaster_event": _legacy_ref(
                "disaster_events", row.get("disaster_event_id")
            ),
            "disaster_event_legacy_id": _legacy_ref(
                "disaster_events", row.get("disaster_event_id")
            ),
            "reporter_profile_legacy_id": _legacy_ref(
                "reporter_profiles", row.get("reporter_profile_id")
            ),
            "reporter_name": row.get("reporter_name"),
            "reporter_phone": row.get("reporter_phone"),
            "reporter_role": row.get("reporter_role"),
            "reporter_verification_level": row.get("reporter_verification_level"),
            "report_type": row.get("report_type"),
            "description": row.get("description"),
            "affected_people_count": row.get("affected_people_count") or 0,
            "priority": row.get("priority"),
            "urgent_needs": row.get("urgent_needs"),

            "location_text": row.get("location_text"),
            "has_coordinates": (
                1
                if row.get("lat") is not None and row.get("lng") is not None
                else 0
            ),
            "latitude": row.get("lat"),
            "longitude": row.get("lng"),
            "location_accuracy_meters": row.get("location_accuracy_meters"),
            "location_input_method": row.get("location_input_method"),
            "location_source": row.get("location_source"),
            "location_status": row.get("location_status"),

            "admin_area_id": row.get("admin_area_id"),
            "admin_level": row.get("admin_level"),
            "area_level": row.get("area_level"),
            "province_name": row.get("province_name"),
            "city_name": row.get("city_name"),
            "district_name": row.get("district_name"),
            "village_name": row.get("village_name"),
            "is_aggregate": 1 if row.get("is_aggregate") else 0,
            "consolidation_status": row.get("consolidation_status"),

            "status": row.get("status"),
            "trust_score": row.get("trust_score") or 0,
            "assigned_verifier_type": row.get("assigned_verifier_type"),
            "assigned_verifier_id": row.get("assigned_verifier_id"),
            "verified_by": row.get("verified_by"),
            "verified_at": row.get("verified_at"),

            "converted_object_type": row.get("converted_object_type"),
            "converted_object_id": row.get("converted_object_id"),
            "consent_to_contact": 1 if row.get("consent_to_contact") else 0,

            "legacy_created_at": row.get("created_at"),
            "legacy_updated_at": row.get("updated_at"),
            "legacy_deleted_at": row.get("deleted_at"),
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
    return json.dumps(dict(row), default=_json_default, ensure_ascii=False, sort_keys=True)


def _json_default(value):
    if isinstance(value, Decimal):
        # Whole-number NUMERIC columns (e.g. quantity_needed=150) must serialize
        # as int, matching the legacy FastAPI JSON output byte-for-byte.
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
