import frappe

from rescue_net.intelligence.normalization import classify_text


def run():
    stats = {
        "organizations": 0,
        "poskos": 0,
        "needs": 0,
        "reports": 0,
        "evidence": 0,
    }

    for name in frappe.get_all(
        "RN Organization",
        pluck="name",
        limit_page_length=10000,
    ):
        doc = frappe.get_doc(
            "RN Organization",
            name,
        )

        changed = False

        if not doc.privacy_mode:
            doc.privacy_mode = "closed"
            changed = True

        if not doc.control_centre_share:
            doc.control_centre_share = "aggregate"
            changed = True

        if doc.privacy_mode == "closed" and doc.allow_posko_public_choice:
            doc.allow_posko_public_choice = 0
            changed = True

        if changed:
            doc.save(ignore_permissions=True)
            stats["organizations"] += 1

    for name in frappe.get_all(
        "RN Posko",
        pluck="name",
        limit_page_length=10000,
    ):
        doc = frappe.get_doc(
            "RN Posko",
            name,
        )

        changed = False

        if not doc.public_detail:
            doc.public_detail = "inherit"
            changed = True

        if not doc.freshness_policy_minutes:
            doc.freshness_policy_minutes = 180
            changed = True

        if changed:
            doc.save(ignore_permissions=True)
            stats["poskos"] += 1

    for name in frappe.get_all(
        "RN Community Need",
        pluck="name",
        limit_page_length=10000,
    ):
        doc = frappe.get_doc(
            "RN Community Need",
            name,
        )

        raw = (
            doc.raw_need_text
            or doc.description
            or doc.title
            or ""
        )

        suggestion = classify_text(raw)

        changed = False

        if not doc.raw_need_text:
            doc.raw_need_text = raw
            changed = True

        if not doc.item_kind or doc.item_kind == "tidak_diketahui":
            doc.item_kind = suggestion["item_kind"]
            changed = True

        if not doc.canonical_category and suggestion["canonical_category"]:
            doc.canonical_category = suggestion["canonical_category"]
            changed = True

        if not doc.canonical_group and suggestion["canonical_group"]:
            doc.canonical_group = suggestion["canonical_group"]
            changed = True

        if not doc.canonical_item and suggestion["canonical_item"]:
            doc.canonical_item = suggestion["canonical_item"]
            changed = True

        if not doc.quantity_mode or doc.quantity_mode == "unknown":
            doc.quantity_mode = suggestion["quantity_mode"]
            changed = True

        if not doc.normalization_source:
            doc.normalization_source = "rule"
            changed = True

        if not doc.normalization_confidence:
            doc.normalization_confidence = suggestion[
                "normalization_confidence"
            ]
            changed = True

        if not doc.normalization_status:
            doc.normalization_status = "suggested"
            changed = True

        if not doc.freshness_policy_minutes:
            doc.freshness_policy_minutes = 180
            changed = True

        if changed:
            doc.save(ignore_permissions=True)
            stats["needs"] += 1

    for name in frappe.get_all(
        "RN Community Report",
        pluck="name",
        limit_page_length=10000,
    ):
        doc = frappe.get_doc(
            "RN Community Report",
            name,
        )

        changed = False

        if not doc.observed_at and doc.legacy_created_at:
            doc.observed_at = doc.legacy_created_at
            changed = True

        if not doc.source_updated_at and doc.legacy_updated_at:
            doc.source_updated_at = doc.legacy_updated_at
            changed = True

        if not doc.freshness_policy_minutes:
            doc.freshness_policy_minutes = 360
            changed = True

        if changed:
            doc.save(ignore_permissions=True)
            stats["reports"] += 1

    for name in frappe.get_all(
        "RN Community Report Evidence",
        pluck="name",
        limit_page_length=10000,
    ):
        doc = frappe.get_doc(
            "RN Community Report Evidence",
            name,
        )

        changed = False

        if not doc.evidence_type:
            doc.evidence_type = (
                doc.file_type
                or "other"
            )
            changed = True

        if not doc.source_updated_at:
            doc.source_updated_at = (
                doc.uploaded_at
                or doc.creation
            )
            changed = True

        if changed:
            doc.save(ignore_permissions=True)
            stats["evidence"] += 1

    frappe.db.commit()
    return stats
