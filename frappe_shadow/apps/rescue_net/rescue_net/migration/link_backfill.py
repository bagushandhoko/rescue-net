import frappe


LINK_RULES = {
    "RN Posko": [
        ("disaster_event_legacy_id", "disaster_event", "RN Disaster Event"),
        ("organization_legacy_id", "organization", "RN Organization"),
    ],
    "RN Logistic Need": [
        ("disaster_event_legacy_id", "disaster_event", "RN Disaster Event"),
        ("posko_legacy_id", "posko", "RN Posko"),
    ],
    "RN Aid Offer": [
        ("disaster_event_legacy_id", "disaster_event", "RN Disaster Event"),
        ("target_posko_legacy_id", "target_posko", "RN Posko"),
    ],
    "RN Distribution Flow": [
        ("disaster_event_legacy_id", "disaster_event", "RN Disaster Event"),
        ("need_legacy_id", "logistic_need", "RN Logistic Need"),
        ("aid_offer_legacy_id", "aid_offer", "RN Aid Offer"),
        ("destination_posko_legacy_id", "destination_posko", "RN Posko"),
    ],
}


def backfill_links():
    summary = {}
    for doctype, rules in LINK_RULES.items():
        rows = frappe.get_all(
            doctype,
            fields=["name"] + [legacy_field for legacy_field, _link_field, _target in rules],
            limit_page_length=0,
        )
        changed = 0
        missing = []
        for row in rows:
            updates = {}
            for legacy_field, link_field, target_doctype in rules:
                legacy_id = row.get(legacy_field)
                if not legacy_id:
                    continue
                target_name = frappe.db.get_value(target_doctype, {"legacy_id": legacy_id}, "name")
                if target_name:
                    updates[link_field] = target_name
                else:
                    missing.append({"name": row.name, "field": legacy_field, "legacy_id": legacy_id})
            if updates:
                frappe.db.set_value(doctype, row.name, updates, update_modified=False)
                changed += 1
        summary[doctype] = {"rows_seen": len(rows), "rows_updated": changed, "missing_targets": missing[:20], "missing_count": len(missing)}
    frappe.db.commit()
    return summary


def verify_links():
    result = {}
    for doctype, rules in LINK_RULES.items():
        fields = ["name"] + [link_field for _legacy_field, link_field, _target in rules]
        rows = frappe.get_all(doctype, fields=fields, limit_page_length=0)
        per_field = {}
        for _legacy_field, link_field, _target in rules:
            filled = sum(1 for row in rows if row.get(link_field))
            per_field[link_field] = {"filled": filled, "total": len(rows)}
        result[doctype] = per_field
    return result
