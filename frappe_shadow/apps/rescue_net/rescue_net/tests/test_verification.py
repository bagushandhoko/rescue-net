"""Verification decisions (phase 2: VF-1, VF-2)."""

import frappe

from rescue_net.tests.factories import RNTestCase, api_call, as_user, make_actor, make_world

APPROVE = "rescue_net.api_verification.approval_action"


class TestRoleRequests(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.requester = make_actor(role="viewer")
        frappe.db.set_value("RN User Account", self.requester.account, {
            "requested_role": "command_center", "role_request_status": "pending",
        })
        self.operator = make_actor(posko=self.w.posko_b)

    def test_operator_cannot_approve_a_role_request(self):
        with as_user(self.operator.user), self.assertRaises(frappe.PermissionError):
            api_call(APPROVE, kind="user", name=self.requester.account, action="approve")
        self.assertEqual(frappe.db.get_value("RN User Account", self.requester.account, "role"), "viewer")

    def test_system_manager_approves_a_role_request(self):
        api_call(APPROVE, kind="user", name=self.requester.account, action="approve")
        self.assertEqual(frappe.db.get_value("RN User Account", self.requester.account, "role"), "command_center")

    def test_direct_save_of_a_role_change_needs_system_manager(self):
        doc = frappe.get_doc("RN User Account", self.requester.account)
        doc.role = "command_center"
        with as_user(self.operator.user), self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)


class TestPoskoVerification(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.own_op = make_actor(org=self.w.org_a, posko=self.w.posko_a)
        self.other_op = make_actor(org=self.w.org_b, posko=self.w.posko_b)

    def status(self):
        return frappe.db.get_value("RN Posko", self.w.posko_a.name, "verification_status")

    def test_operator_cannot_verify_own_posko(self):
        with as_user(self.own_op.user), self.assertRaises(frappe.PermissionError):
            api_call(APPROVE, kind="posko", name=self.w.posko_a.name, action="approve")
        self.assertNotEqual(self.status(), "official_verified")

    def test_other_organisation_operator_may_verify(self):
        with as_user(self.other_op.user):
            api_call(APPROVE, kind="posko", name=self.w.posko_a.name, action="approve")
        self.assertEqual(self.status(), "official_verified")

    def test_decided_item_is_not_re_decided_by_an_operator(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "verification_status", "rejected")
        with as_user(self.other_op.user), self.assertRaises(frappe.PermissionError):
            api_call(APPROVE, kind="posko", name=self.w.posko_a.name, action="approve")
        self.assertEqual(self.status(), "rejected")


def make_verifier(actor, trust_level=2, status="active"):
    from rescue_net.tests.factories import _insert, uid
    return _insert(
        "RN Verifier Profile", title=uid("Verifikator"), user=actor.account,
        verifier_type="community_leader", verifier_status=status, trust_level=trust_level,
        wilayah="Meulaboh Aceh Barat",
    )


class TestEndorsements(RNTestCase):
    """VF-3..VF-6."""

    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.insider = make_actor(org=self.w.org_a, posko=self.w.posko_a)
        self.insider_v = make_verifier(self.insider)
        self.outsider = make_actor(org=self.w.org_b)
        self.outsider_v = make_verifier(self.outsider)

    def endorse(self, who, **kw):
        with as_user(who.user):
            return api_call("rescue_net.api_verifier.endorse_posko", posko=self.w.posko_a.name, **kw)

    def test_verifier_cannot_endorse_own_posko(self):
        with self.assertRaises(frappe.PermissionError):
            self.endorse(self.insider)

    def test_outside_verifier_endorses(self):
        out = self.endorse(self.outsider)
        self.assertEqual(out["verification_status"], "community_verified")

    def test_suspended_verifier_endorsement_stops_counting(self):
        from rescue_net.api_verifier import _recompute_posko_credibility
        self.endorse(self.outsider)
        frappe.db.set_value("RN Verifier Profile", self.outsider_v.name, "verifier_status", "suspended")
        out = _recompute_posko_credibility(self.w.posko_a.name)
        self.assertEqual(out["trusted_verifier_count"], 0)
        self.assertEqual(out["verification_status"], "self_reported")

    def test_endorsement_does_not_overrule_a_rejection(self):
        frappe.db.set_value("RN Posko", self.w.posko_a.name, "verification_status", "rejected")
        self.assertEqual(self.endorse(self.outsider)["verification_status"], "rejected")

    def test_admin_official_status_survives_without_endorsements(self):
        from rescue_net.api_verifier import _recompute_posko_credibility
        frappe.db.set_value("RN Posko", self.w.posko_a.name,
                            {"verification_status": "official_verified", "trusted_verifier_count": 0})
        self.assertEqual(_recompute_posko_credibility(self.w.posko_a.name)["verification_status"],
                         "official_verified")

    def test_request_cannot_name_the_poskos_own_verifier(self):
        with as_user(self.insider.user), self.assertRaises(frappe.ValidationError):
            api_call("rescue_net.api_verifier.request_posko_verification",
                     posko=self.w.posko_a.name, verifier=self.insider_v.name)

    def test_endorsement_must_match_its_open_request(self):
        with as_user(self.insider.user):
            req = api_call("rescue_net.api_verifier.request_posko_verification",
                           posko=self.w.posko_a.name, verifier=self.outsider_v.name)["request"]
        with as_user(self.outsider.user), self.assertRaises(frappe.ValidationError):
            api_call("rescue_net.api_verifier.endorse_posko", request=req, posko=self.w.posko_b.name)
        self.endorse(self.outsider, request=req)
        frappe.db.set_value("RN Verification Endorsement", {"request": req}, "status", "revoked")
        with as_user(self.outsider.user), self.assertRaises(frappe.ValidationError):
            api_call("rescue_net.api_verifier.endorse_posko", request=req)

    def test_sponsor_limits(self):
        sponsee = make_verifier(make_actor(), trust_level=0, status="pending")
        approve = "rescue_net.api_verifier.approve_verifier"
        with as_user(self.outsider.user):
            with self.assertRaises(frappe.PermissionError):
                api_call(approve, verifier=sponsee.name, trust_level=2)      # = own level
            with self.assertRaises(frappe.PermissionError):
                api_call(approve, verifier=self.outsider_v.name)              # self
            self.assertEqual(api_call(approve, verifier=sponsee.name)["trust_level"], 1)
            api_call(approve, verifier=sponsee.name, action="revoke")
            with self.assertRaises(frappe.PermissionError):
                api_call(approve, verifier=sponsee.name)                      # revive revoked
