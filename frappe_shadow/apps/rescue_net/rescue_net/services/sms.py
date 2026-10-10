"""SMS cadangan saat WhatsApp/internet tak ada (Fase 10c, tahap 1: kerangka + mode simulasi).

Aturan (dari audit, menunggu keputusan owner untuk yang bertanda *):
- hanya jenis pesan ``peringatan`` dan ``penugasan``* yang boleh jatuh ke SMS;
- isi SMS SELALU templat tetap ≤160 karakter, ASCII, tanpa data sensitif (nama korban, kondisi medis) — hanya "ada
  pesan baru di Rescue-Net" + kode; pemanggil tidak bisa menyuntikkan teks bebas;
- batas harian per skop (``RN Notification Setting.daily_limit``, bawaan 100)*;
- latihan (posko/event ``is_drill``) tidak pernah mengirim sungguhan;
- tanpa penyedia SMS yang dikonfigurasi (bawaan) = simulasi: hanya dicatat di RN Notification Log;
- penyedia: ``twilio_sms`` (Twilio, From = nomor/alfanumerik, To biasa). Penyedia lokal dipilih owner*.
Skop setelan SMS selalu berawalan ``sms:`` supaya tidak bertabrakan dengan setelan WhatsApp (skop unik).
"""

import re

import frappe
from frappe.utils import add_to_date, getdate, now_datetime

SMS_SCOPE = "sms:global"
ALLOWED_KINDS = ("peringatan", "penugasan")
MAX_LEN = 160
DEFAULT_DAILY_LIMIT = 100
_TEMPLATES = {
    "peringatan": "Rescue-Net: ada peringatan baru{code}. Buka aplikasi atau rescue-net.online.",
    "penugasan": "Rescue-Net: ada penugasan baru{code}. Buka aplikasi atau rescue-net.online.",
}


def sms_text(kind, code=None):
    """Templat tetap; ``code`` hanya alfanumerik pendek (bukan teks bebas)."""
    if kind not in _TEMPLATES:
        frappe.throw("Jenis pesan SMS tidak diizinkan: {}".format(kind))
    code = re.sub(r"[^A-Za-z0-9-]", "", str(code or ""))[:16]
    text = _TEMPLATES[kind].format(code=(" (kode " + code + ")") if code else "")
    return text.encode("ascii", "ignore").decode()[:MAX_LEN]


def _dispatch_twilio_sms(cfg, to, body):
    # api_token = "ACxxxx:auth_token" ; sender_id = nomor Twilio atau ID alfanumerik
    from rescue_net.api_notify import _http_post

    try:
        sid, _, tok = cfg["api_token"].partition(":")
        base = (cfg["api_base"] or "https://api.twilio.com").rstrip("/")
        r = _http_post(base + "/2010-04-01/Accounts/%s/Messages.json" % sid, auth=(sid, tok),
                       data={"From": cfg["sender_id"], "To": "+" + to, "Body": body})
        j = r.json() if r.content else {}
        return bool(r.ok), str(j.get("sid") or ""), "" if r.ok else (r.text or "")[:400]
    except Exception as e:  # noqa: BLE001
        return False, "", str(e)[:400]


SMS_ADAPTERS = {"twilio_sms": _dispatch_twilio_sms}


def _setting():
    from rescue_net.api_notify import _SIM

    name = frappe.db.get_value("RN Notification Setting", {"scope": SMS_SCOPE, "status": "active"}, "name")
    if not name:
        return dict(_SIM, scope=SMS_SCOPE, daily_limit=DEFAULT_DAILY_LIMIT)
    doc = frappe.get_doc("RN Notification Setting", name)
    return {"scope": doc.scope, "provider": (doc.provider or "simulasi").strip().lower(), "enabled": int(doc.enabled or 0),
            "api_base": (doc.api_base or "").strip(), "api_token": doc.get_password("api_token") if doc.api_token else "",
            "sender_id": (doc.sender_id or "").strip(), "daily_limit": int(doc.daily_limit or DEFAULT_DAILY_LIMIT)}


