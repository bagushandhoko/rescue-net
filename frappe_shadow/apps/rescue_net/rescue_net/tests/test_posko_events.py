"""A posko can handle several disasters (owner 2026-10-19): RN Posko.served_events,
picked on registration and changed in Setting; posko lists / destinations /
armada of a disaster include every posko that serves it."""

import frappe

from rescue_net import api_community_cluster as cc
from rescue_net.control_centre.common import posko_served_events, serving_posko_names
from rescue_net.tests.factories import (RNTestCase, as_guest, as_user, make_actor, make_event,
                                        make_posko, make_transport_space, make_world)


class TestPoskoServedEvents(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.e2 = make_event(event_status="active")

    def test_main_event_is_always_served(self):
        self.assertEqual([r.disaster_event for r in self.w.posko_a.served_events], [self.w.event.name])
        self.assertEqual(posko_served_events(self.w.posko_a.name), [self.w.event.name])

    def test_create_posko_with_several_disasters(self):
        op = make_actor()
        with as_user(op.user):
            res = cc.create_posko(title="Gudang Multi", posko_type="logistics", address="Jl. Uji",
                                  disaster_events=frappe.as_json([self.w.event.name, self.e2.name]))
        doc = frappe.get_doc("RN Posko", res["posko"])
        self.assertEqual(doc.disaster_event, self.w.event.name)
        self.assertEqual([r.disaster_event for r in doc.served_events], [self.w.event.name, self.e2.name])
        self.assertIn(doc.name, serving_posko_names(self.e2.name))
        self.assertNotIn(doc.name, serving_posko_names(make_event().name))

    def test_unknown_disaster_rejected(self):
        op = make_actor()
        with as_user(op.user), self.assertRaisesRegex(frappe.ValidationError, "Bencana tidak ditemukan"):
            cc.create_posko(title="X", posko_type="logistics", address="-", disaster_events="tidak-ada-123")

    def test_owner_adds_and_removes_disasters(self):
        op = make_actor(posko=self.w.posko_a)
        with as_user(op.user):
            r = cc.set_posko_served_events(self.w.posko_a.name, [self.w.event.name, self.e2.name])
            self.assertEqual(r["events"], [self.w.event.name, self.e2.name])
            # removing the main disaster moves "main" to the first remaining one
            r = cc.set_posko_served_events(self.w.posko_a.name, [self.e2.name])
            self.assertEqual(r["main_event"], self.e2.name)
            with self.assertRaisesRegex(frappe.ValidationError, "minimal satu"):
                cc.set_posko_served_events(self.w.posko_a.name, [])
            mine = cc.my_poskos_served_events()
        self.assertEqual([p["posko"] for p in mine], [self.w.posko_a.name])
        self.assertNotIn(self.w.posko_a.name, serving_posko_names(self.w.event.name))

    def test_other_user_cannot_change(self):
        other = make_actor(posko=self.w.posko_b)
        with as_user(other.user), self.assertRaises(frappe.PermissionError):
            cc.set_posko_served_events(self.w.posko_a.name, [self.e2.name])

    def test_second_disaster_lists_posko_as_destination_and_armada(self):
        from rescue_net.api_control_centre import event_poskos, logistik_dispatch_options
        transport = make_posko(self.w.event, self.w.org_a, posko_type="transport")
        space = make_transport_space(transport)
        for dt, name in (("RN Posko", self.w.posko_a.name), ("RN Posko", transport.name),
                         ("RN Transport Space", space.name)):    # armada lists its own disasters
            doc = frappe.get_doc(dt, name)
            doc.append("served_events", {"disaster_event": self.e2.name})
            doc.save(ignore_permissions=True)
        with as_guest():
            opts = logistik_dispatch_options(self.e2.name)
            self.assertIn(self.w.posko_a.name, [d["id"] for d in opts["destinations"]])
            self.assertNotIn(self.w.posko_b.name, [d["id"] for d in opts["destinations"]])
            self.assertIn(space.name, [a["id"] for a in opts["armada"]])
        frappe.db.set_value("RN Posko", self.w.posko_a.name, {"latitude": -6.2, "longitude": 106.8})
        with as_guest():
            pts = event_poskos(self.e2.name)["points"]
        self.assertIn(self.w.posko_a.name, [p.get("posko_id") for p in pts])

    def test_disaster_options_all_by_default_and_by_date(self):
        frappe.db.set_value("RN Disaster Event", self.e2.name, "started_at", "2026-03-05 08:00:00")
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "started_at", "2025-01-10 08:00:00")
        with as_guest():
            all_ids = [d["id"] for d in cc.disaster_options()]
            march = [d["id"] for d in cc.disaster_options(date_from="2026-03-01", date_to="2026-03-31")]
        self.assertIn(self.e2.name, all_ids)
        self.assertIn(self.w.event.name, all_ids)
        self.assertIn(self.e2.name, march)
        self.assertNotIn(self.w.event.name, march)

    def test_landing_lists_every_served_disaster(self):
        from rescue_net.api_auth import my_landing
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "event_status", "active")
        op = make_actor(posko=self.w.posko_a)
        with as_user(op.user):
            cc.set_posko_served_events(self.w.posko_a.name, [self.w.event.name, self.e2.name])
            ids = [e["id"] for e in my_landing()["events"]]
        bare = lambda n: n.replace("disaster_events:", "")
        self.assertEqual(set(ids), {bare(self.w.event.name), bare(self.e2.name)})
