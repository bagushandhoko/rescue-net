import json
from pathlib import Path
import frappe


BASE = Path("/tmp")


def _rows(table):
    p = BASE / f"{table}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text())


def _legacy(doctype, raw, prefixes=()):
    if not raw:
        return None

    found = frappe.db.get_value(
        doctype,
        {"legacy_id": raw},
        "name",
    )
    if found:
        return found

    if frappe.db.exists(doctype, raw):
        return raw

    for prefix in prefixes:
        candidate = f"{prefix}:{raw}"
        if frappe.db.exists(doctype, candidate):
            return candidate

    return None


def _save(doc):
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)


def run():
    stats = {}

    org_rows = _rows("organizations")

    for r in org_rows:
        name = _legacy("RN Organization", r["id"], ("organizations",))
        doc = frappe.get_doc("RN Organization", name) if name else frappe.new_doc("RN Organization")

        doc.legacy_id = r["id"]
        doc.legacy_source = "rescue-net-fastapi"
        doc.migration_status = "Shadow Imported"
        doc.title = r["name"]
        doc.organization_type = r["organization_type"]
        doc.trust_level = r["trust_level"]
        doc.status = r["status"]
        doc.owner_type = r.get("owner_type")
        doc.owner_id = r.get("owner_id")
        doc.visibility_scope = r.get("visibility_scope")
        doc.access_policy = r.get("access_policy")
        doc.contact_person = r.get("contact_person")
        doc.notes = r.get("notes")
        doc.identity_verification_status = r.get("identity_verification_status")
        doc.identity_verified_by = r.get("identity_verified_by")
        doc.identity_verified_at = r.get("identity_verified_at")
        doc.trusted_verifier_count = r.get("trusted_verifier_count") or 0
        doc.public_verified_badge = 1 if r.get("public_verified_badge") else 0
        doc.legacy_payload = json.dumps(r, ensure_ascii=False)
        _save(doc)

    stats["organizations"] = len(org_rows)

    posko_rows = _rows("posko_nodes")

    for r in posko_rows:
        name = _legacy("RN Posko", r["id"], ("posko_nodes",))
        doc = frappe.get_doc("RN Posko", name) if name else frappe.new_doc("RN Posko")

        doc.legacy_id = r["id"]
        doc.legacy_source = "rescue-net-fastapi"
        doc.migration_status = "Shadow Imported"
        doc.title = r["name"]
        doc.disaster_event = _legacy(
            "RN Disaster Event",
            r.get("disaster_event_id"),
            ("disaster_events",),
        )
        doc.organization = _legacy(
            "RN Organization",
            r.get("organization_id"),
            ("organizations",),
        )
        doc.posko_type = r["node_type"]
        doc.address = r["location"]
        doc.verification_status = r["verification_status"]
        doc.operational_status = r["operational_status"]
        doc.latitude = r.get("lat")
        doc.longitude = r.get("lng")
        doc.owner_type = r.get("owner_type")
        doc.owner_id = r.get("owner_id")
        doc.visibility_scope = r.get("visibility_scope")
        doc.access_policy = r.get("access_policy")
        doc.officer_in_charge_name = r.get("officer_in_charge_name")
        doc.officer_in_charge_phone = r.get("officer_in_charge_phone")
        doc.officer_in_charge_role = r.get("officer_in_charge_role")
        doc.admin_area_id = r.get("admin_area_id")
        doc.admin_level = r.get("admin_level")
        doc.area_level = r.get("area_level")
        doc.province_name = r.get("province_name")
        doc.city_name = r.get("city_name")
        doc.district_name = r.get("district_name")
        doc.village_name = r.get("village_name")
        doc.coverage_radius_meters = r.get("coverage_radius_meters")
        doc.notes = r.get("notes")
        doc.identity_verification_status = r.get("identity_verification_status")
        doc.identity_verified_by = r.get("identity_verified_by")
        doc.identity_verified_at = r.get("identity_verified_at")
        doc.trusted_verifier_count = r.get("trusted_verifier_count") or 0
        doc.public_verified_badge = 1 if r.get("public_verified_badge") else 0
        doc.legacy_payload = json.dumps(r, ensure_ascii=False)
        _save(doc)

    # Parent/canonical links only after all Posko exist.
    for r in posko_rows:
        name = _legacy("RN Posko", r["id"], ("posko_nodes",))
        if not name:
            continue

        frappe.db.set_value(
            "RN Posko",
            name,
            {
                "parent_posko": _legacy(
                    "RN Posko",
                    r.get("parent_posko_id"),
                    ("posko_nodes",),
                ),
                "canonical_posko": _legacy(
                    "RN Posko",
                    r.get("canonical_posko_id"),
                    ("posko_nodes",),
                ),
            },
            update_modified=False,
        )

    stats["posko_nodes"] = len(posko_rows)

    for table, doctype, relation in [
        ("organization_memberships", "RN Organization Membership", "organization"),
        ("posko_assignments", "RN Posko Assignment", "posko"),
    ]:
        rows = _rows(table)

        for r in rows:
            name = _legacy(doctype, r["id"])
            doc = frappe.get_doc(doctype, name) if name else frappe.new_doc(doctype)

            doc.legacy_id = r["id"]
            doc.legacy_source = "rescue-net-fastapi"
            doc.migration_status = "Shadow Imported"
            doc.user_account = _legacy(
                "RN User Account",
                r["user_id"],
                ("user_accounts",),
            )

            if table == "organization_memberships":
                doc.organization = _legacy(
                    "RN Organization",
                    r["organization_id"],
                    ("organizations",),
                )
                doc.membership_role = r["membership_role"]
                doc.requested_at = r.get("requested_at")
                doc.approved_at = r.get("approved_at")
            else:
                doc.posko = _legacy(
                    "RN Posko",
                    r["posko_id"],
                    ("posko_nodes",),
                )
                doc.assignment_role = r["role"]

            doc.status = r["status"]
            doc.approved_by = _legacy(
                "RN User Account",
                r.get("approved_by"),
                ("user_accounts",),
            )
            doc.legacy_payload = json.dumps(r, ensure_ascii=False)
            _save(doc)

        stats[table] = len(rows)

    rows = _rows("community_report_evidence")

    for r in rows:
        name = _legacy("RN Community Report Evidence", r["id"])
        doc = frappe.get_doc("RN Community Report Evidence", name) if name else frappe.new_doc("RN Community Report Evidence")

        doc.legacy_id = r["id"]
        doc.legacy_source = "rescue-net-fastapi"
        doc.migration_status = "Shadow Imported"
        doc.report = _legacy(
            "RN Community Report",
            r["report_id"],
            ("community_reports",),
        )
        doc.file_url = r["file_url"]
        doc.file_type = r.get("file_type")
        doc.caption = r.get("caption")
        doc.verification_status = r.get("verification_status")
        doc.uploaded_at = r.get("uploaded_at")
        doc.legacy_payload = json.dumps(r, ensure_ascii=False)
        _save(doc)

    stats["community_report_evidence"] = len(rows)

    rows = _rows("community_report_verifications")

    for r in rows:
        name = _legacy("RN Community Report Verification", r["id"])
        doc = frappe.get_doc("RN Community Report Verification", name) if name else frappe.new_doc("RN Community Report Verification")

        doc.legacy_id = r["id"]
        doc.legacy_source = "rescue-net-fastapi"
        doc.migration_status = "Shadow Imported"
        doc.report = _legacy(
            "RN Community Report",
            r["report_id"],
            ("community_reports",),
        )
        doc.verifier_user = _legacy(
            "RN User Account",
            r.get("verifier_id"),
            ("user_accounts",),
        )
        doc.verifier_role = r.get("verifier_role")
        doc.action = r["action"]
        doc.notes = r.get("notes")
        doc.before_status = r.get("before_status")
        doc.after_status = r.get("after_status")
        doc.event_created_at = r.get("created_at")
        doc.legacy_payload = json.dumps(r, ensure_ascii=False)
        _save(doc)

    stats["community_report_verifications"] = len(rows)

    frappe.db.commit()

    stats["frappe"] = {
        "organizations": frappe.db.count("RN Organization"),
        "poskos": frappe.db.count("RN Posko"),
        "memberships": frappe.db.count("RN Organization Membership"),
        "assignments": frappe.db.count("RN Posko Assignment"),
        "evidence": frappe.db.count("RN Community Report Evidence"),
        "verifications": frappe.db.count("RN Community Report Verification"),
    }

    return stats
