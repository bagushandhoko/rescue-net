"""WhatsApp / notification dispatch for Rescue-Net.

RN can send WhatsApp messages through a configurable gateway. Until a real
gateway is configured the provider is ``simulasi``: every send is still
recorded in ``RN Notification Log`` (status ``simulated``) so the flow is
testable and the outbox is visible, but nothing leaves the server.

Config lives in ``RN Notification Setting``, one row per scope::

    scope = "global"             -> app-wide default
    scope = "<organization id>"  -> per-organisation override
    scope = "<posko name>"       -> per-posko override

Resolution walks  posko -> its organisation -> explicit scope -> global ->
built-in simulasi.

Supported providers: ``fonnte``, ``wablas``, ``twilio``, ``meta_cloud``
(plus ``simulasi``). Whitelisted endpoints are System-Manager only, except
the posko broadcast + log reads, which reuse the posko edit gate.
"""

import json
import re

import frappe
from frappe.utils import now_datetime

DEFAULT_SCOPE = "global"
_SIM = {
    "scope": DEFAULT_SCOPE,
    "provider": "simulasi",
    "enabled": 0,
    "api_base": "",
    "api_token": "",
    "sender_id": "",
}


# --------------------------------------------------------------------------- #
# number / string helpers                                                     #
# --------------------------------------------------------------------------- #

def _norm_msisdn(raw):
    """``0812xxxx`` / ``+62 812-xxxx`` / ``62812xxxx`` -> ``62812xxxx``."""
    d = re.sub(r"\D", "", str(raw or ""))
    if not d:
        return ""
    if d.startswith("0"):
        d = "62" + d[1:]
    elif d.startswith("620"):
        d = "62" + d[3:]
    elif not d.startswith("62"):
        d = "62" + d
    return d


def _split_numbers(blob):
    out, seen = [], set()
    for part in re.split(r"[,\n;/]+", str(blob or "")):
        n = _norm_msisdn(part)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


# --------------------------------------------------------------------------- #
# setting resolution                                                          #
# --------------------------------------------------------------------------- #

def _setting_row(scope):
    name = frappe.db.get_value(
        "RN Notification Setting",
        {"scope": scope, "status": "active"},
        "name",
    )
    if not name:
        return None
    doc = frappe.get_doc("RN Notification Setting", name)
    return {
        "scope": doc.scope,
        "provider": (doc.provider or "simulasi").strip().lower(),
        "enabled": int(doc.enabled or 0),
        "api_base": (doc.api_base or "").strip(),
        "api_token": doc.get_password("api_token") if doc.api_token else "",
        "sender_id": (doc.sender_id or "").strip(),
    }


def _resolve_setting(scope=None, posko=None):
    """posko -> its organisation -> explicit scope -> global -> simulasi."""
    chain = []
    if posko:
        chain.append(posko)
        org = frappe.db.get_value("RN Posko", posko, "organization")
        if org:
            chain.append(org)
    if scope and scope not in chain:
        chain.append(scope)
    if DEFAULT_SCOPE not in chain:
        chain.append(DEFAULT_SCOPE)
    for s in chain:
        row = _setting_row(s)
        if row:
            return row
    return dict(_SIM)


# --------------------------------------------------------------------------- #
# provider adapters                                                           #
# Each returns (ok: bool, provider_message_id: str, error: str). Network       #
# errors are caught here so send_whatsapp() never raises into its caller.      #
# --------------------------------------------------------------------------- #

def _http_post(url, **kw):
    import requests

    return requests.post(url, timeout=20, **kw)


def _dispatch_fonnte(cfg, to, body):
    try:
        r = _http_post(
            cfg["api_base"] or "https://api.fonnte.com/send",
            headers={"Authorization": cfg["api_token"]},
            data={"target": to, "message": body},
        )
        j = r.json() if r.content else {}
        ok = bool(r.ok and j.get("status", True))
        mid = ""
        if isinstance(j.get("id"), list) and j["id"]:
            mid = str(j["id"][0])
        elif j.get("id"):
            mid = str(j["id"])
        return ok, mid, "" if ok else (r.text or "")[:400]
    except Exception as e:  # noqa: BLE001
        return False, "", str(e)[:400]


def _dispatch_wablas(cfg, to, body):
    try:
        base = (cfg["api_base"] or "https://api.wablas.com").rstrip("/")
        r = _http_post(
            base + "/api/send-message",
            headers={"Authorization": cfg["api_token"]},
            data={"phone": to, "message": body},
        )
        j = r.json() if r.content else {}
        ok = bool(r.ok and j.get("status", True))
        return ok, str(j.get("id") or ""), "" if ok else (r.text or "")[:400]
    except Exception as e:  # noqa: BLE001
        return False, "", str(e)[:400]


