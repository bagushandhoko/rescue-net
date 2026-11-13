"""Angka ringkasan papan di tampilan "Riil Data Bencana" (owner 2026-11-13): data simulasi tidak ikut dihitung."""

import frappe

from rescue_net import api_comms, api_displacement, api_public_needs, api_verifier
from rescue_net.api_intelligence import control_centre_summary
from rescue_net.tests.factories import _insert, as_guest
from rescue_net.tests.test_operational_mode import SENT, OperationalBase
from rescue_net.tests.test_tampilan_riil import _Cookie


class TestRiilAngka(OperationalBase):
    def setUp(self):
        super().setUp()
        _insert("RN Comms Device", device_name="HT " + SENT, category="ht", status="active",
                posko=self.sim_posko.name, disaster_event=self.sim.name)
        _insert("RN Displacement Plan", title="KK " + SENT, disaster_event=self.sim.name, people_count=5,
                plan_type="undecided", status="proposed")

    def both(self, fn):
        with _Cookie(None), as_guest():
            sim = fn()
        with _Cookie("riil"), as_guest():
            riil = fn()
        return sim, riil

    def test_comms_totals(self):
        sim, riil = self.both(api_comms.comms_board)
        self.assertEqual(sim["inventory_total"]["total"] - riil["inventory_total"]["total"], 1)
        self.assertNotIn(SENT, frappe.as_json(riil))

    def test_displacement_totals(self):
        sim, riil = self.both(api_displacement.displacement_board)
        self.assertGreaterEqual(sim["totals"]["people_total"] - riil["totals"]["people_total"], 5)
        self.assertNotIn(SENT, frappe.as_json(riil))

    def test_public_needs_posko_count(self):
        frappe.db.set_value("RN Posko", self.sim_posko.name, "public_detail", "public")
        frappe.db.set_value("RN Organization", self.sim_org.name, "allow_posko_public_choice", 1)
        sim, riil = self.both(api_public_needs.board)
        self.assertLess(riil["poskos"], sim["poskos"])
        self.assertNotIn(SENT, frappe.as_json(riil))

    def test_need_summary_count(self):
        sim, riil = self.both(control_centre_summary)
        self.assertLess(riil["raw_need_count"], sim["raw_need_count"])

    def test_verifier_directory(self):
        _insert("RN Verifier Profile", title="[SIMULASI] Verifikator " + SENT, verifier_status="active")
        sim, riil = self.both(api_verifier.verifier_directory)
        self.assertIn(SENT, frappe.as_json(sim))
        self.assertNotIn("SIMULASI", frappe.as_json(riil).upper())
        self.assertEqual(riil["count"], len(riil["verifiers"]))

    def test_rows_without_event_hidden_in_riil(self):
        _insert("RN Displacement Plan", title="KK tanpa bencana " + SENT, people_count=7, plan_type="undecided", status="proposed")
        sim, riil = self.both(api_displacement.displacement_board)
        self.assertIn("KK tanpa bencana", frappe.as_json(sim))
        self.assertNotIn("KK tanpa bencana", frappe.as_json(riil))
