"""Fase 7 step 2: key resolution per context, budgets, kill switch, rate limit,
usage rollup and 7-day retention (ADR-0002 sections 5 and 8)."""

from unittest import mock

import frappe
from frappe.utils import add_days, now_datetime

from rescue_net import api_ai
from rescue_net.ai import budget
from rescue_net.services import llm, report_intake
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org

KEY = "fake-byok-BUDGET-0123456789abcdefWXYZ"
ORG_KEY = "fake-byok-ORGKEY-0123456789abcdefWXYZ"


class _Resp:
    status_code, ok = 200, True

    def __init__(self, tokens=100):
        self.tokens = tokens

    def json(self):
        return {"choices": [{"message": {"content": "jawab"}}],
                "usage": {"prompt_tokens": self.tokens, "completion_tokens": 0, "total_tokens": self.tokens}}


def _post(tokens=100):
    return mock.patch.object(llm.requests, "post", lambda *a, **k: _Resp(tokens))


class Base(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.other_org = make_org()
        self.owner = make_actor(org=self.org, org_role="owner")
        self.member = make_actor(org=self.org, org_role="member")
        self.event = make_event()

    def ask(self, user, **kw):
        with as_user(user):
            return api_ai.ask(user, self.event.name, "Ringkas situasi", **kw)


class TestContextResolution(Base):
    def test_a_member_without_a_personal_key_does_not_borrow_the_org_key_by_accident(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
        with as_user(self.member.user):
            self.assertIsNone(api_ai.resolve_ai(self.member.user, "auto"))
            org = api_ai.resolve_ai(self.member.user, "auto", self.org.name)
        self.assertEqual((org["api_key"], org["owner_type"], org["owner_id"]), (ORG_KEY, "organization", self.org.name))
        with as_user(self.member.user), self.assertRaises(frappe.ValidationError):
            self.ask(self.member.user)  # personal context, no personal key

    def test_org_context_uses_only_the_org_key_never_personal_or_platform(self):
        with as_user(self.member.user):
            api_ai.save_user_key(self.member.user, KEY, provider="openai")
        api_ai.save_platform_key(KEY + "P", provider="openai")
        with as_user(self.member.user):
            self.assertIsNone(api_ai.resolve_ai(self.member.user, "auto", self.org.name))

    def test_nobody_uses_the_key_of_an_org_they_do_not_belong_to(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
        outsider = make_actor(org=self.other_org)
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            api_ai.resolve_ai(outsider.user, "auto", self.org.name)
        with as_user(outsider.user), self.assertRaises(frappe.PermissionError):
            api_ai.ask(outsider.user, self.event.name, "x", organization_id=self.org.name)

    def test_ai_contexts_lists_what_the_user_can_use(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
        with as_user(self.member.user):
            c = api_ai.ai_contexts()
        self.assertFalse(c["personal"]["available"])
        self.assertEqual([o["id"] for o in c["organizations"]], [self.org.name])

    def test_profile_selects_the_provider_for_auto(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY, provider="openai")
            api_ai.save_org_key(self.org.name, ORG_KEY + "G", provider="gemini")
            api_ai.save_ai_profile("organization", self.org.name, provider="openai")
            r = api_ai.resolve_ai(self.owner.user, "auto", self.org.name)
        self.assertEqual(r["provider"], "openai")

    def test_local_profile_needs_no_key(self):
        with as_user(self.owner.user):
            api_ai.save_ai_profile("organization", self.org.name, provider="local",
                                   base_url="http://10.0.0.5:11434/v1")
            calls = []

            def post(url, headers=None, json=None, timeout=None):
                calls.append(url)
                return _Resp()

            with mock.patch.object(llm.requests, "post", post):
                out = self.ask(self.owner.user, organization_id=self.org.name)
        self.assertEqual(out["answer"], "jawab")
        self.assertEqual(calls, ["http://10.0.0.5:11434/v1/chat/completions"])


class TestBudget(Base):
    def setUp(self):
        super().setUp()
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)

    def profile(self, **kw):
        with as_user(self.owner.user):
            api_ai.save_ai_profile("organization", self.org.name, provider="openai", **kw)

    def notes(self):
        return frappe.get_all("Notification Log", filters={"for_user": self.owner.user}, pluck="subject")

    def test_calls_are_logged_with_feature_and_rolled_up(self):
        with _post(100):
            self.ask(self.owner.user, organization_id=self.org.name)
            self.ask(self.owner.user, organization_id=self.org.name)
        log = frappe.get_all("RN AI Usage Log", filters={"owner_id": self.org.name}, fields=["feature", "total_tokens"])
        self.assertEqual([(r.feature, r.total_tokens) for r in log], [("ask", 100)] * 2)
        day, month = budget.usage_totals("organization", self.org.name)
        self.assertEqual((day, month), (200, 200))

    def test_daily_budget_warns_at_80_percent_then_blocks_when_exhausted(self):
        self.profile(daily_budget_tokens=300)
        with _post(100):
            self.ask(self.owner.user, organization_id=self.org.name)
            self.ask(self.owner.user, organization_id=self.org.name)
            self.assertEqual(self.notes(), [])  # 200/300 = 66%
            self.ask(self.owner.user, organization_id=self.org.name)  # 300/300
        subjects = self.notes()
        self.assertTrue(any("habis" in s for s in subjects), subjects)
        with _post(100), self.assertRaises(frappe.ValidationError) as e:
            self.ask(self.owner.user, organization_id=self.org.name)
        self.assertIn("Anggaran", str(e.exception))
        self.assertEqual(budget.usage_totals("organization", self.org.name)[0], 300)  # the blocked call cost nothing

    def test_eighty_percent_warning_comes_once(self):
        self.profile(daily_budget_tokens=500)
        with _post(100):
            for _ in range(4):
                self.ask(self.owner.user, organization_id=self.org.name)
        self.assertEqual(len([s for s in self.notes() if "80%" in s]), 1)

    def test_monthly_budget_counts_across_days(self):
        self.profile(monthly_budget_tokens=150)
        today = frappe.utils.getdate(frappe.utils.nowdate())
        first = today.replace(day=1)
        if first == today:
            self.skipTest("first day of the month: no earlier day to put usage on")
        frappe.get_doc({"doctype": "RN AI Usage Daily", "usage_date": first, "owner_type": "organization",
                        "owner_id": self.org.name, "total_tokens": 200, "requests": 2}).insert()
        with _post(100), self.assertRaises(frappe.ValidationError):
            self.ask(self.owner.user, organization_id=self.org.name)

    def test_a_disabled_profile_switches_ai_off_for_the_org_only(self):
        self.profile(status="disabled")
        with _post(), self.assertRaises(frappe.ValidationError) as e:
            self.ask(self.owner.user, organization_id=self.org.name)
        self.assertIn("dinonaktifkan", str(e.exception))
        with as_user(self.owner.user):
            api_ai.save_user_key(self.owner.user, KEY)
        with _post():
            self.assertEqual(self.ask(self.owner.user)["answer"], "jawab")  # personal context still works

    def test_hourly_rate_limit_per_organisation(self):
        with mock.patch.dict(budget.HOURLY_LIMIT, {"organization": 2}), _post(1):
            self.ask(self.owner.user, organization_id=self.org.name)
            self.ask(self.member.user, organization_id=self.org.name)
            with self.assertRaises(frappe.ValidationError) as e:
                self.ask(self.owner.user, organization_id=self.org.name)
        self.assertIn("satu jam", str(e.exception))

    def test_summary_shows_budget_and_daily_rollup(self):
        self.profile(daily_budget_tokens=1000)
        with _post(100):
            self.ask(self.owner.user, organization_id=self.org.name)
        with as_user(self.owner.user):
            s = api_ai.ai_usage_summary(organization_id=self.org.name)
        self.assertEqual((s["budget"]["daily_limit"], s["budget"]["daily_used"]), (1000, 100))
        self.assertEqual([(d["requests"], d["total_tokens"]) for d in s["daily"]], [(1, 100)])


class TestRetentionAndPlatform(Base):
    def test_purge_deletes_only_detail_older_than_seven_days_and_keeps_the_rollup(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
        with _post(100):
            self.ask(self.owner.user, organization_id=self.org.name)
        old = frappe.get_doc({"doctype": "RN AI Usage Log", "owner_type": "organization", "owner_id": self.org.name,
                              "user_id": self.owner.user, "key_source": "organization", "outcome": "ok"}).insert()
        frappe.db.set_value("RN AI Usage Log", old.name, "creation", add_days(now_datetime(), -8))
        budget.purge_usage_logs()
        left = frappe.get_all("RN AI Usage Log", filters={"owner_id": self.org.name}, pluck="name")
        self.assertEqual(len(left), 1)
        self.assertNotIn(old.name, left)
        self.assertEqual(budget.usage_totals("organization", self.org.name)[0], 100)

    def test_platform_intake_falls_back_to_rules_when_the_platform_budget_is_spent(self):
        api_ai.save_platform_key(KEY, provider="openai")
        api_ai.save_ai_profile("platform", None, provider="openai", daily_budget_tokens=50)
        frappe.get_doc({"doctype": "RN AI Usage Daily", "usage_date": frappe.utils.nowdate(),
                        "owner_type": "platform", "owner_id": api_ai.PLATFORM_OWNER, "total_tokens": 50}).insert()
        with mock.patch.object(llm.requests, "post", side_effect=AssertionError("provider must not be called")):
            fields, parser = report_intake.extract("Sumur kering, 50 KK kekurangan air bersih di Dusun Oebelo.")
        self.assertEqual(parser, "rules")
        self.assertEqual(fields["report_type"], "water_shortage")
