"""Offline outbox replay (api_offline.replay): a field form queued on a phone
is applied exactly once per client id, only for allow-listed methods, only
for the logged-in user who queued it."""

import json

import frappe

from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_event, uid

M = "rescue_net.api_resource_tools.create_work_object"


class TestOfflineReplay(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()

    def args(self, title=None):
        return json.dumps({"title": title or uid("Longsor offline"), "object_type": "longsoran",
                           "size_value": 50, "disaster_event": self.event.name})

    def replay(self, cid, args=None, method=M):
        from rescue_net.api_offline import replay
        return replay(method=method, args=args or self.args(), client_event_id=cid, device_id="dev-test")

    def count(self):
        return frappe.db.count("RN Work Object", {"disaster_event": self.event.name})

    def test_applied_once_even_if_sent_twice(self):
        cid = uid("ob") + "-abcdef"
        first = self.replay(cid)
        second = self.replay(cid)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["result"]["work_object"], first["result"]["work_object"])
        self.assertEqual(self.count(), 1)

    def test_method_outside_allow_list_refused(self):
        with self.assertRaises(frappe.PermissionError):
            self.replay(uid("ob") + "-x1234567", method="rescue_net.api_resource_tools.update_resource_profile")

    def test_guest_refused(self):
        with as_guest(), self.assertRaises(frappe.PermissionError):
            self.replay(uid("ob") + "-guest123")

    def test_other_user_cannot_reuse_an_id(self):
        cid = uid("ob") + "-shared12"
        self.replay(cid)
        other = make_actor()
        with as_user(other.user), self.assertRaises(frappe.PermissionError):
            self.replay(cid)

    def test_bad_id_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self.replay("x")

    def test_server_refusal_leaves_id_free_for_a_retry(self):
        cid = uid("ob") + "-retry123"
        bad = json.dumps({"title": "X", "object_type": "tidak-ada", "size_value": 1, "disaster_event": self.event.name})
        frappe.db.savepoint("before_bad")
        with self.assertRaises(frappe.ValidationError):
            self.replay(cid, args=bad)
        frappe.db.rollback(save_point="before_bad")     # the HTTP request would roll back the same way
        self.assertFalse(frappe.db.exists("RN Sync Log", {"event_id": "offline:" + cid}))
        self.assertFalse(self.replay(cid)["duplicate"])
        self.assertEqual(self.count(), 1)


class TestOfflinePack(RNTestCase):
    """api_offline.pack: the user's own posko data, through the same read
    methods (same permissions) the pages use."""

    def test_operator_gets_own_posko_entries(self):
        from rescue_net.api_offline import pack
        from rescue_net.tests.factories import make_world
        w = make_world()
        op = make_actor(posko=w.posko_a)
        with as_user(op.user):
            data = pack()
        names = [p["name"] for p in data["poskos"]]
        self.assertIn(w.posko_a.name, names)
        self.assertNotIn(w.posko_b.name, names)          # other organisation's posko not in my pack
        methods = {(e["method"], e["args"].get("posko")) for e in data["entries"]}
        self.assertIn(("rescue_net.api_control_centre.posko_detail", w.posko_a.name), methods)
        self.assertIn(("rescue_net.api_auth.session_info", None), methods)

    def test_guest_refused(self):
        from rescue_net.api_offline import pack
        with as_guest(), self.assertRaises(frappe.PermissionError):
            pack()

    def test_pack_has_no_medical_data_for_a_non_medical_operator(self):
        from rescue_net.api_offline import pack
        from rescue_net.tests.factories import make_world
        w = make_world()
        frappe.db.set_value("RN Posko", w.posko_b.name, "posko_type", "medical")
        op = make_actor(posko=w.posko_a)
        with as_user(op.user):
            data = pack()
        self.assertFalse([e for e in data["entries"] if e["method"] == "rescue_net.api_medical.dashboard"
                          and e["args"].get("posko") == w.posko_b.name])

    def test_pack_in_parts_covers_the_whole_plan(self):
        from rescue_net.api_offline import pack
        from rescue_net.tests.factories import make_world
        w = make_world()
        op = make_actor(posko=w.posko_a)
        with as_user(op.user):
            whole = pack()
            parts, off = [], 0
            while off is not None:
                r = pack(offset=off, limit=4)
                parts += r["entries"]
                off = r["next_offset"]
        self.assertEqual(whole["total"], r["total"])
        self.assertEqual([e["method"] for e in parts], [e["method"] for e in whole["entries"]])
