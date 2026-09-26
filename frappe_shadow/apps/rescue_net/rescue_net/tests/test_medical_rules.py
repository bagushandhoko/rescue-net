"""Medical case / evacuation rules on every save path (phase 2: M-2, M-3, M-4)."""

import frappe

from rescue_net.tests.factories import RNTestCase, _insert, make_medical_case, make_posko, make_world


def evac(case, **kw):
    return _insert("RN Medical Evacuation", posko=case.posko, medical_case=case.name,
                   destination_facility="RSUD Uji", evacuation_status=kw.pop("status", "requested"), **kw)


def case_status(case):
    return frappe.db.get_value("RN Medical Case", case.name, "case_status")


def move(doc, *statuses):
    for s in statuses:
        doc.evacuation_status = s
        doc.save(ignore_permissions=True)


class TestMedicalRules(RNTestCase):
    def setUp(self):
        super().setUp()
        w = make_world()
        self.posko = make_posko(w.event, w.org_a, posko_type="medical")
        self.case = make_medical_case(self.posko)

    def test_closed_case_is_terminal_on_direct_save(self):
        self.case.case_status = "closed"
        self.case.save(ignore_permissions=True)
        self.case.case_status = "admitted"
        with self.assertRaises(frappe.ValidationError):
            self.case.save(ignore_permissions=True)

    def test_evacuation_moves_the_case(self):
        e = evac(self.case)
        self.assertEqual(case_status(self.case), "referred")
        move(e, "assigned", "patient_on_board")
        self.assertEqual(case_status(self.case), "evacuating")
        move(e, "arrived_hospital", "handover_complete")
        self.assertEqual(case_status(self.case), "admitted")

    def test_evacuation_does_not_revive_a_closed_case(self):
        e = evac(self.case)
        frappe.db.set_value("RN Medical Case", self.case.name, "case_status", "closed")
        move(e, "assigned", "patient_on_board", "arrived_hospital", "handover_complete")
        self.assertEqual(case_status(self.case), "closed")

    def test_cancelled_evacuation_hands_the_case_back(self):
        e = evac(self.case)
        move(e, "cancelled")
        self.assertEqual(case_status(self.case), "active")

    def test_one_running_evacuation_per_case(self):
        evac(self.case)
        with self.assertRaises(frappe.ValidationError):
            evac(self.case)

    def test_terminal_case_cannot_be_evacuated(self):
        frappe.db.set_value("RN Medical Case", self.case.name, "case_status", "deceased")
        with self.assertRaises(frappe.ValidationError):
            evac(self.case)

    def test_evacuation_graph_on_direct_save(self):
        e = evac(self.case)
        e.evacuation_status = "handover_complete"
        with self.assertRaises(frappe.ValidationError):
            e.save(ignore_permissions=True)
