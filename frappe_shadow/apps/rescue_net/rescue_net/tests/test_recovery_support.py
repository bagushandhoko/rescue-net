"""Owner 2026-11-03: Recovery — a tool links to its provider + contact person; tool owners offer tools
(hibah / pinjam / sewa, usable date range, operator included or not, mobilisation needs); recovery projects
publish volunteer needs and volunteers sign up."""

import frappe
from frappe.utils import add_days, getdate

from rescue_net import api_recovery_support as api
from rescue_net.tests.factories import (RNTestCase, _insert, api_call, as_guest, as_user, make_actor, make_event,
                                        make_org)


class TestToolOffers(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        self.org_owner = make_actor(org=self.org, org_role="owner")
        self.person = make_actor(role="citizen")
        self.other = make_actor(role="citizen")

    def offer(self, **kw):
        args = dict(disaster_event=self.event.name, resource_name="Ekskavator PC200", category="ekskavator",
                    quantity=1, unit="unit", available_from=str(getdate()), available_until=str(add_days(getdate(), 30)),
                    offer_type="pinjam", operator_included=1, operator_count=2, support_operator=1,
                    support_transport=1, support_fuel=1, support_accommodation=1,
                    mobilization_needs="Butuh lowbed 20 ton + izin jalan", mobilization_cost=7_500_000,
                    pic_name="Pak Budi", pic_phone="081234500001", pic_email="Budi@Contoh.org",
                    current_location="Meulaboh")
        args.update(kw)
        return api.offer_tool(**args)["resource_profile"]

    def test_individual_offer_and_contact_rules(self):
        with as_user(self.person.user):
            rp = self.offer()
        row = frappe.db.get_value("RN Resource Profile", rp, ["owner_type", "owner_id", "support_operator",
                                                              "pic_email", "offered_by_user"], as_dict=True)
        self.assertEqual((row.owner_type, row.owner_id), ("individual", self.person.account))
        self.assertEqual(row.support_operator, 0)          # comes with operator → does not need one
        self.assertEqual(row.pic_email, "budi@contoh.org")
        with as_guest():
            d = api_call("rescue_net.api_recovery_support.tool_detail", resource_profile=rp)
        self.assertTrue(d["found"])
        self.assertEqual(d["provider"]["label"], "Perorangan")       # a private person's name stays private
        self.assertTrue(d["contact"]["available"])
        self.assertIsNone(d["contact"]["phone"])                     # guest: contact hidden
        self.assertEqual(d["operator_count"], 2)
        self.assertIn("lowbed", d["mobilization_needs"])
        with as_user(self.other.user):
            d = api.tool_detail(rp)
        self.assertEqual(d["contact"]["phone"], "081234500001")      # logged-in account sees the PIC
        self.assertTrue(d["contact"]["whatsapp_url"].startswith("https://wa.me/62"))
        self.assertFalse(d["can_manage"])
        with as_user(self.person.user):
            api.update_tool_offer(rp, contact_public=1)
        with as_guest():
            d = api_call("rescue_net.api_recovery_support.tool_detail", resource_profile=rp)
        self.assertEqual(d["contact"]["phone"], "081234500001")      # owner chose to publish it

    def test_org_offer_links_to_the_org_page(self):
        with as_user(self.person.user), self.assertRaises(frappe.PermissionError):
            self.offer(owner_type="organization", organization=self.org.name)
        with as_user(self.org_owner.user):
            rp = self.offer(owner_type="organization", organization=self.org.name)
            self.offer(owner_type="organization", organization=self.org.name, resource_name="Genset 50 kVA",
                       category="genset")
            mine = api.my_tools()["tools"]
        self.assertEqual(len(mine), 2)
        with as_guest():
            d = api_call("rescue_net.api_recovery_support.tool_detail", resource_profile=rp)
        self.assertEqual(d["provider"]["href"], f"organisasi-posko.html?org={self.org.name}")
        self.assertEqual([t["resource_name"] for t in d["other_tools"]], ["Genset 50 kVA"])

    def test_bad_values_and_owner_only(self):
        with as_user(self.person.user):
            for bad in ({"available_from": str(add_days(getdate(), 5)), "available_until": str(getdate())},
                        {"offer_type": "jual"}, {"quantity": 0}, {"pic_email": "bukan"}, {"category": "x"},
                        {"mobilization_cost": -1}, {"resource_name": ""}):
                with self.assertRaises(frappe.ValidationError, msg=str(bad)):
                    self.offer(**bad)
            rp = self.offer()
        with as_user(self.other.user):
            with self.assertRaises(frappe.PermissionError):
                api.update_tool_offer(rp, quantity=3)
            with self.assertRaises(frappe.PermissionError):
                api.withdraw_tool(rp)
        with as_guest(), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_recovery_support.offer_tool", disaster_event=self.event.name, resource_name="x")
        with as_user(self.person.user):
            api.withdraw_tool(rp)
        self.assertEqual(frappe.db.get_value("RN Resource Profile", rp, "availability_status"), "unavailable")


class TestRecoveryVolunteers(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        self.org = make_org(verification_status="verified")
        from rescue_net.tests.factories import make_posko
        posko = make_posko(self.event, self.org)
        self.owner = make_actor(org=self.org, org_role="owner", posko=posko)
        self.vol1 = make_actor(role="citizen", phone="081200000001")
        self.vol2 = make_actor(role="citizen")
        self.project = _insert("RN Recovery Project", disaster_event=self.event.name, project_name="Rehab SD 3",
                               owner_type="organization", owner_id=self.org.name, status="planned",
                               location="Samatiga").name

    def need(self, n=1):
        with as_user(self.owner.user):
            return api.create_volunteer_need(self.project, "Tukang kayu", people_needed=n,
                                             date_from=str(getdate()), date_to=str(add_days(getdate(), 6)),
                                             provisions="Konsumsi + tempat menginap")["need"]

    def test_only_the_project_owner_creates_needs(self):
        with as_user(self.vol1.user), self.assertRaises(frappe.PermissionError):
            api.create_volunteer_need(self.project, "Tukang", people_needed=2)
        with as_user(self.owner.user), self.assertRaises(frappe.ValidationError):
            api.create_volunteer_need(self.project, "Tukang", people_needed=0)
        n = self.need(2)
        self.assertEqual(frappe.db.get_value("RN Recovery Volunteer Need", n, "location"), "Samatiga")

    def test_signup_confirm_fills_and_reopens(self):
        n = self.need(1)
        with as_user(self.vol1.user):
            s1 = api.signup_volunteer_need(n, skill="kayu")["signup"]
            with self.assertRaises(frappe.ValidationError):
                api.signup_volunteer_need(n)                       # twice
        with as_user(self.vol2.user), self.assertRaises(frappe.ValidationError):
            api.signup_volunteer_need(n)                           # no phone on the account / form
        with as_user(self.vol2.user):
            s2 = api.signup_volunteer_need(n, phone="081299990000")["signup"]
            with self.assertRaises(frappe.PermissionError):
                api.need_signups(n)                                # volunteers cannot read the list
            with self.assertRaises(frappe.PermissionError):
                api.decide_signup(s1, "confirmed")
        with as_guest():
            board = api_call("rescue_net.api_recovery_support.volunteer_needs", disaster_event=self.event.name)
        row = board["needs"][0]
        self.assertEqual((row["requested"], row["confirmed"], row["remaining"]), (2, 0, 1))
        self.assertNotIn("081200000001", frappe.as_json(board))
        with as_user(self.owner.user):
            listed = api.need_signups(n)["signups"]
            self.assertEqual(listed[0]["phone"], "081200000001")
            api.decide_signup(s1, "confirmed")
        self.assertEqual(frappe.db.get_value("RN Recovery Volunteer Need", n, "need_status"), "filled")
        with as_user(self.vol2.user):
            api.cancel_my_signup(s2)
            with self.assertRaises(frappe.ValidationError):
                api.signup_volunteer_need(n, phone="081299990000")   # filled → refused
        with as_user(self.vol1.user):
            api.cancel_my_signup(s1)
        self.assertEqual(frappe.db.get_value("RN Recovery Volunteer Need", n, "need_status"), "open")
        with as_user(self.owner.user):
            api.update_volunteer_need(n, need_status="closed")
        self.assertEqual(frappe.db.get_value("RN Recovery Volunteer Need", n, "need_status"), "closed")
