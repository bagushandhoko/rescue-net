"""Check-in/out relawan (Fase 10h): QR berputar, walk-in perlu tinjauan, idempoten offline, append-only, privat."""

from datetime import timedelta

import frappe
from frappe.utils import now_datetime

from rescue_net import api_presence as api
from rescue_net import api_volunteer as vol
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor, make_world


class PresenceBase(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.op_a = make_actor(posko=self.w.posko_a)
        self.op_b = make_actor(posko=self.w.posko_b)
        self.person = make_actor(role="viewer")
        with as_user(self.person.user):
            self.profile = vol.create_profile("Relawan Hadir", "logistik")["volunteer"]

    def checkin(self, posko=None, **kw):
        with as_user(self.person.user):
            return api.check_in((posko or self.w.posko_a).name if not isinstance(posko, str) else posko, **kw)

    def qr_token(self, posko=None):
        with as_user(self.op_a.user):
            return api.posko_qr((posko or self.w.posko_a).name)["token"]


class TestCheckInRules(PresenceBase):
    def test_qr_token_required_to_be_valid_and_app_button_allowed(self):
        with self.assertRaises(frappe.PermissionError):
            self.checkin(token="RNH-salah")
        r = self.checkin(token=self.qr_token())
        self.assertEqual(r["presence"]["posko"], self.w.posko_a.name)
        self.assertEqual(frappe.db.get_value("RN Volunteer Presence", r["presence"]["name"], "method"), "qr")
        r2 = self.checkin(self.w.posko_b)  # tombol aplikasi tanpa QR: boleh (pindah posko)
        self.assertFalse(r2["duplicate"])
        self.assertEqual(frappe.db.get_value("RN Volunteer Presence", r2["presence"]["name"], "method"), "app")

    def test_token_is_posko_specific_and_not_issued_to_outsiders(self):
        tok = self.qr_token()
        with self.assertRaises(frappe.PermissionError):
            self.checkin(self.w.posko_b, token=tok)               # token posko A tak berlaku di posko B
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api.posko_qr(self.w.posko_a.name)                      # pengelola posko lain tak boleh minta token
        with as_user(self.person.user), self.assertRaises(frappe.PermissionError):
            api.posko_qr(self.w.posko_a.name)                      # relawan biasa pun tidak
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api.posko_qr(self.w.posko_a.name)

    def test_assignment_links_otherwise_walk_in_pending_review(self):
        walk = self.checkin()
        self.assertEqual(walk["walk_in"], 1)
        p = frappe.get_doc("RN Volunteer Presence", walk["presence"]["name"])
        self.assertEqual((p.walk_in, p.review_status, p.assignment), (1, "pending", None))
        with as_user(self.person.user):
            api.check_out()
        with as_user(self.op_a.user):
            a = vol.create_assignment(self.profile, self.w.posko_a.name, "Bongkar muat")["assignment"]
        with as_user(self.person.user):
            vol.update_assignment_status(a, "accepted")
        r = self.checkin()
        p2 = frappe.get_doc("RN Volunteer Presence", r["presence"]["name"])
        self.assertEqual((p2.walk_in, p2.assignment), (0, a))
        self.assertEqual(frappe.db.get_value("RN Volunteer Assignment", a, "assignment_status"), "checked_in")

    def test_replay_and_double_checkin_are_idempotent(self):
        a = self.checkin(offline_id="off-1")
        b = self.checkin(offline_id="off-1")
        c = self.checkin()
        self.assertTrue(b["duplicate"] and c["duplicate"])
        self.assertEqual(a["presence"]["name"], b["presence"]["name"])
        self.assertEqual(frappe.db.count("RN Volunteer Presence", {"volunteer": self.profile}), 1)

    def test_distance_is_a_marker_never_a_refusal(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, {"latitude": -6.2, "longitude": 106.8})
        far = self.checkin(latitude=-7.5, longitude=110.0)
        self.assertGreater(far["distance_m"], 100000)              # jauh tetap tercatat
        self.assertEqual(far["ok"], True)

    def test_moving_posko_closes_previous_presence(self):
        first = self.checkin()
        self.checkin(self.w.posko_b)
        old = frappe.get_doc("RN Volunteer Presence", first["presence"]["name"])
        self.assertTrue(old.out_at and old.auto_closed)

    def test_non_volunteer_cannot_check_in(self):
        nobody = make_actor(role="viewer")
        with as_user(nobody.user), self.assertRaises(frappe.PermissionError):
            api.check_in(self.w.posko_a.name)

    def test_offline_time_is_clamped(self):
        future = (now_datetime() + timedelta(days=2)).isoformat()
        r = self.checkin(at=future)
        in_at = frappe.utils.get_datetime(frappe.db.get_value("RN Volunteer Presence", r["presence"]["name"], "in_at"))
        self.assertLess(in_at, now_datetime() + timedelta(minutes=1))


class TestCheckOutAndSite(PresenceBase):
    def test_check_out_and_idempotent_replay(self):
        self.checkin()
        with as_user(self.person.user):
            out = api.check_out(self.w.posko_a.name)
            self.assertTrue(out["presence"]["out_at"])
            with self.assertRaises(frappe.ValidationError):
                api.check_out()                                    # tidak ada check-in aktif
            self.assertTrue(api.check_out(offline_id="o2")["duplicate"])   # replay offline aman

    def test_on_site_is_manager_only_and_counts(self):
        self.checkin()
        with as_user(self.op_a.user):
            s = api.on_site(self.w.posko_a.name)
        self.assertEqual((s["count"], s["walk_in_pending"]), (1, 1))
        self.assertEqual(s["rows"][0]["volunteer_name"], "Relawan Hadir")
        for u in (self.op_b.user, self.person.user):
            with as_user(u), self.assertRaises(frappe.PermissionError):
                api.on_site(self.w.posko_a.name)
        with as_guest(), self.assertRaises(frappe.ValidationError):
            api.on_site(self.w.posko_a.name)

    def test_review_walk_in(self):
        r = self.checkin()
        with as_user(self.op_b.user), self.assertRaises(frappe.PermissionError):
            api.review_walk_in(r["presence"]["name"])
        with as_user(self.op_a.user):
            api.review_walk_in(r["presence"]["name"])
            self.assertEqual(api.on_site(self.w.posko_a.name)["walk_in_pending"], 0)

    def test_stale_presence_auto_closes_after_12_hours(self):
        r = self.checkin()
        frappe.db.set_value("RN Volunteer Presence", r["presence"]["name"], "in_at", now_datetime() - timedelta(hours=13))
        api.close_stale_presence()
        p = frappe.get_doc("RN Volunteer Presence", r["presence"]["name"])
        self.assertTrue(p.auto_closed)
        self.assertEqual(frappe.utils.get_datetime(p.out_at), frappe.utils.get_datetime(p.in_at) + timedelta(hours=12))
        fresh = self.checkin()
        api.close_stale_presence()
        self.assertFalse(frappe.db.get_value("RN Volunteer Presence", fresh["presence"]["name"], "out_at"))


class TestAppendOnly(PresenceBase):
    def test_records_cannot_be_edited_or_deleted(self):
        r = self.checkin()
        p = frappe.get_doc("RN Volunteer Presence", r["presence"]["name"])
        p.posko = self.w.posko_b.name
        with self.assertRaises(frappe.ValidationError):
            p.save(ignore_permissions=True)
        p = frappe.get_doc("RN Volunteer Presence", r["presence"]["name"])
        with self.assertRaises(frappe.ValidationError):
            p.delete()
        with as_user(self.person.user):
            api.check_out()
        p = frappe.get_doc("RN Volunteer Presence", r["presence"]["name"])
        p.out_at = now_datetime() + timedelta(hours=1)
        with self.assertRaises(frappe.ValidationError):
            p.save(ignore_permissions=True)                        # check-out sudah tercatat
