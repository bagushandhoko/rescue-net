"""Kelola Posko hub (owner 2026-11-01): managers only, pending counts, warnings, button gate."""

import frappe

from rescue_net import api_posko_manage as pm
from rescue_net.tests.factories import RNTestCase, _insert, as_guest, as_user, make_actor, make_world


class TestPoskoManage(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.mgr = make_actor(posko=self.w.posko_a)
        self.other = make_actor(posko=self.w.posko_b)

    def test_only_manager_opens_hub(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            pm.manage_hub(self.w.posko_a.name)
        with as_guest(), self.assertRaises(Exception):
            pm.manage_hub(self.w.posko_a.name)
        with as_user(self.mgr.user):
            h = pm.manage_hub(self.w.posko_a.name)
        self.assertEqual(h["posko"], self.w.posko_a.name)
        self.assertTrue(any(t["key"] == "settings" for t in h["tools"]))
        self.assertTrue(any("kontak" in w for w in h["warnings"]))  # factory posko has no phone

    def test_button_gate(self):
        with as_guest():
            self.assertFalse(pm.can_manage(self.w.posko_a.name)["can_manage"])
        with as_user(self.other.user):
            self.assertFalse(pm.can_manage(self.w.posko_a.name)["can_manage"])
        with as_user(self.mgr.user):
            self.assertTrue(pm.can_manage(self.w.posko_a.name)["can_manage"])

    def test_list_and_pending_counts(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "officer_in_charge_phone", "0812-0000-1111")
        rel = make_actor(role="relawan")
        prof = _insert("RN Volunteer Profile", user_account=rel.account, disaster_event=self.w.event.name,
                       volunteer_name="Uji", contact="0812", main_skill="medis")
        _insert("RN Volunteer Booking", booking_kind="posko", status="requested", volunteer=prof.name,
                user_account=rel.account, disaster_event=self.w.event.name, posko=self.w.posko_a.name)
        with as_user(self.mgr.user):
            mine = pm.my_managed_poskos()["poskos"]
            h = pm.manage_hub(self.w.posko_a.name)
        names = [p["posko"] for p in mine]
        self.assertIn(self.w.posko_a.name, names)
        self.assertNotIn(self.w.posko_b.name, names)
        self.assertEqual(h["pending"]["relawan"], 1)
        self.assertFalse(any("kontak" in w for w in h["warnings"]))

    def test_expiring_stock_counted(self):
        from frappe.utils import add_days, nowdate
        from rescue_net.services.expiry import record_lot
        frappe.get_doc({"doctype": "RN Stock Observation", "title": "Oralit uji", "posko": self.w.posko_a.name, "item_name": "Oralit",
                        "unit": "sachet", "quantity": 100, "observed_at": frappe.utils.now_datetime()}).insert(ignore_permissions=True)
        record_lot(self.w.posko_a.name, "Oralit", "sachet", 30, add_days(nowdate(), -1))
        with as_user(self.mgr.user):
            h = pm.manage_hub(self.w.posko_a.name)
        self.assertGreaterEqual(h["pending"]["kedaluwarsa"], 1)
