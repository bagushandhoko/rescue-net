import frappe


PREFIXES = {
    "RN Disaster Event": "disaster_events:",
    "RN Posko": "posko_nodes:",
    "RN Organization": "organizations:",
}


def _clean(value):
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def resolve_reference(
    doctype,
    value,
    prefix=None,
):
    """
    Resolve Rescue-Net references consistently.

    Accepted inputs:
    - canonical Frappe document name
    - legacy_id
    - unprefixed legacy ID

    Unknown references are returned unchanged for
    backward compatibility; validation remains the
    responsibility of the calling domain.
    """
    value = _clean(value)

    if not value:
        return None

    if frappe.db.exists(
        doctype,
        value,
    ):
        return value

    prefix = (
        prefix
        if prefix is not None
        else PREFIXES.get(doctype)
    )

    candidates = [value]

    if (
        prefix
        and not value.startswith(prefix)
    ):
        candidates.append(
            prefix + value
        )

    for candidate in candidates:
        name = frappe.db.get_value(
            doctype,
            {
                "legacy_id": candidate,
            },
            "name",
        )

        if name:
            return name

        if frappe.db.exists(
            doctype,
            candidate,
        ):
            return candidate

    return value


def resolve_disaster_event(value):
    name = resolve_reference(
        "RN Disaster Event",
        value,
        "disaster_events:",
    )
    # a merged event (SOP 2026-11-01) resolves to the event it was merged into
    if name and frappe.db.exists("RN Disaster Event", name) and frappe.db.get_value(
            "RN Disaster Event", name, "merged_into"):
        from rescue_net.services.event_merge import final_event
        return final_event(name)
    return name


def resolve_posko(value):
    return resolve_reference(
        "RN Posko",
        value,
        "posko_nodes:",
    )


def resolve_organization(value):
    return resolve_reference(
        "RN Organization",
        value,
        "organizations:",
    )
