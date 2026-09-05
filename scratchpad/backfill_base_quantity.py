"""Backfill base_quantity / base_unit / pack_size / conversion_* on existing
RN Aid Offer + RN Logistic Need + RN Stock Observation rows.

Run:  bench --site osiun.localhost execute \
        rescue_net.scratchpad_backfill_base_quantity.run   (see note)

Because scratchpad/ is not importable, this is normally pasted into
`bench console` or run via `bench execute` after copying next to the app.
Idempotent: only fills rows whose conversion_source is empty/none and whose
base_quantity is unset, and never touches conversion_source == 'manual'.
"""

import frappe

from rescue_net.intelligence.packaging import resolve_base_quantity

DOCTYPES = ["RN Aid Offer", "RN Logistic Need", "RN Stock Observation"]


def run():
    summary = {}
    for dt in DOCTYPES:
        rows = frappe.get_all(
            dt,
            fields=[
                "name", "canonical_item", "canonical_group", "quantity",
                "unit", "quantity_mode", "raw_item_text", "item_name",
                "conversion_source", "base_quantity",
            ],
            limit_page_length=0,
        )
        touched = 0
        for r in rows:
            if (r.get("conversion_source") or "none") not in ("none", "", None):
                continue
            if r.get("base_quantity") not in (None, "", 0, 0.0):
                continue
            res = resolve_base_quantity(
                r.get("canonical_item"), r.get("canonical_group"),
                r.get("quantity"), r.get("unit"), r.get("quantity_mode"),
                r.get("raw_item_text") or r.get("item_name") or "",
            )
            vals = {
                "conversion_source": res["conversion_source"],
                "conversion_status": res["conversion_status"],
            }
            if res["base_quantity"] is not None:
                vals["base_quantity"] = res["base_quantity"]
            if res["base_unit"]:
                vals["base_unit"] = res["base_unit"]
            if res["pack_size"] is not None:
                vals["pack_size"] = res["pack_size"]
            frappe.db.set_value(dt, r["name"], vals, update_modified=False)
            touched += 1
        summary[dt] = {"scanned": len(rows), "updated": touched}
    frappe.db.commit()
    return summary
