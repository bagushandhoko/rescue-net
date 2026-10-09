"""Chain-of-custody scans (api_custody): status follows the Flow graph,
offline replays are idempotent, rights match update_flow_status, and the
log is append-only."""

import frappe

from rescue_net import api_custody as cu
from rescue_net import api_logistics as api
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world


class TestCustodyScan(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op_a = make_actor(posko=self.w.posko_a)
        self.op_b = make_actor(posko=self.w.posko_b)
        self.outsider = make_actor()
        with as_user(self.op_a.user):
            self.flow = api.create_flow(self.w.posko_a.name, "Beras 5 kg", quantity=10, unit="karung")["flow"]
        frappe.db.set_value("RN Distribution Flow", self.flow, {
            "source_posko": self.w.posko_a.name, "destination_posko": self.w.posko_b.name,
            "flow_status": "assigned_pickup"})

    def status(self):
        return frappe.db.get_value("RN Distribution Flow", self.flow, "flow_status")

    def scan(self, user, scan_type, **kw):
        with as_user(user):
            return cu.record_scan(flow=self.flow, scan_type=scan_type, **kw)

    def test_dispatch_to_receive_builds_chain(self):
        self.assertEqual(self.scan(self.op_a.user, "dispatch")["scan"]["outcome"], "applied")
        self.assertEqual(self.scan(self.op_a.user, "transit")["scan"]["outcome"], "applied")
        self.assertEqual(self.scan(self.op_b.user, "arrive")["scan"]["outcome"], "applied")
        r = self.scan(self.op_b.user, "receive", received_quantity=10, received_unit="karung")
        self.assertEqual(r["scan"]["outcome"], "applied")
        self.assertEqual(self.status(), "received")
        with as_user(self.op_b.user):
            chain = cu.custody_chain(flow=self.flow)["scans"]
        self.assertEqual([s["scan_type"] for s in chain], ["dispatch", "transit", "arrive", "receive"])

    def test_offline_replay_is_idempotent(self):
        a = self.scan(self.op_a.user, "dispatch", offline_id="dev1-0001")
        b = self.scan(self.op_a.user, "dispatch", offline_id="dev1-0001")
        self.assertTrue(b["duplicate"])
        self.assertEqual(a["scan"]["name"], b["scan"]["name"])
        self.assertEqual(frappe.db.count("RN Custody Scan", {"flow": self.flow}), 1)

    def test_late_duplicate_scan_does_not_regress(self):
        self.scan(self.op_a.user, "dispatch")
        self.scan(self.op_a.user, "transit")
        r = self.scan(self.op_a.user, "dispatch", offline_id="late-1")
        self.assertEqual(r["scan"]["outcome"], "already")
        self.assertEqual(self.status(), "in_transit")

    def test_skipping_ahead_is_rejected_but_logged(self):
        r = self.scan(self.op_b.user, "receive", received_quantity=1)
        self.assertEqual(r["scan"]["outcome"], "rejected")
        self.assertFalse(r["ok"])
        self.assertEqual(self.status(), "assigned_pickup")

    def test_handover_records_without_status_change(self):
        r = self.scan(self.op_a.user, "handover", note="serah ke kurir")
        self.assertEqual(r["scan"]["outcome"], "recorded")
        self.assertEqual(self.status(), "assigned_pickup")

    def test_source_operator_cannot_receive(self):
        self.scan(self.op_a.user, "dispatch")
        self.scan(self.op_b.user, "arrive")
        with self.assertRaises(frappe.PermissionError):
            self.scan(self.op_a.user, "receive", received_quantity=10)

    def test_outsider_and_guest_refused(self):
        with self.assertRaises(frappe.PermissionError):
            self.scan(self.outsider.user, "dispatch")
        with as_guest(), self.assertRaises(frappe.ValidationError):
            cu.record_scan(flow=self.flow, scan_type="dispatch")

    def test_log_is_append_only(self):
        name = self.scan(self.op_a.user, "handover")["scan"]["name"]
        doc = frappe.get_doc("RN Custody Scan", name)
        doc.note = "diubah"
        with self.assertRaises(frappe.ValidationError):
            doc.save()
        with self.assertRaises(frappe.ValidationError):
            doc.delete()
