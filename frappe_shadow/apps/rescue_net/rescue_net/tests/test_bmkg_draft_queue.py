"""S13 (2026-11-02): a big BMKG quake → draft event with coordinates + type → super admin is notified and sees it
in Kelola Bencana with the poskos in range → activates it (prefix dropped, warning acknowledged) or rejects it."""

import frappe

from rescue_net import api_disaster_admin as da
from rescue_net.services import early_warning as ew
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_posko, make_user
from rescue_net.tests.test_early_warning import payload


class TestBmkgDraftQueue(RNTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_user(roles=("System Manager",))
        self.near = make_posko(make_event(event_status="active"), latitude=-6.3, longitude=106.9)
        ew.process([payload(mag="6.1")])
        self.w = frappe.get_all("RN Early Warning", fields=["name", "draft_event"], order_by="creation desc")[0]

    def test_draft_has_coordinates_type_and_admin_notice(self):
        ev = frappe.db.get_value("RN Disaster Event", self.w.draft_event, ["latitude", "longitude", "event_type"], as_dict=True)
        self.assertAlmostEqual(float(ev.latitude), -6.2, places=3)
        self.assertEqual(ev.event_type, "gempa")
        self.assertTrue(frappe.db.exists("Notification Log", {"for_user": self.admin, "subject": ["like", "%Draf bencana dari BMKG%"]}))

    def test_queue_shows_quake_and_nearby_then_activate(self):
        with as_user(self.admin):
            q = da.admin_queue()
        row = [r for r in q["bmkg_drafts"] if r["name"] == self.w.draft_event][0]
        self.assertEqual(float(row["quake"]["magnitude"]), 6.1)
        self.assertIn(self.near.name, [p["posko"] for p in row["quake"]["nearby"]])
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            da.admin_queue()
        with as_user(self.admin):
            da.review_event(self.w.draft_event, "approve")
        ev = frappe.db.get_value("RN Disaster Event", self.w.draft_event, ["event_status", "title"], as_dict=True)
        self.assertEqual(ev.event_status, "active")
        self.assertFalse(ev.title.startswith("[DRAF BMKG]"))
        self.assertEqual(frappe.db.get_value("RN Early Warning", self.w.name, "status"), "acknowledged")

    def test_reject_dismisses_warning(self):
        with as_user(self.admin):
            da.review_event(self.w.draft_event, "reject")
        self.assertEqual(frappe.db.get_value("RN Disaster Event", self.w.draft_event, "event_status"), "rejected")
        self.assertEqual(frappe.db.get_value("RN Early Warning", self.w.name, "status"), "dismissed")
