"""Disaster event list for the public pages (welcome page, disaster detail)
and a health check for the offline app. Replaces the cutover-era
`rescue_net.compat.api` adapter (removed in phase 3)."""

import frappe
from frappe.rate_limiter import rate_limit

_EVENT_FIELDS = ["name", "legacy_id", "title", "event_status", "severity", "location_summary", "started_at",
                 "modified"]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def disasters(limit=100):
    """{"disasters": [...]} newest first — the same shape the old compat
    adapter returned, so the page renderers did not change."""
    meta = frappe.get_meta("RN Disaster Event")
    fields = [f for f in _EVENT_FIELDS if f == "name" or meta.has_field(f)]
    rows = frappe.get_all("RN Disaster Event", fields=fields, order_by="modified desc",
                          limit_page_length=max(1, min(int(limit or 100), 500)))
    out = []
    for r in rows:
        d = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.items()}
        d["id"] = d.get("legacy_id") or d["name"]
        d["frappe_name"] = d["name"]
        out.append(d)
    return {"disasters": out}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def health():
    return {"system": "Rescue-Net", "status": "running", "backend": "frappe"}
