"""Early-warning banner feed (Fase 10a). Guest-safe: only the public facts of
the warning itself — never the draft event, posko list or raw payload."""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime

from rescue_net.access_policy import is_system_manager
from rescue_net.services.early_warning import STATUS_KEY


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def banner():
    rows = frappe.get_all(
        "RN Early Warning",
        filters={"status": ["in", ["new", "acknowledged"]], "meets_threshold": 1,
                 "expires_at": [">", now_datetime()]},
        fields=["name", "title", "area_desc", "potential", "magnitude", "depth_km",
                "issued_at", "severity", "source"],
        order_by="issued_at desc", limit_page_length=5)
    st = frappe.cache().get_value(STATUS_KEY) or {}
    return {
        "warnings": [dict(r, issued_at=str(r.issued_at), unverified=True) for r in rows],
        "source_ok": st.get("ok", True),
        "checked_at": st.get("checked_at"),
        "attribution": "Sumber: BMKG (data.bmkg.go.id). Belum diverifikasi oleh Rescue-Net.",
    }


@frappe.whitelist()
def review(name, action):
    """System Manager: acknowledge or dismiss a warning (activating the draft
    event stays a manual step in Desk)."""
    if not is_system_manager():
        frappe.throw("Hanya System Manager", frappe.PermissionError)
    if action not in ("acknowledged", "dismissed"):
        frappe.throw("Aksi tidak dikenal")
    frappe.db.set_value("RN Early Warning", name, "status", action)
    return {"name": name, "status": action}
