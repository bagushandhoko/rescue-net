import frappe
from frappe.model.document import Document


class RNFederationNode(Document):
    @property
    def operation_template(self):
        if self.flags.get("federation_template"):
            return self.flags.federation_template
        if self.organization:
            return frappe.db.get_value("RN Organization", self.organization, "operation_template") or "umum"
        return None

    def validate(self):
        previous = self.get_doc_before_save()
        if previous and previous.organization and self.organization != previous.organization:
            frappe.throw("Organisasi yang terhubung tidak dapat diganti.")
        self.active_organization = None
        if self.status != "approved":
            return
        org = frappe.db.get_value("RN Organization", self.organization,
                                  "privacy_mode", for_update=True) if self.organization else None
        if not org or org != "closed":
            frappe.throw("Node harus terhubung ke organisasi tertutup sebelum disetujui.")
        active = frappe.db.get_value(self.doctype, {"active_organization": self.organization}, for_update=True)
        if active and active != self.name:
            frappe.throw("Organisasi ini sudah mempunyai node aktif.")
        self.active_organization = self.organization
