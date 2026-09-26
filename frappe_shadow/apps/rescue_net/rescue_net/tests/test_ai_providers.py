"""Multi-provider AI (OpenAI / Claude / Gemini): the right request per provider,
one usage shape, 'auto' takes the key saved last, platform key is System-Manager only."""

from unittest import mock

import frappe

from rescue_net import api_ai
from rescue_net.services import llm
from rescue_net.tests.factories import RNTestCase, as_user, contains_value, make_actor, make_world

KEY = "fake-byok-PROVIDER-0123456789abcdefWXYZ"


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.ok = data, status, status < 400

    def json(self):
        return self._data


ANSWERS = {
    "openai": {"choices": [{"message": {"content": "jawab-openai"}}],
               "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}},
    "anthropic": {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "jawab-claude"}],
                  "stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 2}},
    "gemini": {"candidates": [{"content": {"parts": [{"text": "jawab-gemini"}]}}],
               "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5}},
}


def _fake_post(calls):
    def post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        if "anthropic" in url:
            return _Resp(ANSWERS["anthropic"])
        if "googleapis" in url:
            return _Resp(ANSWERS["gemini"])
        return _Resp(ANSWERS["openai"])
    return post


class TestDispatcher(RNTestCase):
    def test_each_provider_gets_its_own_request_and_one_usage_shape(self):
        for provider, url_part in (("openai", "api.openai.com"), ("anthropic", "api.anthropic.com"),
                                   ("gemini", "generativelanguage.googleapis.com")):
            calls = []
            with mock.patch.object(llm.requests, "post", _fake_post(calls)):
                text, usage = llm.chat(provider, KEY, None, "sistem", ["konteks", "pertanyaan"])
            self.assertIn(url_part, calls[0]["url"])
            self.assertTrue(text.startswith("jawab-"))
            self.assertEqual(usage, {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5})

    def test_claude_request_follows_the_messages_api(self):
        calls = []
        with mock.patch.object(llm.requests, "post", _fake_post(calls)):
            llm.chat("claude", KEY, None, "sistem", ["a", "b"], temperature=0.2)
        req = calls[0]
        self.assertEqual(req["headers"]["x-api-key"], KEY)
        self.assertEqual(req["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(req["json"]["model"], "claude-opus-5")
        self.assertEqual(req["json"]["system"], "sistem")
        self.assertNotIn("temperature", req["json"])  # rejected by Claude 5 models
        self.assertEqual(req["json"]["fallbacks"], "default")

    def test_refusal_and_auth_errors_are_typed(self):
        with mock.patch.object(llm.requests, "post", lambda *a, **k: _Resp({"stop_reason": "refusal", "content": []})):
            with self.assertRaises(llm.LLMError) as e:
                llm.chat("anthropic", KEY, None, "s", ["q"])
        self.assertEqual(e.exception.kind, "refusal")
        with mock.patch.object(llm.requests, "post", lambda *a, **k: _Resp({}, 401)):
            with self.assertRaises(llm.LLMError) as e:
                llm.chat("gemini", KEY, None, "s", ["q"])
        self.assertEqual(e.exception.kind, "auth")

    def test_unknown_provider_is_refused(self):
        with self.assertRaises(llm.LLMError):
            llm.normalize_provider("llama")

    def test_parse_json_handles_fences(self):
        self.assertEqual(llm.parse_json('ok\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(llm.parse_json('{"b": 2}'), {"b": 2})
        self.assertIsNone(llm.parse_json("tidak ada json"))


class TestKeysPerProvider(RNTestCase):
    def setUp(self):
        super().setUp()
        self.me = make_actor()

    def test_claude_key_gets_a_claude_model_and_auto_takes_the_latest(self):
        with as_user(self.me.user):
            api_ai.save_user_key(self.me.user, KEY + "O", provider="openai")
            saved = api_ai.save_user_key(self.me.user, KEY + "C", provider="anthropic", model_name="gpt-4o-mini")
        self.assertEqual(saved["setting"]["model_name"], "claude-opus-5")
        self.assertFalse(contains_value(saved, KEY + "C"))
        with as_user(self.me.user):
            key, model, source, _t, _o, provider = api_ai._resolve_ai_key(self.me.user, "auto")
        self.assertEqual((key, provider, model, source), (KEY + "C", "anthropic", "claude-opus-5", "user"))

    def test_ask_runs_on_the_chosen_provider(self):
        w = make_world()
        with as_user(self.me.user):
            api_ai.save_user_key(self.me.user, KEY, provider="gemini")
            calls = []
            with mock.patch.object(llm.requests, "post", _fake_post(calls)):
                out = api_ai.ask(self.me.user, w.event.name, "Apa yang paling mendesak?", provider="auto")
        self.assertEqual(out["answer"], "jawab-gemini")
        self.assertEqual(out["provider"], "gemini")
        log = frappe.get_all("RN AI Usage Log", filters={"user_id": self.me.user}, fields=["provider", "total_tokens"])
        self.assertEqual([(r.provider, r.total_tokens) for r in log], [("gemini", 5)])

    def test_platform_key_is_system_manager_only(self):
        with as_user(self.me.user), self.assertRaises(frappe.PermissionError):
            api_ai.save_platform_key(KEY, provider="anthropic")
        out = api_ai.save_platform_key(KEY, provider="anthropic")  # Administrator
        self.assertFalse(contains_value(out, KEY))
        self.assertEqual(api_ai.resolve_platform_key(), (KEY, "claude-opus-5", "anthropic"))
