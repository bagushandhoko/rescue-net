"""Small reusable guards for DocType controllers."""

import frappe


def bypass(doc):
    """Data loads (legacy migration, fixtures, bench import, patches) set
    their own states; rules apply to every live write."""
    return bool(
        doc.flags.get("rn_data_load")
        or frappe.flags.in_import
        or frappe.flags.in_migrate
        or frappe.flags.in_install
        or frappe.flags.in_patch
    )


def previous(doc, field):
    """Value of `field` before this save (None on insert)."""
    if doc.is_new():
        return None
    before = doc.get_doc_before_save()
    return before.get(field) if before else None


def changed(doc, field):
    return not doc.is_new() and previous(doc, field) != doc.get(field)


def assert_transition(doc, field, graph, label=None, initial=None):
    """`graph` = {from_state: {allowed to_states}}; list terminal states with
    an empty set. An old value that is not a key at all (legacy / migrated
    spelling) may move to any state — the value-set check stays with the
    controller. On insert, `initial` (if given) limits the first state."""
    if bypass(doc):
        return
    new = doc.get(field) or None
    label = label or doc.meta.get_label(field) or field
    if doc.is_new():
        if initial is not None and new not in initial:
            frappe.throw(f"{label} awal '{new}' tidak diizinkan.")
        return
    old = previous(doc, field) or None
    if old == new or old not in graph:
        return
    if new not in graph.get(old, ()):
        frappe.throw(f"{label} tidak bisa berubah dari '{old}' ke '{new}'.")


def assert_non_negative(doc, *fields):
    for f in fields:
        v = doc.get(f)
        if v is not None and v != "" and float(v) < 0:
            frappe.throw(f"{doc.meta.get_label(f) or f} tidak boleh negatif.")


def assert_positive(doc, *fields):
    for f in fields:
        v = doc.get(f)
        if v is None or v == "" or float(v) <= 0:
            frappe.throw(f"{doc.meta.get_label(f) or f} harus lebih dari 0.")


def is_privileged(user=None):
    from rescue_net.access_policy import is_system_manager
    return is_system_manager(user)
