import re

import frappe

from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    rn_actor,
)
from rescue_net.api_community_cluster import list_poskos


def _normalize_whatsapp(value):
    number = re.sub(r"\D", "", value or "")

    if not number:
        return None

    if number.startswith("0"):
        number = "62" + number[1:]
    elif number.startswith("8"):
        number = "62" + number

    return number


def _can_edit_posko(actor, posko):
    if is_system_manager():
        return True

    if can_manage_posko(actor, posko):
        return True

    organization = frappe.db.get_value(
        "RN Posko",
        posko,
        "organization",
    )

    return bool(
        organization
        and can_manage_organization(actor, organization)
    )


@frappe.whitelist()
def list_poskos_with_contact():
    rows = list_poskos() or []

    for row in rows:
        name = (
            row.get("name")
            if isinstance(row, dict)
            else getattr(row, "name", None)
        )

        contact = frappe.db.get_value(
            "RN Posko",
            name,
            "officer_in_charge_phone",
        )

        if isinstance(row, dict):
            row["officer_in_charge_phone"] = contact
        else:
            row.officer_in_charge_phone = contact

    return rows


@frappe.whitelist()
def set_posko_contact(posko, contact):
    actor = rn_actor()

    if not _can_edit_posko(actor, posko):
        frappe.throw(
            "Anda tidak berhak mengubah kontak Posko ini",
            frappe.PermissionError,
        )

    number = _normalize_whatsapp(contact)

    if not number:
        frappe.throw("Nomor WhatsApp tidak valid")

    frappe.db.set_value(
        "RN Posko",
        posko,
        "officer_in_charge_phone",
        number,
        update_modified=False,
    )

    return {
        "posko": posko,
        "contact": number,
        "whatsapp_url": "https://wa.me/" + number,
    }
