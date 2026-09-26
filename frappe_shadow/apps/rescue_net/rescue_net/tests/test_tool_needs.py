"""Kebutuhan & Manajemen Alat Kerja: tools follow from the physical field
condition (owner's examples), estimates become requests once, then management."""

import frappe

from rescue_net import api_resource_tools as api
from rescue_net.services import tool_needs
from rescue_net.tests.factories import RNTestCase, _insert, as_user, make_actor, make_posko, make_world


class TestEstimate(RNTestCase):
    def qty(self, *args):
        return {e["category"]: (e["predicted_qty"], e["work_days"]) for e in tool_needs.estimate(*args)}

    def test_owner_examples(self):
        self.assertEqual(self.qty("longsoran", 200, 2), {"ekskavator": (2, 2), "buldoser": (1, 2)})
        self.assertEqual(self.qty("banjir_pemukiman", 5), {"perahu_karet": (5, None)})
        self.assertEqual(self.qty("korban_jiwa", 200), {"kantong_jenazah": (250, None)})

    def test_fewer_days_need_more_machines(self):
        self.assertEqual(self.qty("longsoran", 200, 1), {"ekskavator": (4, 1), "buldoser": (2, 1)})


class TestFromConditionToRequests(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op = make_actor(posko=self.w.posko_a)
        self.op_b = make_actor(posko=self.w.posko_b)

    def condition(self, **kw):
        with as_user(self.op.user):
            return api.create_work_object(kw.pop("title", "Longsor Jalan Desa"), kw.pop("object_type", "longsoran"),
                                          kw.pop("size_value", 200), posko=self.w.posko_a.name,
                                          work_days_target=kw.pop("days", 2), **kw)["work_object"]

    def test_other_posko_cannot_record_on_behalf(self):
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api.create_work_object("x", "longsoran", 10, posko=self.w.posko_a.name)

    def test_estimate_becomes_requests_once_and_board_shows_the_chain(self):
        obj = self.condition()
        self.assertEqual(frappe.db.get_value("RN Work Object", obj, "size_unit"), "m3")
        _insert("RN Resource Profile", disaster_event=self.w.event.name, owner_type="posko",
                owner_id=self.w.posko_b.name, resource_name="Ekskavator PU", resource_type="alat_berat",
                category="ekskavator", quantity=1, unit="unit", availability_status="available")
        with as_user(self.op.user):
            out = api.create_requests_from_work_object(obj)
            again = api.create_requests_from_work_object(obj)
        self.assertEqual({(c["tool_type"], c["quantity"], c["work_days"]) for c in out["created"]},
                         {("ekskavator", 2, 2), ("buldoser", 1, 2)})
        self.assertEqual(again["created"], [])
        req = frappe.get_doc("RN Work Tool Request", {"work_object": obj, "tool_type": "ekskavator"})
        self.assertEqual((req.requested_by_type, req.requested_by_id), ("posko", self.w.posko_a.name))
        self.assertIn("2 hari kerja", req.needed_for)
        self.assertEqual(frappe.db.get_value("RN Work Object", obj, "status"), "in_progress")

        board = api.work_objects_board(self.w.event.name)
        row = next(r for r in board["objects"] if r["name"] == obj)
        exc = next(p for p in row["predictions"] if p["category"] == "ekskavator")
        self.assertEqual((exc["predicted_qty"], exc["ready_available"], exc["gap"], exc["requested"], exc["to_request"]),
                         (2, 1, 1, 2, 0))
        self.assertTrue(any(c["object_type"] == "korban_jiwa" for c in board["conditions"]))

    def test_other_posko_cannot_turn_my_estimate_into_requests(self):
        obj = self.condition(object_type="korban_jiwa", size_value=200, days=None, title="Korban tertimbun")
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api.create_requests_from_work_object(obj)
        with as_user(self.op.user):
            out = api.create_requests_from_work_object(obj)
        self.assertEqual([(c["tool_type"], c["quantity"], c["unit"]) for c in out["created"]],
                         [("kantong_jenazah", 250, "pcs")])
