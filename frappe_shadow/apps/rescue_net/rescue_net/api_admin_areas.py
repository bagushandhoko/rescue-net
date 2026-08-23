import json
import urllib.parse
import urllib.request

import frappe


LEGACY_CHILDREN_URL = (
    "http://rescue-net-api:8092/admin-areas/children"
)


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


def _legacy_children(parent_code=None, level=None):
    params = {}

    if parent_code:
        params["parent_code"] = parent_code

    if level:
        params["level"] = level

    url = LEGACY_CHILDREN_URL + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=8) as response:
        rows = json.loads(response.read().decode("utf-8"))

    result = []

    for row in rows:
        result.append({
            "code": row.get("code"),
            "area_name": row.get("name"),
            "level": row.get("level"),
            "parent_code": row.get("parent_code"),
        })

    return result


@frappe.whitelist(allow_guest=True)
def get_children(parent_code=None, level=None):
    try:
        rows = _legacy_children(
            parent_code=parent_code,
            level=level,
        )
        if rows:
            return rows
    except Exception:
        pass

    return _local_children(
        parent_code=parent_code,
        level=level,
    )


@frappe.whitelist(allow_guest=True)
def get_provinces():
    return get_children(level="province")
