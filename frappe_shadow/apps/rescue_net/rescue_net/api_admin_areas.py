import frappe
from frappe.rate_limiter import rate_limit


def _local_children(parent_code=None, level=None):
    filters = {"enabled": 1}

    if parent_code:
        filters["parent_code"] = parent_code

    if level:
        filters["level"] = level

    return frappe.get_all(
        "RN Admin Area",
        filters=filters,
        fields=["code", "area_name", "level", "parent_code"],
        order_by="area_name asc",
        limit_page_length=0,
    )


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def get_children(parent_code=None, level=None):
    return _local_children(
        parent_code=parent_code,
        level=level,
    )


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def get_provinces():
    return get_children(level="province")


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def search_areas(q=None, level=None, parent_code=None, limit=20, start=0):
    """Paged search over the (eventually ~80,000) administrative areas: by name or code, optionally within a
    level / parent. Guest-readable (administrative names are public reference data)."""
    from frappe.utils import cint

    filters = {"enabled": 1}
    if level in ("province", "city", "district", "village"):
        filters["level"] = level
    if parent_code:
        filters["parent_code"] = parent_code
    limit, start = min(max(cint(limit) or 20, 1), 100), max(cint(start), 0)
    text = (q or "").strip()
    or_filters = None
    if text:
        like = "%" + text.replace("%", "").replace("_", "") + "%"
        or_filters = [["area_name", "like", like], ["name", "like", like]]
    rows = frappe.get_all("RN Admin Area", filters=filters, or_filters=or_filters,
                          fields=["name as code", "area_name", "level", "parent_code"],
                          order_by="area_name asc", limit_start=start, limit_page_length=limit + 1)
    return {"rows": rows[:limit], "has_more": len(rows) > limit, "start": start}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def get_area(code):
    """One area with its ancestors (breadcrumb) and the external codes mapped to it (P-code, BPS …)."""
    from rescue_net.services import admin_areas

    row = frappe.db.get_value("RN Admin Area", code, ["name as code", "area_name", "level", "parent_code", "pcode_ocha",
                                                       "bps_code", "valid_from", "valid_to", "replaced_by", "enabled"], as_dict=True)
    if not row:
        frappe.throw("Wilayah tidak ditemukan", frappe.DoesNotExistError)
    return {"area": row, "path": admin_areas.ancestors(code), "external_codes": admin_areas.external_codes(code)}
