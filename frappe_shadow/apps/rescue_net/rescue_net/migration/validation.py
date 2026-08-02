import json
from datetime import datetime, timezone

import frappe

from rescue_net.migration.import_from_rescuenet_pg import source_counts


DOCTYPE_TABLE_MAP = {
    "RN Disaster Event": ["disaster_events"],
    "RN Organization": ["organizations"],
    "RN Posko": ["posko_nodes"],
    "RN Logistic Need": ["logistic_needs", "consolidated_needs"],
    "RN Aid Offer": ["aid_offers"],
    "RN Distribution Flow": ["distribution_flows"],
}

REFERENCE_CHECKS = {
    "RN Posko": [
        ("disaster_event_legacy_id", "RN Disaster Event"),
        ("organization_legacy_id", "RN Organization"),
    ],
    "RN Logistic Need": [
        ("disaster_event_legacy_id", "RN Disaster Event"),
        ("posko_legacy_id", "RN Posko"),
    ],
    "RN Aid Offer": [
        ("disaster_event_legacy_id", "RN Disaster Event"),
        ("target_posko_legacy_id", "RN Posko"),
    ],
    "RN Distribution Flow": [
        ("disaster_event_legacy_id", "RN Disaster Event"),
        ("need_legacy_id", "RN Logistic Need"),
        ("aid_offer_legacy_id", "RN Aid Offer"),
        ("destination_posko_legacy_id", "RN Posko"),
    ],
}


def build_validation_report():
    src_counts = source_counts()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "shadow-validation",
        "counts": _count_checks(src_counts),
        "duplicates": _duplicate_checks(),
        "missing_legacy_payload": _missing_payload_checks(),
        "orphan_references": _orphan_reference_checks(),
    }
    report["summary"] = _summary(report)
    return report


def build_validation_report_json():
    return json.dumps(build_validation_report(), ensure_ascii=False, indent=2, sort_keys=True)


def _count_checks(src_counts):
    checks = {}
    for doctype, tables in DOCTYPE_TABLE_MAP.items():
        source_total = sum(src_counts.get(table, 0) for table in tables)
        target_total = frappe.db.count(doctype)
        checks[doctype] = {
            "source_tables": tables,
            "source_count": source_total,
            "target_count": target_total,
            "status": "pass" if source_total == target_total else "fail",
        }
    return checks


def _duplicate_checks():
    checks = {}
    for doctype in DOCTYPE_TABLE_MAP:
        rows = frappe.db.sql(
            f"""
            select legacy_id, count(*) as count
            from `tab{doctype}`
            group by legacy_id
            having count(*) > 1
            """,
            as_dict=True,
        )
        checks[doctype] = {"duplicate_count": len(rows), "duplicates": rows[:20], "status": "pass" if not rows else "fail"}
    return checks


def _missing_payload_checks():
    checks = {}
    for doctype in DOCTYPE_TABLE_MAP:
        missing = frappe.db.count(doctype, {"legacy_payload": ["in", ["", None]]})
        checks[doctype] = {"missing_legacy_payload": missing, "status": "pass" if missing == 0 else "fail"}
    return checks


def _orphan_reference_checks():
    result = {}
    legacy_sets = {
        doctype: {
            row.legacy_id
            for row in frappe.get_all(doctype, fields=["legacy_id"], limit_page_length=0)
            if row.legacy_id
        }
        for doctype in DOCTYPE_TABLE_MAP
    }

    for doctype, checks in REFERENCE_CHECKS.items():
        rows = frappe.get_all(
            doctype,
            fields=["name", "legacy_id"] + [field for field, _target in checks],
            limit_page_length=0,
        )
        per_field = {}
        for field, target_doctype in checks:
            target_ids = legacy_sets[target_doctype]
            missing = []
            for row in rows:
                value = row.get(field)
                if value and value not in target_ids:
                    missing.append({"name": row.name, "legacy_id": row.legacy_id, field: value})
            per_field[field] = {
                "target_doctype": target_doctype,
                "orphan_count": len(missing),
                "orphans": missing[:20],
                "status": "pass" if not missing else "fail",
            }
        result[doctype] = per_field
    return result


def _summary(report):
    failures = []
    for section, checks in report.items():
        if section in {"generated_at", "mode", "summary"}:
            continue
        _collect_failures(section, checks, failures)
    return {
        "status": "pass" if not failures else "fail",
        "failure_count": len(failures),
        "failures": failures[:50],
    }


def _collect_failures(prefix, value, failures):
    if isinstance(value, dict):
        if value.get("status") == "fail":
            failures.append(prefix)
        for key, child in value.items():
            _collect_failures(f"{prefix}.{key}", child, failures)
