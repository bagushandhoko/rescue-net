"""SITREP otomatis (2026-10-26): one report per disaster and period, safe for guests."""

import frappe

from rescue_net.api_sitrep import sitrep
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, make_world


class TestSitrep(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()

    def test_guest_gets_a_report_with_period_changes(self):
        _insert("RN Logistic Need", title="Beras", posko=self.w.posko_a.name, item_name="Beras", quantity=10, unit="karung",
                disaster_event=self.w.event.name)
        with as_guest():
            r = sitrep(self.w.event.name, hours=24)
        self.assertEqual(r["periode"]["jam"], 24)
        self.assertIn("situasi", r)
        keys = {c["key"]: c["value"] for c in r["perubahan_periode"]}
        self.assertGreaterEqual(keys.get("kebutuhan_baru", 0), 1)

    def test_hours_are_clamped_and_unknown_event_refused(self):
        with as_guest():
            self.assertEqual(sitrep(self.w.event.name, hours=999)["periode"]["jam"], 168)
            with self.assertRaises(frappe.DoesNotExistError):
                sitrep("event-tidak-ada")

    def test_no_contact_or_patient_detail_in_report(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "officer_in_charge_phone", "0812-0000-5555")
        with as_guest():
            blob = frappe.as_json(sitrep(self.w.event.name))
        self.assertNotIn("0812-0000-5555", blob)

    def test_untagged_record_of_a_serving_posko_is_counted(self):
        from rescue_net.api_sitrep import _count, _scope
        from frappe.utils import add_to_date, now_datetime
        _insert("RN Logistic Need", title="Air", posko=self.w.posko_a.name, item_name="Air", quantity=1, unit="dus")
        from rescue_net.control_centre.common import serving_posko_names
        n = _count("RN Logistic Need", _scope("RN Logistic Need", self.w.event.name, serving_posko_names(self.w.event.name)),
                   add_to_date(now_datetime(), hours=-1), now_datetime())
        self.assertGreaterEqual(n, 1)