def _sent_today(scope):
    start = getdate(now_datetime())
    return frappe.db.count("RN Notification Log", {"channel": "sms", "scope": scope, "creation": [">=", start],
                                                   "status": ["in", ["sent", "simulated"]]})


def send_sms(to, kind, code=None, *, context_type=None, context_id=None, posko=None, fallback_of=None):
    """Kirim satu SMS templat. Selalu menulis RN Notification Log; tidak pernah melempar."""
    from rescue_net.api_notify import _norm_msisdn
    from rescue_net.services.drill import is_drill_posko

    if kind not in ALLOWED_KINDS:
        return {"status": "skipped", "reason": "jenis pesan tidak diizinkan lewat SMS"}
    num = _norm_msisdn(to)
    cfg = _setting()
    provider = cfg["provider"]
    log = frappe.new_doc("RN Notification Log")
    log.channel, log.to_number, log.body = "sms", num, sms_text(kind, code)
    log.context_type, log.context_id, log.event_key = context_type, context_id, kind
    log.scope, log.provider, log.fallback_of = cfg["scope"], provider, fallback_of
    log.created_by_user_id = frappe.session.user
    if not num:
        log.status, log.error = "failed", "nomor tidak valid"
        log.insert(ignore_permissions=True)
        return {"status": "failed", "log": log.name, "error": log.error}
    if _sent_today(cfg["scope"]) >= cfg["daily_limit"]:
        log.status, log.error = "failed", "batas harian SMS tercapai"
        log.insert(ignore_permissions=True)
        return {"status": "failed", "log": log.name, "error": log.error}
    live = provider in SMS_ADAPTERS and cfg["enabled"] and cfg["api_token"] and not is_drill_posko(posko or (
        context_id if context_type == "posko" else None))
    if not live:
        log.status, log.sent_at = "simulated", now_datetime()
        log.insert(ignore_permissions=True)
        return {"status": "simulated", "log": log.name, "provider": provider}
    ok, mid, err = SMS_ADAPTERS[provider](cfg, num, log.body)
    log.status, log.provider_message_id, log.error, log.sent_at = ("sent" if ok else "failed"), mid, err, now_datetime()
    log.insert(ignore_permissions=True)
    return {"status": log.status, "log": log.name, "provider": provider, "error": err}


def send_with_fallback(to, wa_body, kind, code=None, **ctx):
    """WhatsApp dulu; bila gagal dan jenisnya diizinkan -> SMS templat ke nomor yang sama."""
    from rescue_net.api_notify import send_whatsapp

    wa = send_whatsapp(to, wa_body, event_key=kind, **ctx)
    out = {"whatsapp": wa, "sms": None}
    if wa.get("status") == "failed" and kind in ALLOWED_KINDS:
        out["sms"] = send_sms(to, kind, code, context_type=ctx.get("context_type"), context_id=ctx.get("context_id"),
                              posko=ctx.get("posko"), fallback_of=wa.get("log"))
    return out


def sweep_failed_whatsapp(minutes=60):
    """Terjadwal (tiap jam): WhatsApp jenis peringatan/penugasan yang gagal dalam N menit terakhir dan belum punya SMS cadangan."""
    since = add_to_date(now_datetime(), minutes=-minutes)
    for lg in frappe.get_all("RN Notification Log",
                             filters={"channel": "whatsapp", "status": "failed", "event_key": ["in", list(ALLOWED_KINDS)],
                                      "creation": [">", since]},
                             fields=["name", "to_number", "event_key", "context_type", "context_id"], limit_page_length=500):
        if frappe.db.exists("RN Notification Log", {"channel": "sms", "fallback_of": lg.name}):
            continue
        send_sms(lg.to_number, lg.event_key, None, context_type=lg.context_type, context_id=lg.context_id, fallback_of=lg.name)
