"""Program Khusus plan editing: milestones, locations, needs, output verification."""

import frappe
from frappe.utils import cint, flt

from rescue_net.api_kitchen import rn_actor, _is_control
from rescue_net.donor_program.common import _allowed_owner, _program

_KINDS = {
    "milestone": ("RN Program Milestone", {"title", "sort_order", "due_date", "milestone_status", "progress_percent"}),
    "location": ("RN Program Location", {"title", "latitude", "longitude", "location_status"}),
    "need": ("RN Program Need", {"item", "kind", "qty_needed", "qty_available", "unit", "needed_by"}),
}


def _assert_manage(actor, row):
    if not (_is_control(actor) or _allowed_owner(actor, row.owner_type, row.owner_id)):
        frappe.throw("Hanya pemilik program atau Control Centre yang boleh mengubah rencana program.",
                     frappe.PermissionError)


@frappe.whitelist()
def save_plan_item(donor_program, item_type, name=None, values=None):
    """Create or edit one milestone / location / need of a program."""
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    if item_type not in _KINDS:
        frappe.throw("Jenis item rencana tidak dikenal.")
    doctype, allowed = _KINDS[item_type]
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    clean = {k: v for k, v in values.items() if k in allowed}
    if name:
        doc = frappe.get_doc(doctype, name)
        if doc.program != donor_program:
            frappe.throw("Item bukan milik program ini.", frappe.PermissionError)
        doc.update(clean)
    else:
        doc = frappe.new_doc(doctype)
        doc.program = donor_program
        doc.update(clean)
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "item_type": item_type}


@frappe.whitelist()
def delete_plan_item(donor_program, item_type, name):
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    if item_type not in _KINDS:
        frappe.throw("Jenis item rencana tidak dikenal.")
    doctype = _KINDS[item_type][0]
    if frappe.db.get_value(doctype, name, "program") != donor_program:
        frappe.throw("Item bukan milik program ini.", frappe.PermissionError)
    frappe.delete_doc(doctype, name, ignore_permissions=True)
    return {"deleted": name}


@frappe.whitelist()
def set_output_verification(donor_program, status=None, output_target=None, output_verified=None,
                            verifier=None, estimated_done=None):
    """Record the output check (e.g. 6 of 12 posko verified). Verified count
    can never exceed the target."""
    actor = rn_actor()
    row = _program(donor_program)
    _assert_manage(actor, row)
    if status not in (None, "", "belum_dimulai", "dalam_proses", "terverifikasi", "ditolak"):
        frappe.throw("Status verifikasi output tidak valid.")
    current = frappe.db.get_value("RN Donor Program", donor_program, ["output_target", "output_verified"], as_dict=True)
    target = cint(current.output_target) if output_target in (None, "") else cint(output_target)
    verified = cint(current.output_verified) if output_verified in (None, "") else cint(output_verified)
    if target < 0 or verified < 0:
        frappe.throw("Output tidak boleh negatif.")
    if verified > target:
        frappe.throw("Output terverifikasi tidak boleh melebihi target output.")
    updates = {"output_target": target, "output_verified": verified}
    if status not in (None, ""):
        updates["output_verification_status"] = status
    if verifier is not None:
        updates["output_verifier"] = verifier
    if estimated_done not in (None, ""):
        updates["output_estimated_done"] = estimated_done
    for k, v in updates.items():
        frappe.db.set_value("RN Donor Program", donor_program, k, v)
    return {"program": donor_program, **updates}
