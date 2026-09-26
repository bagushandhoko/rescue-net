"""Control Centre — shared helpers: event/posko reference resolution, column helpers, viewer context, shared constants."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)


def cols(doctype):
    return set(
        frappe.get_meta(
            doctype
        ).get_valid_columns()
    )


def canonical_event(value):
    """Resolve a disaster-event reference to whatever value is actually
    stored on `RN Posko.disaster_event` etc. Historically every event was
    migrated in with its `name` literally prefixed `disaster_events:...`,
    so this used to just blindly prepend that prefix. A disaster event
    created directly in Frappe (`frappe.new_doc("RN Disaster Event")`,
    e.g. via the registration form) has a bare `name`/`legacy_id` instead —
    blindly prefixing it silently broke every board that filters by event
    (posko_registry_board and friends all returned zero rows). Delegate to
    the DB-aware resolver so both old (prefixed) and new (bare) events
    resolve to their real stored value."""
    from rescue_net.reference_resolver import resolve_disaster_event

    value = str(value or "").strip()
    if not value:
        return value
    return resolve_disaster_event(value) or value


def first(row, *names):
    for name in names:
        value = row.get(name)

        if value not in (
            None,
            "",
        ):
            return value

    return None


def event_filters(columns, event):
    if "disaster_event" in columns:
        return {
            "disaster_event":
                event
        }

    if (
        "disaster_event_id"
        in columns
    ):
        return {
            "disaster_event_id":
                event
        }

    return {}


_MODULE_KEYWORDS = [
    ("Medis", ("medical", "medis")),
    ("Distribusi", ("distribution", "distribusi", "transport", "road_access")),
    ("Logistik", ("logistic", "logistik", "stock", "aid_offer", "aid offer", "donation", "donasi")),
    ("Search & Found", ("missing_person", "found_person", "search_found", "missing", "found")),
    ("Shelter", ("shelter",)),
    ("Dapur Umum", ("kitchen", "dapur")),
    ("Relawan", ("volunteer", "relawan")),
    ("Program", ("donor", "recovery", "program", "work_tool", "resource_profile")),
]


_MIME_EXT = {
    "jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "webp": "image",
    "mp4": "video", "mov": "video", "webm": "video", "avi": "video",
    "pdf": "document", "doc": "document", "docx": "document", "xls": "document", "xlsx": "document",
}


_EVIDENCE_MODULE_ORDER = [
    "Logistik", "Medis", "Distribusi", "Program", "Search & Found",
    "Shelter", "Dapur Umum", "Relawan", "Lainnya",
]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_posko(value):
    value = str(value or "").strip()

    if not value:
        return None

    if frappe.db.exists("RN Posko", value):
        return value

    return frappe.db.get_value(
        "RN Posko", {"legacy_id": value}, "name"
    ) or frappe.db.get_value(
        "RN Posko", {"legacy_id": "posko_nodes:" + value}, "name"
    )


def _sf(doctype, wanted):
    """Keep only fields that actually exist on the doctype."""
    valid = cols(doctype)
    return [f for f in wanted if f == "name" or f in valid]


# share-reasons that mean the viewer OWNS/operates the posko (vs merely
# being allowed to see its detail). Used by every operational page to tell
# "manage" from "coordinate/view".
_POSKO_OWNER_REASONS = {
    "system_manager", "posko_operator", "org_member",
    "posko_assignment", "org_membership",
}


def _posko_actor_flags(posko_name, actor="__unset__"):
    """(logged_in, can_manage, can_coordinate) for an operational posko page.

    manage      -> operator / assigned / member of the posko's org
    coordinate  -> any other logged-in user, when the posko opened
                   `public_participation` (book a transport slot, send aid…)
    Server-side write endpoints still enforce their own checks; this only
    drives which controls the page shows."""
    if actor == "__unset__":
        try:
            from rescue_net.access_policy import rn_actor
            actor = rn_actor(required=False)
        except Exception:
            actor = None
    logged_in = bool(actor)
    if not posko_name:
        return logged_in, False, False
    try:
        from rescue_net.visibility import effective_posko_share
        reason = effective_posko_share(posko_name, actor).get("reason")
    except Exception:
        reason = None
    can_manage = reason in _POSKO_OWNER_REASONS
    pp = frappe.db.get_value("RN Posko", posko_name, "public_participation")
    can_coordinate = bool(logged_in and not can_manage and pp)
    return logged_in, can_manage, can_coordinate


def _poskos_viewer_context():
    """Who is asking for the posko list — lets the selector on operational
    pages group "my organisation's poskos" vs "other (national) poskos".

    Kept deliberately small: org docname + title, and the set of poskos the
    viewer may actually operate. Guests get logged_in=False / org=None and
    the frontend falls back to a single flat list."""
    try:
        from rescue_net.access_policy import rn_actor
        actor = rn_actor(required=False)
    except Exception:
        actor = None

    if not actor:
        return {"logged_in": False, "org": None, "org_title": None, "manages": []}

    org_name = actor.get("organization")
    org_title = None
    if org_name:
        org_title = (
            frappe.db.get_value("RN Organization", org_name, "title") or org_name
        )

    try:
        manages = sorted(_my_posko_names(actor))
    except Exception:
        manages = []

    return {
        "logged_in": True,
        "org": org_name,
        "org_title": org_title,
        "manages": manages,
    }


# Unit conversion reference (static domain data).
_LOGISTIK_CONVERSIONS = [
    {"item": "Beras", "base_unit": "karung", "factor": 50, "target_unit": "kg"},
    {"item": "Air Mineral", "base_unit": "dus", "factor": 24, "target_unit": "botol (600 ml)"},
    {"item": "Minyak Goreng", "base_unit": "dus", "factor": 12, "target_unit": "liter"},
    {"item": "Mie Instan", "base_unit": "dus", "factor": 40, "target_unit": "pcs"},
    {"item": "Selimut", "base_unit": "bal", "factor": 25, "target_unit": "pcs"},
]


def _norm_item(v):
    import re
    return re.sub(r"[_\s]+", " ", str(v or "").strip().lower())


_RECEIVED_STATES = {
    "received", "received_verified", "arrived", "arrived_at_posko",
    "stock_transferred", "completed", "closed",
}


_INTRANSIT_STATES = {"dispatched", "in_transit", "on_the_way", "assigned_pickup", "pickup_claimed"}


_DRILL_URGENT = {"critical", "urgent", "high", "tinggi", "darurat", "segera"}


_DRILL_CLOSED_NEED = {"fulfilled", "closed", "cancelled", "met", "resolved", "done"}


_DRILL_BLOCKED_FLOW = {
    "blocked", "delayed", "on_hold", "pending", "pending_pickup",
    "need_pickup", "awaiting_pickup", "stuck", "assigned_pickup", "cancelled",
}


_DRILL_DELIVERED_OFFER = {
    "delivered", "distributed", "completed", "closed", "received", "fulfilled",
}


_DRILL_TITLES = {
    "jiwa": "Jiwa Berisiko per Posko",
    "kebutuhan": "Kebutuhan Lapangan Belum Terpenuhi",
    "posko_kritis": "Posko Berstatus Kritis",
    "distribusi": "Alur Distribusi Bantuan",
    "distribusi_terhambat": "Distribusi Terhambat / Menunggu Pickup",
    "medis": "Kasus Medis",
    "donasi": "Tawaran Bantuan Belum Tersalur",
    "stok": "Stok Barang per Posko",
    "relawan": "Penugasan Relawan",
    "program": "Program Khusus & Donasi Terarah",
    "search": "Laporan Orang Hilang & Ditemukan",
}


_MEDICAL_OPEN_CASE = {"active", "stabilized", "evacuating"}


_MEDICAL_ACTIVE_ASSIGNMENT = {"accepted", "checked_in", "in_progress"}


_JIWA_NEED_URGENCY = {"critical", "urgent"}


JIWA_ASPECTS = (("logistik", "Logistik"), ("shelter", "Shelter"), ("medis", "Medis"))


def _fmt(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v or "")
    return f"{int(round(f)):,}".replace(",", ".")


# The six top KPI tiles + the bottom module cards. Each value is the SAME row count its drill-down
# (`kpi_drilldown`) lists, so a tile can never disagree with its own detail;
# `base` is the denominator the tile's bar is drawn against.
KPI_DIMENSIONS = ("jiwa", "kebutuhan", "posko_kritis", "distribusi",
                  "distribusi_terhambat", "medis", "donasi",
                  # bottom module cards
                  "stok", "relawan", "program", "search")


# Activity per Control Centre module card (the sparkline under each
# bottom card). Real records only: count of records per period, dated by
# `observed_at` when the doctype has it, else `creation`. Aggregate counts,
# no per-posko detail, so it is as guest-safe as the card values themselves.
TREND_SOURCES = {
    "logistics": ("RN Logistic Need",),
    "distribution": ("RN Distribution Flow",),
    "medical": ("RN Medical Case",),
    "volunteer": ("RN Volunteer Assignment",),
    "program": ("RN Donor Program Update",),
    "search_found": ("RN Missing Person Report", "RN Found Person Report"),
}


_SIT_RANK = {"safe": 0, "warning": 1, "critical": 2}


_SIT_STATUS = {"safe": "Waspada", "warning": "Siaga", "critical": "Kritis"}


_SEV_STATUS = {
    "critical": "Kritis", "urgent": "Siaga", "high": "Siaga",
    "warning": "Siaga", "normal": "Waspada", "low": "Waspada", "": "Waspada",
}


_OPS_CRITICAL = {"critical", "overload", "emergency", "danger"}


_OPS_WARNING = {"urgent", "warning", "affected", "disrupted"}


_CRIT_URGENCY = {"critical", "urgent", "high"}


_CLOSED_NEED = {"fulfilled", "closed", "cancelled", "met", "done"}


_BA_POSKO_TYPE_LABEL = {
    "medical": "Posko Medis",
    "shelter": "Shelter",
    "kitchen": "Dapur Umum",
    "logistics": "Posko Logistik",
    "collection_hub": "Posko Logistik",
    "transport": "Posko Distribusi",
}


_MEDICAL_CRIT_SEVERITY = {"severe", "critical"}


_MEDICAL_CRIT_TRIAGE = {"red", "black"}


_MEDICAL_CLOSED_CASE = {"discharged", "closed", "deceased"}


# categories that are not about one posko's own people/problems — they stay
# separate lists in the drill instead of being merged per posko
_JIWA_NON_POSKO = {"laporan_korban", "jiwa_belum_lapor"}


_DISTRIBUSI_STATUS_LABEL = {
    "planned": "Direncanakan",
    "pickup_claimed": "Akan Dijemput",
    "assigned_pickup": "Menunggu Jemput",
    "dispatched": "Dalam Perjalanan",
    "in_transit": "Dalam Perjalanan",
    "arrived": "Tiba di Tujuan",
    "received": "Diterima",
    "received_verified": "Diterima (Terverifikasi)",
    "stock_transferred": "Stok Ditransfer",
    "cancelled": "Dibatalkan",
}


# Public shipment-tracking timeline. Ordered lifecycle steps + the
# RN Distribution Flow timestamp field that marks each one reached.
_FLOW_TRACE_STEPS = [
    ("planned",         "Direncanakan",       "creation"),
    ("assigned_pickup", "Menunggu Dijemput",  "assigned_pickup_at"),
    ("dispatched",      "Berangkat",          "dispatched_at"),
    ("in_transit",      "Dalam Perjalanan",   "in_transit_at"),
    ("arrived",         "Tiba di Tujuan",     "arrived_at"),
    ("received",        "Diterima",           "received_at"),
]


# Every flow_status value we may store, folded onto a step above.
_FLOW_STATUS_TO_STEP = {
    "planned": "planned",
    "pickup_claimed": "assigned_pickup",
    "assigned_pickup": "assigned_pickup",
    "dispatched": "dispatched",
    "in_transit": "in_transit",
    "arrived": "arrived",
    "arrived_at_posko": "arrived",
    "partially_received": "received",
    "received": "received",
    "received_verified": "received",
    "stock_transferred": "received",
}


_SERVICE_MODE_LABEL = {
    "space_only": "Penyedia Ruang Muat", "courier_pickup": "Kurir Jemput-Antar",
    "both": "Ruang Muat + Kurir",
}


_ARMADA_STATUS_LABEL = {
    "available": "Tersedia", "reserved": "Dipesan", "assigned": "Ditugaskan",
    "in_transit": "Dalam Perjalanan", "arrived": "Tiba",
    "completed": "Selesai", "cancelled": "Dibatalkan",
}


_BOOKING_STATUS_LABEL = {
    "requested": "Menunggu Konfirmasi", "confirmed": "Terkonfirmasi",
    "rejected": "Ditolak", "cancelled": "Dibatalkan", "completed": "Selesai",
}


_DELIVERY_LABEL = {
    "use_transporter": "Pakai transporter posko",
    "self_deliver": "Antar sendiri ke titik jemput",
}


_ORG_PENDING_TERMS = {"pending", "self_reported", "", None}


_POSKO_INACTIVE_TERMS = {"offline", "inactive", "closed", "non_aktif", "nonaktif"}


_ORG_BRAND_ACCENT = {
    "SIM-LR-ORG": "#2f6f3e",              # Komunitas Landrover — green
    "organizations:org-landrover": "#2f6f3e",
}


_ORG_BRAND_FIELDS = [
    "name", "title", "organization_type", "control_centre_share",
    "privacy_mode", "allow_posko_public_choice", "brand_color", "brand_logo",
]


def _my_posko_names(actor):
    """Poskos the actor may manage: direct RN User Account.posko + approved
    RN Posko Assignment rows."""
    names = set()
    if actor.get("posko"):
        names.add(actor["posko"])
    try:
        for a in frappe.get_all(
            "RN Posko Assignment",
            filters={"user_account": actor.get("name"), "status": "approved"},
            fields=["posko"], limit_page_length=0,
        ):
            if a.get("posko"):
                names.add(a["posko"])
    except Exception:
        pass
    return names


def _operate_href(posko_row, event):
    """Route a posko to its operational workspace by type. Strips the
    legacy `posko_nodes:` prefix some pre-Frappe-cutover posko docnames
    still carry — every other href-builder in this module already does
    this (kebutuhan_items/posko_kritis_items/etc); this one didn't, so a
    legacy-prefixed posko (e.g. `posko_nodes:posko-sim-dapur`) produced a
    broken `?id=posko_nodes:...` link."""
    pid = str(posko_row.get("name") or "").replace("posko_nodes:", "")
    ev = event or posko_row.get("disaster_event") or ""
    ptype = str(posko_row.get("posko_type") or "").lower()
    page = {
        "logistics": "posko-logistik.html",
        "collection_hub": "posko-logistik.html",
        "transport": "posko-distribusi.html",
        "medical": "posko-medis-detail.html",
        "shelter": "shelter-detail.html",
        "kitchen": "dapur-umum.html",
    }.get(ptype, "posko-detail.html")
    return page + "?id=" + pid + "&event=" + ev
