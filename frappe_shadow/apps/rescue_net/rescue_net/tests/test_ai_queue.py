"""Fase 7 step 3: rule-based fallbacks and the reprocess queue (ADR-0002 section 5)."""

import json
from unittest import mock

import frappe
from frappe.utils import add_to_date, now_datetime

from rescue_net import api_ai
from rescue_net import api_reports as api
from rescue_net.ai import budget, queue
from rescue_net.services import duplicates, llm
from rescue_net.tests.factories import (RNTestCase, as_user, make_actor, make_event, make_org, make_posko,
                                        make_user)

KEY = "fake-byok-QUEUE-0123456789abcdefWXYZ"
TEXT = "Banjir setinggi 1 meter merendam Desa Sukamaju, 40 orang mengungsi ke masjid, butuh selimut dan makanan."


class _Resp:
    status_code, ok = 200, True

    def __init__(self, content):
        self.content = content

    def json(self):
        return {"choices": [{"message": {"content": self.content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


AI_FIELDS = json.dumps({"title": "Banjir Sukamaju (AI)", "report_type": "shelter_need", "priority": "high",
                        "affected_people_count": 55, "urgent_needs": "selimut, makanan", "location_text": "Desa Sukamaju",
                        "damage_scale_value": None, "damage_scale_unit": None, "notes": []})


def _provider(content=AI_FIELDS):
    return mock.patch.object(llm.requests, "post", lambda *a, **k: _Resp(content))


class TestRuleVerdict(RNTestCase):
    def need(self, **kw):
        return {"quantity": 100, "unit": "pcs", "posko": "A", "observed_at": "2026-10-01 08:00:00", **kw}

    def test_same_quantity_close_in_time_is_a_duplicate(self):
        r = duplicates.rule_verdict(self.need(), self.need(quantity=105, observed_at="2026-10-01 20:00:00"))
        self.assertEqual(r["verdict"], "duplicate")
        self.assertIn("tanpa AI", r["answer"])

    def test_far_quantities_or_far_in_time_are_different(self):
        self.assertEqual(duplicates.rule_verdict(self.need(), self.need(quantity=500))["verdict"], "different")
        self.assertEqual(duplicates.rule_verdict(
            self.need(), self.need(posko="B", observed_at="2026-10-09 08:00:00"))["verdict"], "different")

    def test_other_unit_is_unclear(self):
        self.assertEqual(duplicates.rule_verdict(self.need(), self.need(unit="dus"))["verdict"], "unclear")


class TestDuplicateFallback(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.posko = make_posko(self.event, make_org())
        self.me = make_actor(posko=self.posko)

        def need(qty):
            return frappe.get_doc({"doctype": "RN Logistic Need", "title": "Selimut", "item_name": "Selimut", "raw_item_text": "selimut",
                                   "quantity": qty, "unit": "pcs", "posko": self.posko.name,
                                   "disaster_event": self.event.name, "observed_at": now_datetime()}
                                  ).insert(ignore_permissions=True).name
        self.a, self.b = need(100), need(104)

    def run_it(self, **kw):
        with as_user(self.me.user):
            return api_ai.analyze_duplicate_candidate(self.me.user, self.a, self.b, **kw)

    def test_without_a_key_the_rules_answer_and_say_so(self):
        out = self.run_it()
        self.assertTrue(out["processed_without_ai"])
        self.assertEqual((out["verdict"], out["label"]), ("duplicate", "diproses tanpa AI"))

    def test_with_a_key_the_ai_answers(self):
        with as_user(self.me.user):
            api_ai.save_user_key(self.me.user, KEY, provider="openai")
        with _provider("BEDA\nalasan"):
            out = self.run_it()
        self.assertFalse(out["processed_without_ai"])
        self.assertEqual(out["verdict"], "different")

    def test_a_spent_budget_falls_back_instead_of_failing(self):
        with as_user(self.me.user):
            api_ai.save_user_key(self.me.user, KEY, provider="openai")
            api_ai.save_ai_profile("personal", self.me.user, provider="openai", daily_budget_tokens=10)
        frappe.get_doc({"doctype": "RN AI Usage Daily", "usage_date": frappe.utils.nowdate(), "owner_type": "user",
                        "owner_id": self.me.user, "total_tokens": 10}).insert()
        with mock.patch.object(llm.requests, "post", side_effect=AssertionError("provider must not be called")):
            out = self.run_it()
        self.assertTrue(out["processed_without_ai"])


class TestReportQueue(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event(event_status="active")
        org = make_org()
        self.posko = make_posko(self.event, org, title="Posko Sukamaju", village_name="Sukamaju",
                                posko_type="logistics", latitude=-6.90, longitude=107.10)
        self.op = make_actor(posko=self.posko)
        self.reporter = make_actor(role="viewer")
        self.stranger = make_actor()

    def submit(self):
        with as_user(self.reporter.user):
            return api.submit_community_report(description=TEXT, intake_mode="narrative",
                                               disaster_event=self.event.name, latitude=-6.901, longitude=107.101)

    def test_a_narrative_read_only_by_rules_waits_for_an_ai_pass(self):
        out = self.submit()
        self.assertEqual(out["ai_status"], "pending_ai")
        job = frappe.get_all("RN AI Job", filters={"ref_name": out["name"]}, fields=["feature", "status", "owner_type"])
        self.assertEqual([(j.feature, j.status, j.owner_type) for j in job], [("report_intake", "pending", "platform")])
        self.assertEqual(frappe.db.get_value("RN Community Report", out["name"], "ai_status"), "pending_ai")

    def test_a_narrative_the_ai_read_needs_no_pass_and_a_form_report_neither(self):
        api_ai.save_platform_key(KEY, provider="openai")
        with _provider():
            out = self.submit()
        self.assertEqual(out["intake_parser"], "ai:openai")
        self.assertFalse(frappe.db.exists("RN AI Job", {"ref_name": out["name"]}))
        with as_user(self.reporter.user):
            form = api.submit_community_report(title="Jalan putus", description="x" * 20, report_type="blocked_access",
                                               disaster_event=self.event.name)
        self.assertFalse(frappe.db.exists("RN AI Job", {"ref_name": form["name"]}))

    def test_nothing_happens_while_ai_is_still_unavailable(self):
        out = self.submit()
        self.assertEqual(queue.process_pending(), 0)
        job = frappe.get_doc("RN AI Job", {"ref_name": out["name"]})
        self.assertEqual((job.status, job.attempts), ("pending", 0))

    def test_once_a_key_exists_the_job_yields_a_draft_suggestion_and_leaves_the_report_alone(self):
        out = self.submit()
        before = frappe.db.get_value("RN Community Report", out["name"], ["title", "affected_people_count"], as_dict=True)
        api_ai.save_platform_key(KEY, provider="openai")
        with _provider():
            self.assertEqual(queue.process_pending(), 1)
        job = frappe.get_doc("RN AI Job", {"ref_name": out["name"]})
        sug = frappe.get_doc("RN AI Suggestion", job.suggestion)
        self.assertEqual((job.status, sug.status), ("done", "draft"))
        self.assertEqual(json.loads(sug.payload)["proposed"]["affected_people_count"], 55)
        after = frappe.db.get_value("RN Community Report", out["name"], ["title", "affected_people_count", "ai_status"], as_dict=True)
        self.assertEqual((after.title, after.affected_people_count), (before.title, before.affected_people_count))
        self.assertEqual(after.ai_status, "ai_suggested")
        log = frappe.get_all("RN AI Usage Log", filters={"feature": "report_intake_retry"}, pluck="owner_type")
        self.assertEqual(log, ["platform"])

    def test_provider_errors_count_attempts_and_the_job_fails_after_five(self):
        out = self.submit()
        api_ai.save_platform_key(KEY, provider="openai")
        bad = mock.patch.object(llm.requests, "post", lambda *a, **k: type("R", (), {"status_code": 500, "ok": False, "json": lambda s: {}})())
        with bad:
            for _ in range(queue.MAX_ATTEMPTS):
                queue.process_pending()
        job = frappe.get_doc("RN AI Job", {"ref_name": out["name"]})
        self.assertEqual((job.status, job.attempts), ("failed", queue.MAX_ATTEMPTS))

    def test_a_run_handles_at_most_the_hourly_cap(self):
        for _ in range(3):
            self.submit()
        api_ai.save_platform_key(KEY, provider="openai")
        with _provider():
            self.assertEqual(queue.process_pending(limit=2), 2)
        self.assertEqual(frappe.db.count("RN AI Job", {"status": "pending"}), 1)

    def _suggested(self):
        out = self.submit()
        api_ai.save_platform_key(KEY, provider="openai")
        with _provider():
            queue.process_pending()
        return out["name"], frappe.db.get_value("RN AI Suggestion", {"ref_name": out["name"]}, "name")

    def test_only_the_reports_posko_decides_and_accepting_applies_the_proposed_fields(self):
        report, sug = self._suggested()
        with as_user(self.stranger.user):
            self.assertEqual(api_ai.list_ai_suggestions(), [])
            with self.assertRaises(frappe.PermissionError):
                api_ai.decide_ai_suggestion(sug, "accepted")
        with as_user(self.reporter.user), self.assertRaises(frappe.PermissionError):
            api_ai.decide_ai_suggestion(sug, "accepted")  # the reporter never decides on their own report
        with as_user(self.op.user):
            self.assertEqual([s["name"] for s in api_ai.list_ai_suggestions()], [sug])
            out = api_ai.decide_ai_suggestion(sug, "accepted")
            with self.assertRaises(frappe.ValidationError):
                api_ai.decide_ai_suggestion(sug, "rejected")  # decided once
        self.assertEqual(out["applied"]["affected_people_count"], 55)
        r = frappe.db.get_value("RN Community Report", report, ["affected_people_count", "ai_status", "intake_parser", "status"], as_dict=True)
        self.assertEqual((r.affected_people_count, r.ai_status, r.intake_parser, r.status),
                         (55, "ai_applied", "ai:openai", "submitted"))

    def test_rejecting_changes_nothing(self):
        report, sug = self._suggested()
        before = frappe.db.get_value("RN Community Report", report, "affected_people_count")
        with as_user(self.op.user):
            api_ai.decide_ai_suggestion(sug, "rejected")
        r = frappe.db.get_value("RN Community Report", report, ["affected_people_count", "ai_status"], as_dict=True)
        self.assertEqual((r.affected_people_count, r.ai_status), (before, "ai_rejected"))

    def test_direct_save_keeps_the_status_rules(self):
        report, sug = self._suggested()
        doc = frappe.get_doc("RN AI Suggestion", sug)
        doc.status = "accepted"
        doc.save(ignore_permissions=True)
        doc.status = "draft"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)
