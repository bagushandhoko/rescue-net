"""session_info hands back the session's own CSRF token (2026-10-25: a Google-login
session holds one and Frappe refused every POST without it — logout, member approval)."""

import frappe

from rescue_net.api_auth import session_info
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor


class TestSessionCsrf(RNTestCase):
    def test_token_returned_only_when_the_session_has_one(self):
        op = make_actor()
        with as_user(op.user):
            frappe.session.data.pop("csrf_token", None)
            self.assertIsNone(session_info()["csrf_token"])          # never created here
            self.assertNotIn("csrf_token", frappe.session.data)
            frappe.session.data.csrf_token = "tok-uji-123"
            self.assertEqual(session_info()["csrf_token"], "tok-uji-123")
            frappe.session.data.pop("csrf_token", None)

    def test_guest_gets_no_token(self):
        with as_guest():
            self.assertEqual(session_info(), {"user": "Guest"})


class TestAccountMenuFlags(RNTestCase):
    def test_flags_for_plain_member_and_org_owner(self):
        from rescue_net.api_auth import session_info
        from rescue_net.tests.factories import make_actor, make_world
        w = make_world()
        plain = make_actor()
        owner = make_actor(org=w.org_a, org_role="owner")
        with as_user(plain.user):
            s = session_info()
        self.assertFalse(s["is_system_manager"])
        self.assertFalse(s["manages_org"])
        with as_user(owner.user):
            self.assertTrue(session_info()["manages_org"])
