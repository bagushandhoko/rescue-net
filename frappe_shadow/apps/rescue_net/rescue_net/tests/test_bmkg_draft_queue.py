"""S13 / owner 2026-11-02: a big BMKG quake is an ANNOUNCEMENT (no disaster created). The super admin sees it in
Kelola Bencana with the poskos in range and turns it into a disaster only once it is declared one, or dismisses it."""

import frappe

from rescue_net import api_disaster_admin as da
from rescue_net.services import early_warning as ew
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_posko, make_user
from rescue_net.tests.test_early_warning import payload


class TestBmkgNotices(RNTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_user(roles=("System Manager",))
        self.near = make_posko(make_event(event_status="active"), latitude=-6.3, longitude=106.9)
        ew.process([payload(mag="6.1")])
        self.w = frappe.get_all("RN Early Warning", fields=["name", "draft_event"], order_by="creation desc")[0]

    def test_notice_listed_with_nearby_poskos_and_admin_told(self):
        self.assertFalse(self.w.draft_event)
        self.assertTrue(frappe.db.exists("Notification Log", {"for_user": self.admin, "subject": ["like", "%Pengumuman BMKG%"]}))
        with as_user(self.admin):
            q = da.admin_queue()
        row = [r for r in q["bmkg_notices"] if r["warning"] == self.w.name][0]
        self.assertEqual(float(row["magnitude"]), 6.1)
        self.assertIn(self.near.name, [p["posko"] for p in row["nearby"]])
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            da.admin_queue()

    def test_promote_when_declared(self):
        with as_user(make_actor().user), self.assertRaises(frappe.PermissionError):
            da.promote_warning(self.w.name)
        with as_user(self.admin):
            r = da.promote_warning(self.w.name, title="Gempa Banten 2026")
            with self.assertRaisesRegex(frappe.ValidationError, "sudah dijadikan"):
                da.promote_warning(self.w.name)
            self.assertNotIn(self.w.name, [x["warning"] for x in da.admin_queue()["bmkg_notices"]])
        ev = frappe.db.get_value("RN Disaster Event", r["event"], ["event_status", "title", "event_type", "latitude"], as_dict=True)
        self.assertEqual((ev.event_status, ev.title, ev.event_type), ("active", "Gempa Banten 2026", "gempa"))
        self.assertAlmostEqual(float(ev.latitude), -6.2, places=3)
        self.assertEqual(frappe.db.get_value("RN Early Warning", self.w.name, "status"), "acknowledged")

    def test_dismiss(self):
        with as_user(self.admin):
            da.dismiss_warning(self.w.name)
            self.assertNotIn(self.w.name, [x["warning"] for x in da.admin_queue()["bmkg_notices"]])
        self.assertEqual(frappe.db.get_value("RN Early Warning", self.w.name, "status"), "dismissed")
