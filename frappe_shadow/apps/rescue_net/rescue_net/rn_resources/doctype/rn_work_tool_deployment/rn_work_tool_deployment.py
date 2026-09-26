import hashlib

import frappe
from frappe.model.document import Document
from frappe.utils import flt


# completed / cancelled are final
TRANSITIONS = {
    "reserved": {"deployed", "cancelled"},
    "deployed": {"in_use", "completed", "cancelled"},
    "in_use": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class RNWorkToolDeployment(Document):
    def autoname(self):
        if self.legacy_id:
            self.name = self.legacy_id
            return

        seed = (
            f"{self.work_tool_request}:"
            f"{self.resource_profile}:"
            f"{frappe.generate_hash(length=12)}"
        )

        self.name = (
            "rn-tool-deploy-"
            + hashlib.sha256(
                seed.encode()
            ).hexdigest()[:20]
        )

    def validate(self):
        if self.deployment_status not in TRANSITIONS:
            frappe.throw(
                "Status deployment tidak valid"
            )

        from rescue_net.services.guards import assert_transition
        assert_transition(self, "deployment_status", TRANSITIONS, "Status deployment", initial={"reserved"})

        if flt(self.quantity_assigned) <= 0:
            frappe.throw(
                "Quantity deployment harus lebih dari 0"
            )
