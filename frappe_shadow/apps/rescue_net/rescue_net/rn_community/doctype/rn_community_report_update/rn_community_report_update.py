import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

UPDATE_TYPES = {"info", "additional_need", "resolved"}


class RNCommunityReportUpdate(Document):
    """A follow-up on a citizen report: the reporter adds what changed or what
    else is needed, the routed posko answers. Written only through
    api_reports.add_community_report_update (who may write is checked there
    and again here)."""

    def before_insert(self):
        self.posted_at = self.posted_at or now_datetime()

    def validate(self):
        from rescue_net.services.guards import assert_non_negative, bypass

        if self.update_type not in UPDATE_TYPES:
            frappe.throw("Jenis tindak lanjut tidak valid")
        if not (self.body or "").strip():
            frappe.throw("Isi tindak lanjut wajib diisi")
        assert_non_negative(self, "affected_people_count")
        if bypass(self) or not self.is_new():
            return
        if self.author_role not in ("reporter", "posko"):
            frappe.throw("Tindak lanjut hanya dari pelapor atau posko tujuan.", frappe.PermissionError)
