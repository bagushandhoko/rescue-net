"""One chat call for every AI provider Rescue-Net supports (BYOK).

Callers pass the provider + key they resolved; this module only speaks
HTTP to the provider and normalises the answer:

    text, usage = chat("anthropic", key, "claude-opus-5", system, [user_msg])

`usage` is always {prompt_tokens, completion_tokens, total_tokens} so the
RN AI Usage Log stays the same for every provider. Failures raise
LLMError with a `kind` (network / auth / http / refusal / invalid) so the
caller can log and show one message.
"""

import json
import re

import requests

PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1", "gpt-4o"],
        "key_hint": "sk-...",
    },
    "anthropic": {
        "label": "Claude (Anthropic)",
        "default_model": "claude-opus-5",
        "models": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
        "key_hint": "sk-ant-...",
    },
    "gemini": {
        "label": "Google Gemini",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
        "key_hint": "AIza...",
    },
}

ANTHROPIC_VERSION = "2023-06-01"
# Opus 5 / Fable: a safety decline is re-run server-side on Anthropic's
# recommended fallback model instead of coming back as an empty refusal.
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
TIMEOUT = 90


class LLMError(Exception):
    def __init__(self, kind, note=""):
        super().__init__(f"{kind}: {note}")
        self.kind = kind
        self.note = str(note)[:140]


def normalize_provider(provider):
    p = (provider or "openai").strip().lower()
    aliases = {"claude": "anthropic", "google": "gemini"}
    p = aliases.get(p, p)
    if p not in PROVIDERS:
        raise LLMError("unsupported", p)
    return p


def default_model(provider):
    return PROVIDERS[normalize_provider(provider)]["default_model"]


def catalog():
    return [
        {"provider": k, "label": v["label"], "default_model": v["default_model"],
         "models": v["models"], "key_hint": v["key_hint"]}
        for k, v in PROVIDERS.items()
    ]


def _post(url, headers, payload):
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    except Exception as e:
        raise LLMError("network", type(e).__name__)
    if r.status_code in (401, 403):
        raise LLMError("auth", r.status_code)
    if not r.ok:
        raise LLMError("http", r.status_code)
    try:
        return r.json()
    except Exception:
        raise LLMError("invalid", "non-json")


def _openai(key, model, system, messages, temperature, json_mode, max_tokens):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}]
        + [{"role": "user", "content": m} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post("https://api.openai.com/v1/chat/completions",
                 {"Authorization": "Bearer " + key, "Content-Type": "application/json"}, payload)
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        raise LLMError("invalid", "choices")
    u = data.get("usage") or {}
    return text, {
        "prompt_tokens": u.get("prompt_tokens") or 0,
        "completion_tokens": u.get("completion_tokens") or 0,
        "total_tokens": u.get("total_tokens") or 0,
    }


def _anthropic(key, model, system, messages, temperature, json_mode, max_tokens):
    # Claude 5 models take no temperature/top_p (400) and think adaptively
    # by default — the request stays minimal.
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": "\n\n".join(messages)}],
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    if model.startswith(("claude-opus-5", "claude-fable")):
        payload["fallbacks"] = "default"
        headers["anthropic-beta"] = ANTHROPIC_FALLBACK_BETA
    data = _post("https://api.anthropic.com/v1/messages", headers, payload)
    if data.get("stop_reason") == "refusal":
        raise LLMError("refusal", (data.get("stop_details") or {}).get("category") or "")
    text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
    if not text:
        raise LLMError("invalid", data.get("stop_reason") or "empty")
    u = data.get("usage") or {}
    pin, pout = u.get("input_tokens") or 0, u.get("output_tokens") or 0
    return text, {"prompt_tokens": pin, "completion_tokens": pout, "total_tokens": pin + pout}


def _gemini(key, model, system, messages, temperature, json_mode, max_tokens):
    config = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        config["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": m} for m in messages]}],
        "generationConfig": config,
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    data = _post(url, {"x-goog-api-key": key, "Content-Type": "application/json"}, payload)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
    except Exception:
        reason = (data.get("promptFeedback") or {}).get("blockReason")
        raise LLMError("refusal" if reason else "invalid", reason or "candidates")
    u = data.get("usageMetadata") or {}
    return text, {
        "prompt_tokens": u.get("promptTokenCount") or 0,
        "completion_tokens": u.get("candidatesTokenCount") or 0,
        "total_tokens": u.get("totalTokenCount") or 0,
    }


_CALLS = {"openai": _openai, "anthropic": _anthropic, "gemini": _gemini}


def chat(provider, api_key, model, system, messages, temperature=0.2, json_mode=False,
         max_tokens=16000):
    """`messages` = list of user-turn strings (context first, question last)."""
    provider = normalize_provider(provider)
    if isinstance(messages, str):
        messages = [messages]
    model = (model or "").strip() or default_model(provider)
    return _CALLS[provider](api_key, model, system, list(messages), temperature, json_mode, max_tokens)


def test_key(provider, api_key):
    """Cheap authenticated listing call; returns (ok, message). Never echoes the key."""
    provider = normalize_provider(provider)
    if provider == "openai":
        url, headers = "https://api.openai.com/v1/models", {"Authorization": "Bearer " + api_key}
    elif provider == "anthropic":
        url, headers = "https://api.anthropic.com/v1/models", {
            "x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
    else:
        url, headers = "https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key": api_key}
    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception:
        return False, "Gagal menghubungi provider (jaringan)."
    if r.status_code in (400, 401, 403):
        return False, f"Kunci ditolak ({r.status_code})."
    if not r.ok:
        return False, f"Provider mengembalikan {r.status_code}."
    return True, "Kunci valid."


def parse_json(text):
    """Pull the first JSON object out of a model answer (fenced or bare)."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    try:
        value = json.loads(raw)
    except Exception:
        return None
    return value if isinstance(value, dict) else None
