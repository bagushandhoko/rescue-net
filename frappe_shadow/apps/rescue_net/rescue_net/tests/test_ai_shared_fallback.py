"""Owner 2026-10-23: personal key -> organisation key (if the admin shares it with
members) -> platform key (System Manager, every disaster); a spent shared quota
tells the user to add their own key."""

from unittest import mock

import frappe

from rescue_net import api_ai
from rescue_net.tests.factories import RNTestCase, as_user, make_actor, make_event, make_org
from rescue_net.tests.test_ai_budget import KEY, ORG_KEY, _post

PLATFORM_KEY = "fake-byok-PLATFORM-0123456789abcdefWXYZ"


class TestSharedFallback(RNTestCase):
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.owner = make_actor(org=self.org, org_role="owner")
        self.member = make_actor(org=self.org, org_role="member")
        self.lone = make_actor()
        self.event = make_event()

    def resolve(self, who):
        with as_user(who.user):
            return api_ai.resolve_ai(who.user, "auto")

    def test_personal_key_always_wins(self):
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        with as_user(self.member.user):
            api_ai.save_user_key(self.member.user, KEY, provider="openai")
        r = self.resolve(self.member)
        self.assertEqual((r["api_key"], r["owner_type"]), (KEY, "user"))

    def test_org_key_reaches_members_only_when_the_admin_shares_it(self):
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
        self.assertIsNone(self.resolve(self.member))
        with as_user(self.owner.user):
            api_ai.save_ai_profile("organization", self.org.name, provider="openai", share_with_members=1)
        r = self.resolve(self.member)
        self.assertEqual((r["api_key"], r["owner_type"], r["owner_id"]), (ORG_KEY, "organization", self.org.name))
        self.assertIsNone(self.resolve(self.lone))          # not a member -> no org key

    def test_platform_key_serves_everyone_without_a_key(self):
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        r = self.resolve(self.lone)
        self.assertEqual((r["api_key"], r["owner_type"], r["owner_id"]), (PLATFORM_KEY, "platform", api_ai.PLATFORM_OWNER))
        # an organisation key that is shared goes before the platform key
        with as_user(self.owner.user):
            api_ai.save_org_key(self.org.name, ORG_KEY)
            api_ai.save_ai_profile("organization", self.org.name, provider="openai", share_with_members=1)
        self.assertEqual(self.resolve(self.member)["owner_type"], "organization")

    def test_org_context_still_never_uses_the_platform_key(self):
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        with as_user(self.member.user):
            self.assertIsNone(api_ai.resolve_ai(self.member.user, "auto", self.org.name))

    def test_disabled_platform_profile_switches_the_fallback_off(self):
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        api_ai.save_ai_profile("platform", None, provider="openai", status="disabled")
        self.assertIsNone(self.resolve(self.lone))

    def test_spent_platform_quota_notifies_the_user_to_use_their_own_key(self):
        api_ai.save_platform_key(PLATFORM_KEY, provider="openai")
        api_ai.save_ai_profile("platform", None, provider="openai", daily_budget_tokens=100)
        with as_user(self.lone.user), _post(100):
            api_ai.ask(self.lone.user, self.event.name, "Ringkas")       # spends the whole quota
        with as_user(self.lone.user), self.assertRaisesRegex(frappe.ValidationError, "kunci AI Anda sendiri"):
            api_ai.ask(self.lone.user, self.event.name, "Lagi")
        subjects = frappe.get_all("Notification Log", filters={"for_user": self.lone.user}, pluck="subject")
        self.assertTrue(any("Pasang kunci AI Anda sendiri" in s for s in subjects))
        # a second refusal the same day does not pile up a second notice
        with as_user(self.lone.user), self.assertRaises(frappe.ValidationError):
            api_ai.ask(self.lone.user, self.event.name, "Lagi")
        again = frappe.get_all("Notification Log", filters={"for_user": self.lone.user,
                               "subject": ["like", "%Pasang kunci AI Anda sendiri%"]}, pluck="name")
        self.assertEqual(len(again), 1)
        # once the user adds their own key, AI works again
        with as_user(self.lone.user):
            api_ai.save_user_key(self.lone.user, KEY, provider="openai")
        with as_user(self.lone.user), _post(5):
            self.assertEqual(api_ai.ask(self.lone.user, self.event.name, "Lagi")["answer"], "jawab")

    def test_only_an_org_admin_may_share(self):
        with as_user(self.member.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_ai_profile("organization", self.org.name, provider="openai", share_with_members=1)
