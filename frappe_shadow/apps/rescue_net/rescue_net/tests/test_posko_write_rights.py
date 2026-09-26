"""Posko data, stock and resource-request writes need the right owner (phase 2: O-7, L-23, L-24)."""

import frappe
from frappe.utils import now_datetime

from rescue_net import api_control_centre as cc
from rescue_net import api_frontend_bridge as bridge
from rescue_net import api_logistics as api
from rescue_net.tests.factories import _insert, as_user, uid
from rescue_net.tests.test_logistics_chain import LogisticsTestCase

ITEM = "Air mineral"


class TestPoskoWriteRights(LogisticsTestCase):
    def setUp(self):
        super().setUp()
        self.obs = _insert("RN Stock Observation", title=f"{ITEM} - uji", posko=self.w.posko_a.name,
                           item_name=ITEM, quantity=40, unit="dus", quantity_mode="exact",
                           stock_state="available", observed_at=now_datetime())

    def refused(self, fn, *args, users=None, **kw):
        for actor in users or (self.outsider, self.member_a, self.op_b):
            with as_user(actor.user), self.assertRaises(frappe.PermissionError):
                fn(*args, **kw)

    def test_beneficiary_count_only_by_posko_operators(self):
        self.refused(cc.set_posko_beneficiary, self.w.posko_a.name, 120)
        with as_user(self.op_a.user):
            cc.set_posko_beneficiary(self.w.posko_a.name, 120)
            with self.assertRaises(frappe.ValidationError):
                cc.set_posko_beneficiary(self.w.posko_a.name, -5)
        self.assertEqual(frappe.db.get_value("RN Posko", self.w.posko_a.name, "rn_beneficiary_count"), 120)

    def test_daily_consumption_only_by_posko_operators(self):
        self.refused(cc.set_item_consumption, self.w.posko_a.name, ITEM, 3)
        with as_user(self.op_a.user):
            cc.set_item_consumption(self.w.posko_a.name, ITEM, 3)
            with self.assertRaises(frappe.ValidationError):
                cc.set_item_consumption(self.w.posko_a.name, ITEM, -1)

    def test_org_member_may_regroup_but_not_rewrite_stock_quantity(self):
        with as_user(self.member_a.user):
            api.correct_item_normalization("RN Stock Observation", self.obs.name, canonical_group="air")
            with self.assertRaises(frappe.PermissionError):
                api.correct_item_normalization("RN Stock Observation", self.obs.name, quantity=400)
        self.assertEqual(frappe.db.get_value("RN Stock Observation", self.obs.name, "quantity"), 40)
        with as_user(self.op_a.user):
            api.correct_item_normalization("RN Stock Observation", self.obs.name, quantity=38)
        self.assertEqual(frappe.db.get_value("RN Stock Observation", self.obs.name, "quantity"), 38)

    def request_for(self, owner_type, owner_id):
        profile = _insert("RN Resource Profile", owner_type=owner_type, owner_id=owner_id,
                          resource_name="Perahu karet", resource_type="vehicle",
                          availability_status="available")
        return _insert("RN Resource Request", sync_event_id=uid("sync"), resource_profile=profile.name,
                       requested_by_type="posko", requested_by_id=self.w.posko_b.name,
                       request_status="requested")

    def test_resource_request_approved_by_the_resource_owner_only(self):
        req = self.request_for("posko", self.w.posko_a.name)
        self.refused(bridge.approve_resource_request, req.name)
        with as_user(self.op_a.user):
            bridge.approve_resource_request(req.name)
        self.assertEqual(frappe.db.get_value("RN Resource Request", req.name, "request_status"), "approved")

    def test_org_resource_approved_by_org_owner(self):
        req = self.request_for("organization", self.w.org_a.name)
        self.refused(bridge.approve_resource_request, req.name, users=(self.member_a, self.op_b))
        with as_user(self.owner_a.user):
            bridge.approve_resource_request(req.name)
