import json
from datetime import datetime, timezone

import frappe

from rescue_net.migration.import_p2_from_rescuenet_pg import source_counts_p2
from rescue_net.migration.link_backfill import LINK_RULES


DOCTYPE_TABLE_MAP_P2 = {
    "RN User Account": ["user_accounts"],
    "RN User Session": ["user_sessions"],
    "RN Device": ["devices"],
    "RN Verification Request": ["verification_requests"],
    "RN Verifier Profile": ["verifier_profiles"],
    "RN Verification Endorsement": ["verification_endorsements"],
    "RN Verification Action": ["verification_actions"],
    "RN Trusted Verification Request": ["trusted_verification_requests"],
}

LINK_COVERAGE_CHECKS_P2 = {
    doctype: rules for doctype, rules in LINK_RULES.items() if doctype in DOCTYPE_TABLE_MAP_P2
}

SECRET_FIELDS_P2 = {
    "RN User Session": ["session_token"],
}


def build_validation_report_p2():
    src_counts = source_counts_p2()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "shadow-validation-p2",
        "counts": _count_checks(src_counts),
        "duplicates": _duplicate_checks(),
        "missing_legacy_payload": _missing_payload_checks(),
        "link_coverage": _link_coverage_checks(),
        "secret_leak_scan": _secret_leak_checks(),
    }
    report["summary"] = _summary(report)
    return report


def build_validation_report_p2_json():
    return json.dumps(build_validation_report_p2(), ensure_ascii=False, indent=2, sort_keys=True)


def _count_checks(src_counts):
    checks = {}
    for doctype, tables in DOCTYPE_TABLE_MAP_P2.items():
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
    for doctype in DOCTYPE_TABLE_MAP_P2:
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
    for doctype in DOCTYPE_TABLE_MAP_P2:
        missing = frappe.db.count(doctype, {"legacy_payload": ["in", ["", None]]})
        checks[doctype] = {"missing_legacy_payload": missing, "status": "pass" if missing == 0 else "fail"}
    return checks


def _link_coverage_checks():
    result = {}
    legacy_name_maps = {
        doctype: {
            row.legacy_id: row.name
            for row in frappe.get_all(doctype, fields=["legacy_id", "name"], limit_page_length=0)
            if row.legacy_id
        }
        for doctype in set(DOCTYPE_TABLE_MAP_P2)
        | {target for rules in LINK_COVERAGE_CHECKS_P2.values() for _l, _f, target in rules}
    }

    for doctype, checks in LINK_COVERAGE_CHECKS_P2.items():
        rows = frappe.get_all(
            doctype,
            fields=["name", "legacy_id"] + [field for pair in checks for field in pair[:2]],
            limit_page_length=0,
        )
        per_field = {}
        for legacy_field, link_field, target_doctype in checks:
            expected_count = 0
            linked_count = 0
            mismatch = []
            for row in rows:
                legacy_value = row.get(legacy_field)
                if not legacy_value:
                    continue
                expected_name = legacy_name_maps.get(target_doctype, {}).get(legacy_value)
                if not expected_name:
                    continue
                expected_count += 1
                actual_name = row.get(link_field)
                if actual_name == expected_name:
                    linked_count += 1
                else:
                    mismatch.append(
                        {
                            "name": row.name,
                            "legacy_id": row.legacy_id,
                            legacy_field: legacy_value,
                            link_field: actual_name,
                            "expected_link": expected_name,
                        }
                    )
            per_field[link_field] = {
                "legacy_field": legacy_field,
                "target_doctype": target_doctype,
                "expected_link_count": expected_count,
                "linked_count": linked_count,
                "missing_or_mismatch_count": len(mismatch),
                "missing_or_mismatch": mismatch[:20],
                "status": "pass" if not mismatch else "fail",
            }
        result[doctype] = per_field
    return result


def _secret_leak_checks():
    """Confirm raw session tokens never made it into legacy_payload or any field."""
    checks = {}
    for doctype, fields in SECRET_FIELDS_P2.items():
        rows = frappe.get_all(doctype, fields=["name", "legacy_payload"], limit_page_length=0)
        leaks = []
        for row in rows:
            payload = row.get("legacy_payload") or ""
            for field in fields:
                if f'"{field}":' in payload and "[REDACTED" not in payload:
                    leaks.append({"name": row.name, "field": field})
        checks[doctype] = {"leak_count": len(leaks), "leaks": leaks[:20], "status": "pass" if not leaks else "fail"}
    return checks


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