def _dispatch_twilio(cfg, to, body):
    # api_token = "ACxxxx:auth_token" ; sender_id = "whatsapp:+14155238886"
    try:
        sid, _, tok = cfg["api_token"].partition(":")
        base = (cfg["api_base"] or "https://api.twilio.com").rstrip("/")
        r = _http_post(
            base + "/2010-04-01/Accounts/%s/Messages.json" % sid,
            auth=(sid, tok),
            data={
                "From": cfg["sender_id"],
                "To": "whatsapp:+" + to,
                "Body": body,
            },
        )
        j = r.json() if r.content else {}
        return bool(r.ok), str(j.get("sid") or ""), "" if r.ok else (r.text or "")[:400]
    except Exception as e:  # noqa: BLE001
        return False, "", str(e)[:400]


def _dispatch_meta(cfg, to, body):
    # sender_id = phone_number_id ; api_token = permanent access token
    try:
        base = (cfg["api_base"] or "https://graph.facebook.com/v21.0").rstrip("/")
        r = _http_post(
            "%s/%s/messages" % (base, cfg["sender_id"]),
            headers={
                "Authorization": "Bearer " + cfg["api_token"],
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": body},
                }
            ),
        )
        j = r.json() if r.content else {}
        mid = ""
        msgs = j.get("messages")
        if isinstance(msgs, list) and msgs:
            mid = str(msgs[0].get("id") or "")
        return bool(r.ok), mid, "" if r.ok else (r.text or "")[:400]
    except Exception as e:  # noqa: BLE001
        return False, "", str(e)[:400]


_ADAPTERS = {
    "fonnte": _dispatch_fonnte,
    "wablas": _dispatch_wablas,
    "twilio": _dispatch_twilio,
    "meta_cloud": _dispatch_meta,
}


# --------------------------------------------------------------------------- #
# core send                                                                   #
# --------------------------------------------------------------------------- #

def send_whatsapp(to, body, *, context_type=None, context_id=None,
                  event_key=None, scope=None, posko=None):
    """Send one WhatsApp message. Always writes an ``RN Notification Log`` row.

    Never raises — returns
    ``{status, log, provider, provider_message_id, error}`` where ``status`` is
    one of ``sent`` / ``failed`` / ``simulated``.
    """
    num = _norm_msisdn(to)
    cfg = _resolve_setting(scope=scope, posko=posko)
    provider = cfg["provider"]

    log = frappe.new_doc("RN Notification Log")
    log.channel = "whatsapp"
    log.to_number = num
    log.body = (body or "")[:2000]
    log.context_type = context_type
    log.context_id = context_id
    log.event_key = event_key
    log.scope = cfg.get("scope")
    log.provider = provider
    log.created_by_user_id = frappe.session.user

    if not num:
        log.status, log.error = "failed", "nomor tidak valid"
        log.insert(ignore_permissions=True)
        return {"status": "failed", "log": log.name, "error": log.error}

    live = provider in _ADAPTERS and cfg["enabled"] and cfg["api_token"]
    if not live:
        log.status = "simulated"
        log.sent_at = now_datetime()
        log.insert(ignore_permissions=True)
        return {"status": "simulated", "log": log.name, "provider": provider}

    ok, mid, err = _ADAPTERS[provider](cfg, num, body or "")
    log.status = "sent" if ok else "failed"
    log.provider_message_id = mid
    log.error = err
    log.sent_at = now_datetime()
    log.insert(ignore_permissions=True)
    return {
        "status": log.status,
        "log": log.name,
        "provider": provider,
        "provider_message_id": mid,
        "error": err,
    }


def notify_posko(posko, body, event_key):
    """Fan a message out to a posko's configured notification numbers.

    No-op (``status: skipped``) when the posko has notifications disabled or
    has no numbers set.
    """
    row = frappe.db.get_value(
        "RN Posko",
        posko,
        ["notify_whatsapp_enabled", "notify_whatsapp_numbers", "title"],
        as_dict=True,
    )
    if not row or not row.notify_whatsapp_enabled:
        return {"status": "skipped", "reason": "notifikasi posko nonaktif"}
    numbers = _split_numbers(row.notify_whatsapp_numbers)
    if not numbers:
        return {"status": "skipped", "reason": "tidak ada nomor"}
    results = [
        send_whatsapp(
            n, body,
            context_type="posko", context_id=posko,
            event_key=event_key, posko=posko,
        )
        for n in numbers
    ]
    return {"status": "done", "count": len(results), "results": results}


# --------------------------------------------------------------------------- #
# gate helpers                                                                #
# --------------------------------------------------------------------------- #

