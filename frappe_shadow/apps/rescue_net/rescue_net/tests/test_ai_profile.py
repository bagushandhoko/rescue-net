"""RN AI Profile + local-model provider (ADR-0002 section 4, Fase 7 step 1)."""

from unittest import mock

import frappe

from rescue_net import api_ai
from rescue_net.services import llm
from rescue_net.tests.factories import RNTestCase, as_user, contains_value, make_actor, make_org

KEY = "fake-byok-PROFILE-0123456789abcdefWXYZ"


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.ok = data, status, status < 400

    def json(self):
        return self._data


class TestLocalProvider(RNTestCase):
    def test_local_model_uses_the_given_endpoint_without_a_key(self):
        calls = []

        def post(url, headers=None, json=None, timeout=None):
            calls.append((url, headers))
            return _Resp({"choices": [{"message": {"content": "jawab-lokal"}}], "usage": {}})

        with mock.patch.object(llm.requests, "post", post):
            text, usage = llm.chat("local", None, None, "s", ["q"], base_url="http://10.0.0.5:11434/v1/")
        self.assertEqual(text, "jawab-lokal")
        self.assertEqual(calls[0][0], "http://10.0.0.5:11434/v1/chat/completions")
        self.assertNotIn("Authorization", calls[0][1])
        self.assertEqual(usage["total_tokens"], 0)

    def test_local_model_needs_a_valid_endpoint(self):
        with self.assertRaises(llm.LLMError):
            llm.chat("local", None, None, "s", ["q"])
        for bad in ("ftp://x/v1", "http://169.254.169.254/latest", "http://u:p@host/v1",
                    "http://metadata.google.internal/", "not a url", ""):
            with self.assertRaises(llm.LLMError, msg=bad):
                llm.validate_base_url(bad)

    def test_base_url_is_ignored_for_cloud_providers(self):
        calls = []

        def post(url, headers=None, json=None, timeout=None):
            calls.append(url)
            return _Resp({"choices": [{"message": {"content": "x"}}], "usage": {}})

        with mock.patch.object(llm.requests, "post", post):
            llm.chat("openai", KEY, None, "s", ["q"], base_url="http://evil.local/v1")
        self.assertEqual(calls, ["https://api.openai.com/v1/chat/completions"])

    def test_local_is_not_a_byok_key_provider(self):
        self.assertNotIn("local", [c["provider"] for c in llm.catalog()])
        me = make_actor()
        with as_user(me.user), self.assertRaises(frappe.ValidationError):
            api_ai.save_user_key(me.user, KEY, provider="local")


class TestProfiles(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.admin = make_actor(org=self.org, org_role="owner")
        self.member = make_actor(org=self.org, org_role="member")
        self.other = make_actor()

    def test_personal_profile_needs_own_active_key_and_never_returns_it(self):
        with as_user(self.other.user):
            with self.assertRaises(frappe.ValidationError):
                api_ai.save_ai_profile("personal", self.other.user, provider="anthropic")
            api_ai.save_user_key(self.other.user, KEY, provider="anthropic")
            out = api_ai.save_ai_profile("personal", self.other.user, provider="anthropic",
                                         allowed_tools=["ringkas_tugas"], daily_budget_tokens=1000,
                                         monthly_budget_tokens=20000)
        p = out["profile"]
        self.assertEqual((p["data_scope"], p["model_name"], p["has_key"]),
                         ("user_permission", "claude-opus-5", True))
        self.assertEqual(p["allowed_tools"], ["ringkas_tugas"])
        self.assertFalse(contains_value(out, KEY))

    def test_nobody_edits_someone_elses_profile(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_ai_profile("personal", self.member.user, provider="openai")
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            api_ai.get_ai_profile("personal", self.member.user)

    def test_organisation_profile_is_for_org_admins_and_uses_the_org_key(self):
        with as_user(self.admin.user):
            api_ai.save_org_key(self.org.name, KEY, provider="openai")
            out = api_ai.save_ai_profile("organization", self.org.name, provider="openai")
        self.assertEqual(out["profile"]["data_scope"], "organization")
        with as_user(self.member.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_ai_profile("organization", self.org.name, provider="openai")
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            api_ai.get_ai_profile("organization", self.org.name)
        # a personal key is never the key of the organisation profile
        with as_user(self.admin.user):
            api_ai.save_user_key(self.admin.user, KEY, provider="gemini")
            with self.assertRaises(frappe.ValidationError):
                api_ai.save_ai_profile("organization", self.org.name, provider="gemini")

    def test_platform_profile_is_system_manager_only(self):
        with as_user(self.admin.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_ai_profile("platform", None, provider="openai")
        api_ai.save_platform_key(KEY, provider="openai")  # Administrator
        out = api_ai.save_ai_profile("platform", None, provider="openai")
        self.assertEqual((out["profile"]["owner_id"], out["profile"]["data_scope"]), ("__platform__", "aggregate"))

    def test_local_endpoint_rules(self):
        with as_user(self.other.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_ai_profile("personal", self.other.user, provider="local", base_url="http://10.0.0.5/v1")
        with as_user(self.admin.user):
            with self.assertRaises(frappe.ValidationError):
                api_ai.save_ai_profile("organization", self.org.name, provider="local",
                                       base_url="http://169.254.169.254/")
            out = api_ai.save_ai_profile("organization", self.org.name, provider="local",
                                         base_url="http://10.0.0.5:11434/v1/")
        self.assertEqual((out["profile"]["base_url"], out["profile"]["has_key"]),
                         ("http://10.0.0.5:11434/v1", False))

    def test_direct_save_keeps_the_rules(self):
        def new(**f):
            return frappe.get_doc({"doctype": "RN AI Profile", "level": "organization",
                                   "owner_id": self.org.name, "provider": "local",
                                   "base_url": "http://10.0.0.5/v1", **f})
        for bad in ({"daily_budget_tokens": -1}, {"daily_budget_tokens": 50, "monthly_budget_tokens": 10},
                    {"allowed_tools": "{not json"}, {"allowed_tools": '["Drop Table"]'}):
            with self.assertRaises(frappe.ValidationError, msg=str(bad)):
                new(**bad).insert(ignore_permissions=True)
        doc = new().insert(ignore_permissions=True)
        self.assertEqual(doc.data_scope, "organization")
