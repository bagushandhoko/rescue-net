"""Kitchen production and work-tool deployment status graphs hold on a direct save (phase 2: L-14, L-15)."""

import frappe

from rescue_net.tests.factories import RNTestCase, make_posko, make_world


def _insert_loose(doctype, **fields):
    doc = frappe.get_doc({"doctype": doctype, **fields})
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    return doc


class TestStatusGraphs(RNTestCase):
    def setUp(self):
        super().setUp()
        self.posko = make_posko(make_world().event)

    def walk(self, doc, field, ok, refused):
        for state in ok:
            doc.set(field, state)
            doc.save(ignore_permissions=True)
        doc.set(field, refused)
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_kitchen_production_moves_forward_only(self):
        doc = _insert_loose("RN Kitchen Production", posko=self.posko.name, meal_name="Nasi bungkus",
                            portions=100, production_status="prepared")
        self.walk(doc, "production_status", ["dispatched", "distributed"], "prepared")
        with self.assertRaises(frappe.ValidationError):
            _insert_loose("RN Kitchen Production", posko=self.posko.name, meal_name="X",
                          portions=1, production_status="distributed")

    def test_tool_deployment_completed_is_final(self):
        doc = _insert_loose("RN Work Tool Deployment", work_tool_request="req-x", resource_profile="res-x",
                            quantity_assigned=1, deployment_status="reserved")
        self.walk(doc, "deployment_status", ["deployed", "completed"], "in_use")
        doc2 = _insert_loose("RN Work Tool Deployment", work_tool_request="req-x", resource_profile="res-x",
                             quantity_assigned=1, deployment_status="reserved")
        doc2.deployment_status = "in_use"
        with self.assertRaises(frappe.ValidationError):
            doc2.save(ignore_permissions=True)
