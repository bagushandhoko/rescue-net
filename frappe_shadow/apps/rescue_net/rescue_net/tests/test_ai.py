"""AI: a BYOK key never appears in any response, other users cannot manage
someone else's key, and the public AI context is scrubbed."""

import frappe
from frappe.utils import now_datetime

from rescue_net import api_ai
from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    api_call,
    as_guest,
    as_user,
    contains_value,
    make_actor,
    make_medical_case,
    make_posko,
    make_world,
    walk,
)

USER_KEY = "fake-byok-USERKEY-0123456789abcdefWXYZ"
ORG_KEY = "fake-byok-ORGKEY-0123456789abcdefQRST"
PHONE = "+62811-0000-5555"
EMAIL = "pic.rahasia@test.rescue-net.local"


class TestByokKey(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        self.me = make_actor()
        self.other = make_actor()
        self.org_owner = make_actor(org=self.w.org_a, org_role="owner")
        self.org_member = make_actor(org=self.w.org_a, org_role="member")

    def save_mine(self):
        with as_user(self.me.user):
            return api_ai.save_user_key(self.me.user, USER_KEY, api_key_label="uji")

    def test_key_is_not_returned_on_save_or_status(self):
        saved = self.save_mine()
        self.assertFalse(contains_value(saved, USER_KEY))
        with as_user(self.me.user):
            status = api_ai.get_user_key_status(self.me.user)
            info = api_ai.session_info()
            model = api_ai.update_user_model(self.me.user, "gpt-4o-mini")
            usage = api_ai.ai_usage_summary(user_id=self.me.user)
        self.assertTrue(status["key_exists"])
        self.assertEqual(status["masked_key"], "****" + USER_KEY[-4:])
        for response in (status, info, model, usage):
            self.assertFalse(contains_value(response, USER_KEY), response)
            self.assertFalse(contains_value(response, USER_KEY[:-4]), response)

    def test_key_is_stored_encrypted(self):
        self.save_mine()
        name = api_ai._setting_name(self.me.user, "openai")
        raw = frappe.db.sql("select api_key from `tabRN AI User Setting` where name=%s", name)[0][0]
        self.assertNotEqual(raw, USER_KEY)
        self.assertNotIn("USERKEY", raw or "")
        # ...but it is still recoverable for the provider call
        self.assertEqual(frappe.get_doc("RN AI User Setting", name).get_password("api_key"), USER_KEY)

    def test_other_user_cannot_read_or_change_my_key(self):
        self.save_mine()
        with as_user(self.other.user):
            for fn, args in (
                (api_ai.get_user_key_status, (self.me.user,)),
                (api_ai.update_user_model, (self.me.user, "x")),
                (api_ai.delete_user_key, (self.me.user,)),
                (api_ai.save_user_key, (self.me.user, "fake-byok-attacker-000000000000000000")),
            ):
                with self.assertRaises(frappe.PermissionError):
                    fn(*args)

    def test_guest_cannot_call_key_endpoints(self):
        for fn in ("save_user_key", "get_user_key_status", "delete_user_key",
                   "save_org_key", "get_org_key_status", "test_ai_key", "ask", "context"):
            with as_guest(), self.assertRaises(frappe.PermissionError):
                api_call(f"rescue_net.api_ai.{fn}", user_id=self.me.user)

    def test_org_key_admin_only_and_never_returned(self):
        with as_user(self.org_member.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_org_key(self.w.org_a.name, ORG_KEY)
        with as_user(self.org_owner.user):
            saved = api_ai.save_org_key(self.w.org_a.name, ORG_KEY)
            status = api_ai.get_org_key_status(self.w.org_a.name)
        self.assertTrue(status["key_exists"])
        for response in (saved, status):
            self.assertFalse(contains_value(response, ORG_KEY), response)
        with as_user(self.org_member.user), self.assertRaises(frappe.PermissionError):
            api_ai.get_org_key_status(self.w.org_a.name)


class TestPublicAiContext(RNTestCase):
    def setUp(self):
        super().setUp()
        self.w = make_world()
        frappe.db.set_value("RN Posko", self.w.posko_a.name, {
            "officer_in_charge_phone": PHONE,
            "officer_in_charge_email": EMAIL,
        })
        self.med = make_posko(self.w.event, self.w.org_a, posko_type="medical")
        make_medical_case(self.med, patient_code="PX-AI-RAHASIA", disaster_event=self.w.event.name)
        _insert("RN Missing Person Report", disaster_event=self.w.event.name, posko=self.w.posko_a.name,
                person_code="MP-AI-01", person_name="Nama AI Rahasia", report_status="missing",
                observed_at=now_datetime())
        _insert("RN Aid Offer", title="Donasi uji", disaster_event=self.w.event.name,
                target_posko=self.w.posko_a.name, donor_name="Donatur Uji", donor_contact=PHONE,
                item_name="Beras", quantity=5, unit="karung", offer_status="available")
        with as_user(make_actor().user):
            api_ai.save_user_key(frappe.session.user, USER_KEY)

    def public(self):
        with as_guest():
            return api_call("rescue_net.api_ai.public_context", disaster_event_id=self.w.event.name)

    def test_public_context_has_no_contact_or_secret_keys(self):
        data = self.public()
        self.assertTrue(data)
        blocked = ("phone", "email", "contact", "password", "token", "secret", "api_key")
        leaked = [f"{p}.{k}" for p, k, _v in walk(data) if any(b in str(k).lower() for b in blocked)]
        self.assertEqual(leaked, [])
        for secret in (PHONE, EMAIL, USER_KEY):
            self.assertFalse(contains_value(data, secret), secret)

    def test_public_context_has_no_person_identity(self):
        data = self.public()
        self.assertFalse(contains_value(data, "Nama AI Rahasia"))
        self.assertFalse(any(k in ("person_name", "treatment_notes") for _p, k, _v in walk(data)))

    def test_unscrubbed_builder_is_not_http_callable(self):
        """BUG-4 (fixed 2026-09-26): _build_context(public=True) returns data
        before _public_scrub, so it must not be reachable over HTTP."""
        outsider = make_actor(role="viewer")
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            api_call("rescue_net.api_ai._build_context", disaster_event_id=self.w.event.name, public=1)