def _only_system_manager():
    from rescue_net.access_policy import is_system_manager

    if not is_system_manager():
        frappe.throw("Hanya System Manager", frappe.PermissionError)


def _assert_can_edit_posko(posko):
    from rescue_net.api_community_cluster import _actor, _can_edit_posko

    doc = frappe.get_doc("RN Posko", posko)
    if not _can_edit_posko(_actor(), doc):
        frappe.throw("Akses posko ditolak", frappe.PermissionError)
    return doc


# --------------------------------------------------------------------------- #
# whitelisted endpoints                                                       #
# --------------------------------------------------------------------------- #

@frappe.whitelist()
def get_notification_setting(scope=DEFAULT_SCOPE):
    _only_system_manager()
    scope = (scope or DEFAULT_SCOPE).strip()
    name = frappe.db.get_value(
        "RN Notification Setting", {"scope": scope, "status": "active"}, "name"
    )
    if not name:
        return {
            "scope": scope,
            "exists": False,
            "providers": ["simulasi"] + sorted(_ADAPTERS),
            "setting": {"provider": "simulasi", "enabled": 0},
        }
    d = frappe.get_doc("RN Notification Setting", name)
    return {
        "scope": scope,
        "exists": True,
        "providers": ["simulasi"] + sorted(_ADAPTERS),
        "setting": {
            "scope": d.scope,
            "channel": d.channel or "whatsapp",
            "provider": d.provider,
            "enabled": int(d.enabled or 0),
            "api_base": d.api_base or "",
            "sender_id": d.sender_id or "",
            "note": d.note or "",
            "token_set": bool(d.api_token),
            "token_last4": d.api_token_last4 or "",
        },
    }


@frappe.whitelist()
def save_notification_setting(scope=DEFAULT_SCOPE, provider="simulasi", enabled=0,
                              api_base=None, api_token=None, sender_id=None,
                              note=None):
    _only_system_manager()
    scope = (scope or DEFAULT_SCOPE).strip()
    provider = (provider or "simulasi").strip().lower()
    if provider not in ({"simulasi"} | set(_ADAPTERS)):
        frappe.throw("Provider tidak dikenal: " + provider)

    name = frappe.db.get_value(
        "RN Notification Setting", {"scope": scope, "status": "active"}, "name"
    )
    doc = (
        frappe.get_doc("RN Notification Setting", name)
        if name
        else frappe.new_doc("RN Notification Setting")
    )
    creating = doc.is_new()
    if creating:
        doc.scope = scope
        doc.channel = "whatsapp"
        doc.created_by_user_id = frappe.session.user

    doc.provider = provider
    doc.enabled = 1 if str(enabled) in ("1", "true", "True", "on", "yes") else 0
    if api_base is not None:
        doc.api_base = (api_base or "").strip()
    if sender_id is not None:
        doc.sender_id = (sender_id or "").strip()
    if note is not None:
        doc.note = note
    if api_token:  # only overwrite the secret when a fresh one is supplied
        tok = api_token.strip()
        doc.api_token = tok
        doc.api_token_last4 = tok[-4:]
    doc.updated_by_user_id = frappe.session.user
    doc.status = "active"

    if creating:
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"status": "saved", "scope": scope, "provider": provider,
            "enabled": doc.enabled}


@frappe.whitelist()
def send_test_whatsapp(to, scope=DEFAULT_SCOPE):
    _only_system_manager()
    return send_whatsapp(
        to,
        "[Rescue-Net] Tes notifikasi WhatsApp. Kalau pesan ini sampai, gateway sudah aktif.",
        context_type="test",
        context_id=(scope or DEFAULT_SCOPE),
        event_key="test",
        scope=scope,
    )


@frappe.whitelist()
def posko_broadcast_whatsapp(posko, message):
    """Send a free-text message to a posko's configured notification numbers.
    Gated to whoever may edit the posko (same gate as ``update_posko``)."""
    _assert_can_edit_posko(posko)
    message = (message or "").strip()
    if not message:
        frappe.throw("Pesan kosong")
    return notify_posko(posko, "[Rescue-Net] " + message, "posko_broadcast")


@frappe.whitelist()
def posko_notification_log(posko, limit=20):
    _assert_can_edit_posko(posko)
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20
    rows = frappe.get_all(
        "RN Notification Log",
        filters={"context_type": "posko", "context_id": posko},
        fields=[
            "name", "to_number", "body", "event_key", "provider", "status",
            "provider_message_id", "error", "sent_at", "creation",
        ],
        order_by="creation desc",
        limit=limit,
    )
    return {"posko": posko, "rows": rows}
