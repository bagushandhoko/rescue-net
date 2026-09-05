"""Re-run normalisation on RN Aid Offer / Logistic Need / Stock Observation
rows whose canonical_group is still empty (created before the rule registry
was wired). Sets canonical_* from normalization_registry.classify_text and
refreshes base_quantity via packaging.enrich_document.

Idempotent: skips rows that already have a canonical_group, and rows whose
normalization_source is 'manual'.

Run:  bench --site osiun.localhost execute rescue_net.<thismodule>.run
"""

import frappe

from rescue_net.intelligence.normalization_registry import classify_text
from rescue_net.intelligence.packaging import enrich_document

DOCTYPES = ["RN Aid Offer", "RN Logistic Need", "RN Stock Observation"]


def run():
    summary = {}
    for dt in DOCTYPES:
        names = frappe.get_all(
            dt,
            filters={"canonical_group": ["in", [None, ""]]},
            pluck="name",
            limit_page_length=0,
        )
        fixed = 0
        still_null = 0
        for nm in names:
            doc = frappe.get_doc(dt, nm)
            if (doc.normalization_source or "") == "manual":
                continue
            raw = doc.raw_item_text or doc.item_name or doc.get("title") or ""
            s = classify_text(raw)
            if not s.get("canonical_group"):
                still_null += 1
                continue
            doc.canonical_category = s.get("canonical_category")
            doc.canonical_group = s.get("canonical_group")
            doc.canonical_item = s.get("canonical_item") or doc.canonical_item
            doc.normalization_source = "rule"
            if not doc.normalization_confidence:
                doc.normalization_confidence = s.get("normalization_confidence")
            if not doc.normalization_status:
                doc.normalization_status = "suggested"
            # recompute base quantity against the new group/item
            doc.conversion_source = "none"
            doc.base_quantity = 0
            enrich_document(doc)
            doc.save(ignore_permissions=True)
            fixed += 1
        summary[dt] = {"null_rows": len(names), "reclassified": fixed,
                       "still_unmatched": still_null}
    frappe.db.commit()
    return summary
