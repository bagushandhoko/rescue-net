"""Early-warning banner feed (Fase 10a). Guest-safe: only the public facts of
the warning itself — never the draft event, posko list or raw payload."""

import frappe
from frappe.rate_limiter import rate_limit
from datetime import datetime, timezone

from rescue_net.access_policy import is_system_manager
from rescue_net.services.early_warning import STATUS_KEY


def _now_utc():
    # BMKG times (issued_at / expires_at) are stored in UTC; now_datetime() is
    # the site's WIB clock, which cut the 48-hour window to ~41 hours
    return datetime.now(timezone.utc).replace(tzinfo=None)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def banner():
    rows = frappe.get_all(
        "RN Early Warning",
        filters={"status": ["in", ["new", "acknowledged"]], "meets_threshold": 1,
                 "expires_at": [">", _now_utc()]},
        fields=["name", "title", "area_desc", "potential", "magnitude", "depth_km",
                "issued_at", "severity", "source"],
        order_by="issued_at desc", limit_page_length=5)
    # every recent quake (any magnitude) so the page always shows the live feed
    latest = frappe.get_all(
        "RN Early Warning",
        filters={"status": ["!=", "dismissed"], "expires_at": [">", _now_utc()]},
        fields=["title", "magnitude", "depth_km", "issued_at"],
        order_by="issued_at desc", limit_page_length=3)
    st = frappe.cache().get_value(STATUS_KEY) or {}
    return {
        "warnings": [dict(r, issued_at=str(r.issued_at), unverified=True) for r in rows],
        "latest": [dict(r, issued_at=str(r.issued_at)) for r in latest],
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
