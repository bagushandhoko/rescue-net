"""Serve uploaded files through the API (found 2026-11-02).

The public site's nginx (rescue-web) only proxies `/rescue-net-frappe/api/method/rescue_net.api_*` to Frappe;
`/files/…` and `/private/files/…` answered 404, so every uploaded RAB, plan drawing and evidence photo was
unreachable. This endpoint streams the file instead, and rn-frappe-client.js rewrites those links on every page.

- Public files (`/files/…`): anyone (they are public by definition — program documents are transparency data).
- Private files (`/private/files/…`): the uploader, System Manager / Control Centre, or a manager of the posko
  the evidence belongs to. Everyone else gets 403 — same rule as the evidence board's "Terbatas".
"""

import mimetypes
import os
import re

import frappe

from rescue_net.access_policy import can_manage_posko, is_system_manager, rn_actor

_SAFE = re.compile(r"^/(private/)?files/[^/\\]+$")


def _file_row(url):
    return frappe.db.get_value("File", {"file_url": url}, ["name", "file_url", "is_private", "owner"], as_dict=True)


def _can_read_private(row):
    user = frappe.session.user
    if user in (None, "", "Guest"):
        return False
    if row.owner == user or is_system_manager():
        return True
    actor = rn_actor(required=False)
    if not actor:
        return False
    try:
        from rescue_net.api_kitchen import _is_control

        if _is_control(actor):
            return True
    except Exception:
        pass
    for dt, field in (("RN Evidence File", "file_path"), ("RN Operational Evidence", "file_url")):
        if not frappe.db.exists("DocType", dt) or not frappe.get_meta(dt).has_field(field):
            continue
        for posko in frappe.get_all(dt, filters={field: row.file_url}, pluck="posko", limit_page_length=20):
            if posko and can_manage_posko(actor, posko):
                return True
    return False


@frappe.whitelist(allow_guest=True)
def file(u):
    url = str(u or "").split("?", 1)[0].strip()
    if not _SAFE.match(url):
        frappe.throw("Alamat berkas tidak valid.", frappe.PermissionError)
    row = _file_row(url)
    if not row:
        raise frappe.DoesNotExistError("Berkas tidak ditemukan.")
    private = url.startswith("/private/")
    if private and not _can_read_private(row):
        frappe.throw("Berkas ini terbatas.", frappe.PermissionError)
    path = frappe.get_site_path(*([p for p in url.strip("/").split("/")] if private else ["public"] + url.strip("/").split("/")))
    if not os.path.isfile(path):
        raise frappe.DoesNotExistError("Berkas tidak ditemukan.")
    with open(path, "rb") as f:
        content = f.read()
    name = os.path.basename(path)
    frappe.local.response.filename = name
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"
    frappe.local.response.content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
