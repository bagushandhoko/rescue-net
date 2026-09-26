"""Stock receipts — one path for flow receipts and direct aid offers (phase 2: L-3, L-4).

Stock is an append-only series of RN Stock Observation snapshots; kitchen usage
(RN Kitchen Ingredient Usage, status consumed) after the latest snapshot is
subtracted at read time. A receipt therefore starts from the *effective* stock
(snapshot − usage since it), not the raw snapshot — otherwise every receipt
"refunds" the kitchen usage because the new snapshot resets the baseline.
"""

import frappe
from frappe.utils import flt, now_datetime


def consumed_after(posko, item_name, unit, baseline):
    """Kitchen usage of this item consumed after `baseline` (None = all)."""
    filters = {
        "posko": posko,
        "item_name": item_name,
        "unit": unit,
        "usage_status": "consumed",
    }
    if baseline:
        filters["consumed_at"] = [">", baseline]
    rows = frappe.get_all("RN Kitchen Ingredient Usage", filters=filters,
                          fields=["quantity"], limit_page_length=5000)
    return sum(flt(r.quantity) for r in rows)


def _lock_posko(posko):
    # coarse lock: serializes receipts even when no snapshot exists yet
    frappe.db.sql("SELECT name FROM `tabRN Posko` WHERE name=%s FOR UPDATE", (posko,))


def effective_quantity(posko, item_name, unit, what="penerimaan"):
    """Effective stock before a receipt, with the latest snapshot locked.
    Refuses a unit mismatch or a non-exact snapshot (it must be verified first)."""
    latest = frappe.db.sql(
        """
        SELECT name, quantity, unit, quantity_mode, observed_at, source_updated_at, creation
        FROM `tabRN Stock Observation`
        WHERE posko=%s AND item_name=%s
        ORDER BY observed_at DESC, creation DESC
        LIMIT 1
        FOR UPDATE
        """,
        (posko, item_name),
        as_dict=True,
    )
    if not latest:
        return 0.0, 0.0
    prev = latest[0]
    prev_unit = (prev.unit or "").strip()
    if prev_unit and prev_unit != unit:
        frappe.throw(
            f"Unit stok terakhir berbeda: {prev_unit} != {unit}. "
            f"Normalisasi unit diperlukan sebelum {what}."
        )
    if (prev.quantity_mode or "unknown") != "exact" and prev.quantity not in (None, ""):
        frappe.throw(
            "Stok terakhir bukan quantity exact. Verifikasi stok terlebih "
            f"dahulu sebelum {what}."
        )
    snapshot = flt(prev.quantity or 0)
    baseline = prev.observed_at or prev.source_updated_at or prev.creation
    used = consumed_after(posko, item_name, prev_unit or unit, baseline)
    return max(snapshot - used, 0.0), used


def receive_into_stock(posko, item_name, unit, qty, disaster_event, notes, what="penerimaan"):
    """Lock, compute the effective stock, append the new snapshot. Returns
    (stock_observation, previous_effective_quantity, used_since_snapshot)."""
    _lock_posko(posko)
    previous, used = effective_quantity(posko, item_name, unit, what)
    now = now_datetime()
    stock = frappe.new_doc("RN Stock Observation")
    stock.title = f"{item_name} - receipt"
    stock.disaster_event = disaster_event
    stock.posko = posko
    stock.item_name = item_name
    stock.raw_item_text = item_name
    stock.quantity = previous + qty
    stock.quantity_mode = "exact"
    stock.unit = unit
    stock.stock_state = "available"
    stock.notes = notes(previous, used) if callable(notes) else notes
    stock.observed_at = now
    stock.source_updated_at = now
    stock.insert(ignore_permissions=True)
    return stock, previous, used
