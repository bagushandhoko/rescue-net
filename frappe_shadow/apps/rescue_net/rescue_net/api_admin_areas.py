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
