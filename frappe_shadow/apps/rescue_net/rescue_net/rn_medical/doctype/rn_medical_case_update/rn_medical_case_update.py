import frappe
from frappe.model.document import Document


class RNMedicalCaseUpdate(Document):
    """One entry on a patient's history timeline: a status change or a note.

    Written only through rescue_net.api_medical (update_case_status /
    add_case_note); never edited by hand in the clinical flow.
    """

    pass
