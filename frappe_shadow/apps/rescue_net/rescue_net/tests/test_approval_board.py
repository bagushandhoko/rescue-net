"""Verification & Approval board: risk from real signals, approval flow, decision log."""

import frappe

from rescue_net import api_verification as api
from rescue_net.services.approval_risk import evidence_signal, risk_label
from rescue_net.tests.factories import RNTestCase, api_call, as_guest, as_user, make_world


class TestApprovalBoard(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.posko = self.w.posko_a.name
        frappe.db.set_value("RN Posko", self.posko, "verification_status", "self_reported")

    def queue(self):
        with as_guest():
            return api_call("rescue_net.api_verification.approval_queue", disaster_event=self.w.event.name)["queue"]

    def mine(self):
        return next(r for r in self.queue() if r["name"] == self.posko)

    def detail(self):
        with as_guest():
            return api_call("rescue_net.api_verification.approval_item_detail", kind="posko", name=self.posko)

    def test_scale(self):
        self.assertEqual([risk_label(x) for x in (90, 60, 10)], ["Rendah", "Sedang", "Tinggi"])
        self.assertEqual([evidence_signal(n) for n in (0, 1, 2, 5)], [0, 50, 75, 100])

    def test_queue_row_has_risk_and_detail_explains_it(self):
        row = self.mine()
        self.assertIn(row["risk"], ("Rendah", "Sedang", "Tinggi"))
        d = self.detail()
        self.assertEqual({s["key"] for s in d["signals"]}, {"identity", "track", "evidence"})
        self.assertEqual(d["risk_score"], row["risk_score"])
        self.assertEqual(round(sum(s["value"] for s in d["signals"]) / 3), d["risk_score"])
        self.assertEqual(d["flow"][0]["state"], "current")      # pending: Pemeriksaan Awal
        self.assertEqual(d["audit"][-1]["label"], "Draft dibuat")

    def test_decisions_are_logged_and_move_the_flow(self):
        with as_user("Administrator"):
            api.approval_action("posko", self.posko, "escalate", note="Perlu senior")
        d = self.detail()
        self.assertEqual(d["flow"][1]["state"], "current")      # Review Senior
        self.assertEqual(d["audit"][0]["label"], "Dieskalasi")
        self.assertEqual(d["audit"][0]["note"], "Perlu senior")
        with as_user("Administrator"):
            api.approval_action("posko", self.posko, "approve")
        d = self.detail()
        self.assertEqual([s["state"] for s in d["flow"]], ["done", "done", "done", "done"])
        self.assertEqual(len(frappe.get_all("RN Approval Log", filters={"target_name": self.posko})), 2)

    def test_log_cannot_be_edited(self):
        with as_user("Administrator"):
            api.approval_action("posko", self.posko, "reject")
        log = frappe.get_doc("RN Approval Log", frappe.get_all("RN Approval Log", filters={"target_name": self.posko}, pluck="name")[0])
        log.note = "diubah"
        with self.assertRaises(frappe.ValidationError):
            log.save(ignore_permissions=True)
