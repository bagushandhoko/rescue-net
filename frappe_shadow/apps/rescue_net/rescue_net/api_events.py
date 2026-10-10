"""Disaster event list for the public pages (welcome page, disaster detail)
and a health check for the offline app. Replaces the cutover-era
`rescue_net.compat.api` adapter (removed in phase 3)."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.services.drill import real_rows

_EVENT_FIELDS = ["name", "legacy_id", "title", "event_status", "severity", "location_summary", "started_at", "is_drill", "drill_label",
                 "modified"]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def disasters(limit=100, include_drill=None):
    """{"disasters": [...]} newest first — the same shape the old compat
    adapter returned, so the page renderers did not change."""
    meta = frappe.get_meta("RN Disaster Event")
    fields = [f for f in _EVENT_FIELDS if f == "name" or meta.has_field(f)]
    # draft events (BMKG early-warning drafts) are unverified: never in the public list
    rows = frappe.get_all("RN Disaster Event", filters={"event_status": ["!=", "draft"]}, fields=fields, order_by="modified desc",
                          limit_page_length=max(1, min(int(limit or 100), 500)))
    rows = real_rows(rows, key="name", include_drill=include_drill)  # latihan (10g) tidak pernah di daftar publik
    out = []
    for r in rows:
        d = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.items()}
        d["id"] = d.get("legacy_id") or d["name"]
        d["frappe_name"] = d["name"]
        out.append(d)
    return {"disasters": out}


@frappe.whitelist()
def drill_status(event):
    """Untuk banner 'MODE LATIHAN' (pengguna login): apakah event ini latihan, dan labelnya."""
    from rescue_net.services.drill import is_drill_event

    name = frappe.db.get_value("RN Disaster Event", event, "name") or frappe.db.get_value(
        "RN Disaster Event", {"legacy_id": str(event).replace("disaster_events:", "")}, "name")
    if not name or not is_drill_event(name):
        return {"is_drill": 0}
    return {"is_drill": 1, "label": frappe.db.get_value("RN Disaster Event", name, "drill_label") or "Latihan"}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def health():
    return {"system": "Rescue-Net", "status": "running", "backend": "frappe"}
