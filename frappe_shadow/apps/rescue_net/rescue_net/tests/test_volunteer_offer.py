"""Relawan Saya (owner 2026-11-01): offer to work at a posko, own profile edit, and the
public volunteer board shows names + phone only after login."""

import frappe

from rescue_net import api_volunteer as av
from rescue_net import api_volunteer_booking as vb
from rescue_net.tests.factories import (RNTestCase, as_guest, as_user, make_actor, make_event, make_posko,
                                        make_world)


class TestVolunteerOffer(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Disaster Event", self.w.event.name, "event_status", "active")
        self.rel = make_actor(role="relawan")
        with as_user(self.rel.user):
            vb.offer_events([self.w.event.name], contact="0812-7777-1234", main_skill="medis")
        self.prof = frappe.db.get_value("RN Volunteer Profile", {"user_account": self.rel.account}, "name")

    def test_offer_to_posko_and_posko_accepts(self):
        with as_user(self.rel.user):
            opts = vb.booking_options(self.w.event.name)
            self.assertIn(self.w.posko_a.name, [p["id"] for p in opts["posko"]])
            b = vb.book("posko", self.w.posko_a.name, self.w.event.name, note="bisa mulai besok")["booking"]
            with self.assertRaisesRegex(frappe.ValidationError, "sudah menawarkan"):
                vb.book("posko", self.w.posko_a.name, self.w.event.name)
        # another posko cannot decide
        with as_user(make_actor(posko=self.w.posko_b).user), self.assertRaises(frappe.PermissionError):
            vb.decide_booking(b, "confirm")
        with as_user(make_actor(posko=self.w.posko_a).user):
            mine = vb.posko_bookings(self.w.posko_a.name)["bookings"]
            self.assertEqual(mine[0]["contact"], "0812-7777-1234")
            self.assertEqual(vb.decide_booking(b, "confirm")["status"], "confirmed")
        asg = frappe.db.get_value("RN Volunteer Booking", b, "assignment")
        self.assertTrue(asg)
        self.assertEqual(frappe.db.get_value("RN Volunteer Assignment", asg, ["posko", "assignment_status"]),
                         (self.w.posko_a.name, "accepted"))
        prof = frappe.db.get_value("RN Volunteer Profile", self.prof, ["availability_status", "assigned_posko"])
        self.assertEqual(prof, ("assigned", self.w.posko_a.name))

    def test_posko_of_other_disaster_rejected(self):
        other = make_posko(make_event(event_status="active"), self.w.org_a)
        with as_user(self.rel.user), self.assertRaisesRegex(frappe.ValidationError, "tidak melayani"):
            vb.book("posko", other.name, self.w.event.name)

    def test_update_my_profile_all_profiles(self):
        ev2 = make_event(event_status="active")
        with as_user(self.rel.user):
            vb.offer_events([self.w.event.name, ev2.name])
            r = vb.update_my_profile(equipment_owned="P3K, senter", availability_schedule="Sabtu-Minggu",
                                     needs_pickup="1", contact="0812-7777-9999")
        self.assertEqual(r["profile"]["equipment_owned"], "P3K, senter")
        rows = frappe.get_all("RN Volunteer Profile", filters={"user_account": self.rel.account},
                              fields=["equipment_owned", "needs_pickup", "contact"])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(x.equipment_owned == "P3K, senter" and x.needs_pickup == 1 and x.contact == "0812-7777-9999"
                            for x in rows))
        with as_user(self.rel.user), self.assertRaisesRegex(frappe.ValidationError, "wajib"):
            vb.update_my_profile(contact="")

    def test_board_hides_name_and_phone_from_guest(self):
        with as_user(self.rel.user):
            vb.update_my_profile(equipment_owned="Perahu karet", availability_schedule="24 jam")
        with as_guest():
            g = av.volunteer_board(self.w.event.name)
        self.assertFalse(g["logged_in"])
        row = [r for r in g["relawan_tersedia"] if r["name"] == self.prof][0]
        self.assertEqual(row["volunteer_name"], av.GUEST_VOLUNTEER_NAME)
        self.assertIsNone(row["kontak"])
        self.assertEqual(row["peralatan"], "Perahu karet")       # what they offer stays public
        self.assertEqual(row["jadwal_tersedia"], "24 jam")
        blob = frappe.as_json(g)
        self.assertNotIn("0812-7777-1234", blob)
        real = frappe.db.get_value("RN Volunteer Profile", self.prof, "volunteer_name")
        if real:
            self.assertNotIn(real, blob)
        with as_guest():
            d = av.dashboard()
        self.assertNotIn("0812-7777-1234", frappe.as_json(d))

        with as_user(make_actor().user):
            u = av.volunteer_board(self.w.event.name)
        row = [r for r in u["relawan_tersedia"] if r["name"] == self.prof][0]
        self.assertEqual(row["kontak"], "0812-7777-1234")
        self.assertNotEqual(row["volunteer_name"], av.GUEST_VOLUNTEER_NAME)
