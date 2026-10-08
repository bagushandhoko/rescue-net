"""AI — reprocess queue and suggestions (ADR-0002 sections 5 and 6).

Work that arrived while AI was unavailable (no key, budget spent, provider down)
is saved as an RN AI Job. An hourly job (`process_pending`) runs a few of them once AI
is available again. The result is never written into the record: it becomes an
RN AI Suggestion (draft) that a human accepts or rejects."""

import json

import frappe
from frappe.utils import now_datetime

from rescue_net.access_policy import can_manage_posko, is_system_manager, rn_actor
from rescue_net.ai import budget
from rescue_net.services import llm

PER_RUN = 20  # jobs per hourly run
MAX_ATTEMPTS = 5

# report fields an AI pass may suggest (never status, verification, routing or reporter data)
REPORT_FIELDS = ("title", "report_type", "priority", "affected_people_count", "urgent_needs",
                 "location_text", "damage_scale_value", "damage_scale_unit")


def enqueue(feature, owner_type, owner_id, user_id, ref_doctype, ref_name):
    """One pending job per (feature, record)."""
    if frappe.db.exists("RN AI Job", {"feature": feature, "ref_doctype": ref_doctype, "ref_name": ref_name,
                                      "status": ["in", ["pending", "failed"]]}):
        return None
    job = frappe.get_doc({"doctype": "RN AI Job", "feature": feature, "ref_doctype": ref_doctype,
                          "ref_name": ref_name, "owner_type": owner_type, "owner_id": owner_id,
                          "user_id": user_id, "status": "pending"})
    job.insert(ignore_permissions=True)
    return job.name


def _report_handler(job):
    """Re-read a citizen report with the platform AI key -> suggestion payload."""
    from rescue_net import api_ai
    from rescue_net.services.report_intake import ai_extract

    key, model, provider = api_ai.resolve_platform_key()
    if not key:
        raise budget.AIUnavailable("key", "Belum ada kunci AI platform.")
    budget.check_allowed("platform", api_ai.PLATFORM_OWNER)
    report = frappe.get_doc("RN Community Report", job.ref_name)
    log = dict(owner_type="platform", owner_id=api_ai.PLATFORM_OWNER, user_id=job.user_id,
               key_source="platform", provider=provider, model_name=model, disaster_event=report.disaster_event,
               q_chars=len(report.description or ""), feature="report_intake_retry")
    try:
        fields, usage = ai_extract(report.description or "", key, model, provider)
    except llm.LLMError as e:
        api_ai._log_ai_usage(**log, outcome="error", error_note=f"{e.kind} {e.note}")
        raise
    api_ai._log_ai_usage(**log, usage=usage, outcome="ok")
    current = {f: report.get(f) for f in REPORT_FIELDS}
    proposed = {f: fields.get(f) for f in REPORT_FIELDS if fields.get(f) not in (None, "")}
    diff = {f: v for f, v in proposed.items() if v != current.get(f)}
    return {"provider": provider, "model": model, "payload": {"current": current, "proposed": diff}}


NEED_FIELDS = ("canonical_category", "canonical_group", "canonical_item")
NEED_LOOKBACK_DAYS = 14
NEED_PER_RUN = 50

NEED_SYSTEM = """You normalise one free-text logistics need from a disaster posko into a fixed catalogue.
Catalogue (category | group | item):
{catalogue}
Answer ONLY a JSON object: {{"category": str, "group": str, "item": str, "confidence": 0-100}}.
Pick the closest catalogue row. Only if nothing fits, invent a short Indonesian category/group/item and give
confidence below 50. Never answer anything but that JSON object."""


def _catalogue():
    """(category, group, item) triples: built-in rules + enabled RN Normalization Rule rows."""
    from rescue_net.intelligence.normalization import RULES

    rows = {(r["category"], r["group"], r["item"]) for r in RULES}
    if frappe.db.exists("DocType", "RN Normalization Rule"):
        for r in frappe.get_all("RN Normalization Rule", filters={"enabled": 1},
                                fields=["canonical_category", "canonical_group", "canonical_item"],
                                limit_page_length=2000):
            if r.canonical_item:
                rows.add((r.canonical_category or "", r.canonical_group or "", r.canonical_item))
    return sorted(rows)


def enqueue_unmatched_needs(limit=NEED_PER_RUN):
    """Recent logistic needs the keyword rules could not group get one AI job each (platform key)."""
    from rescue_net import api_ai

    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -NEED_LOOKBACK_DAYS)
    made = 0
    for n in frappe.get_all(
            "RN Logistic Need",
            filters={"creation": [">", cutoff], "canonical_group": ["in", ["", None]],
                     "normalization_status": ["!=", "accepted"]},
            fields=["name", "created_by_user"], order_by="creation asc", limit_page_length=limit * 4):
        if frappe.db.exists("RN AI Job", {"feature": "need_normalization", "ref_name": n.name}):
            continue
        enqueue("need_normalization", "platform", api_ai.PLATFORM_OWNER, n.created_by_user or "Administrator",
                "RN Logistic Need", n.name)
        made += 1
        if made >= limit:
            break
    return made


def _need_handler(job):
    """Ask the platform AI to place an unmatched need in the catalogue -> suggestion payload."""
    from rescue_net import api_ai

    key, model, provider = api_ai.resolve_platform_key()
    if not key:
        raise budget.AIUnavailable("key", "Belum ada kunci AI platform.")
    budget.check_allowed("platform", api_ai.PLATFORM_OWNER)
    need = frappe.get_doc("RN Logistic Need", job.ref_name)
    text = (need.raw_item_text or need.item_name or "").strip()
    if not text:
        raise ValueError("kebutuhan tanpa teks barang")
    log = dict(owner_type="platform", owner_id=api_ai.PLATFORM_OWNER, user_id=job.user_id, key_source="platform",
               provider=provider, model_name=model, disaster_event=need.disaster_event, q_chars=len(text),
               feature="need_normalization")
    system = NEED_SYSTEM.format(catalogue="\n".join(" | ".join(t) for t in _catalogue()))
    try:
        answer, usage = llm.chat(provider, key, model, system, [text], temperature=0, json_mode=True,
                                 max_tokens=300)
    except llm.LLMError as e:
        api_ai._log_ai_usage(**log, outcome="error", error_note=f"{e.kind} {e.note}")
        raise
    api_ai._log_ai_usage(**log, usage=usage, outcome="ok")
    parsed = llm.parse_json(answer) or {}
    proposed = {"canonical_category": str(parsed.get("category") or "").strip()[:140],
                "canonical_group": str(parsed.get("group") or "").strip()[:140],
                "canonical_item": str(parsed.get("item") or "").strip()[:140]}
    if not proposed["canonical_item"]:
        raise ValueError("AI tidak memberi barang baku")
    try:
        conf = max(0, min(100, int(float(parsed.get("confidence")))))
    except (TypeError, ValueError):
        conf = 50
    current = {f: need.get(f) for f in NEED_FIELDS}
    return {"provider": provider, "model": model,
            "payload": {"current": current, "proposed": proposed, "confidence": conf, "raw_text": text}}


HANDLERS = {"report_intake": _report_handler, "need_normalization": _need_handler}


def process_pending(limit=PER_RUN):
    """Hourly: run up to `limit` pending jobs, oldest first. A job whose AI is still
    unavailable stays pending without counting an attempt."""
    done = 0
    enqueue_unmatched_needs()
    for name in frappe.get_all("RN AI Job", filters={"status": "pending"}, order_by="creation asc",
                               pluck="name", limit_page_length=limit):
        job = frappe.get_doc("RN AI Job", name)
        handler = HANDLERS.get(job.feature)
        if not handler:
            continue
        try:
            out = handler(job)
        except budget.AIUnavailable:
            continue
        except Exception as e:
            job.attempts = int(job.attempts or 0) + 1
            job.last_error = str(e)[:140]
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "failed"
            job.save(ignore_permissions=True)
            continue
        sug = frappe.get_doc({
            "doctype": "RN AI Suggestion", "feature": job.feature, "ref_doctype": job.ref_doctype,
            "ref_name": job.ref_name, "owner_type": job.owner_type, "owner_id": job.owner_id,
            "provider": out["provider"], "model_name": out["model"], "payload": json.dumps(out["payload"], default=str),
            "status": "draft"}).insert(ignore_permissions=True)
        job.status, job.suggestion, job.processed_at = "done", sug.name, now_datetime()
        job.save(ignore_permissions=True)
        if job.ref_doctype == "RN Community Report":
            frappe.db.set_value("RN Community Report", job.ref_name, "ai_status", "ai_suggested")
        done += 1
    return done


def _can_decide(suggestion, actor):
    if is_system_manager() or (actor and actor.get("role") == "command_center"):
        return True
    if suggestion.ref_doctype == "RN Community Report":
        posko = frappe.db.get_value("RN Community Report", suggestion.ref_name, "posko")
        return bool(posko and can_manage_posko(actor, posko))
    if suggestion.ref_doctype == "RN Logistic Need":
        posko = frappe.db.get_value("RN Logistic Need", suggestion.ref_name, "posko")
        return bool(posko and can_manage_posko(actor, posko))
    return False


@frappe.whitelist()
def list_ai_suggestions(ref_doctype="RN Community Report", ref_name=None, status="draft"):
    """Suggestions the asker may decide (posko managers of the report's posko, Control Centre,
    System Manager)."""
    actor = rn_actor(required=True)
    filters = {"ref_doctype": ref_doctype}
    if ref_name:
        filters["ref_name"] = ref_name
    if status:
        filters["status"] = status
    out = []
    for s in frappe.get_all("RN AI Suggestion", filters=filters, order_by="creation desc", limit_page_length=100,
                            fields=["name", "feature", "ref_doctype", "ref_name", "provider", "model_name",
                                    "payload", "status", "creation"]):
        if _can_decide(frappe._dict(s), actor):
            s["payload"] = json.loads(s["payload"] or "{}")
            out.append(s)
    return out


@frappe.whitelist(methods=["POST"])
def decide_ai_suggestion(suggestion, decision):
    """A human accepts (applies the proposed fields) or rejects a suggestion."""
    actor = rn_actor(required=True)
    if decision not in ("accepted", "rejected"):
        frappe.throw("Keputusan harus 'accepted' atau 'rejected'.")
    sug = frappe.get_doc("RN AI Suggestion", suggestion)
    if not _can_decide(sug, actor):
        frappe.throw("Hanya posko laporan ini atau Control Centre yang dapat memutuskan saran AI.",
                     frappe.PermissionError)
    if sug.status != "draft":
        frappe.throw("Saran ini sudah diputuskan.")
    applied = {}
    if decision == "accepted" and sug.ref_doctype == "RN Community Report":
        proposed = (json.loads(sug.payload or "{}")).get("proposed") or {}
        applied = {f: v for f, v in proposed.items() if f in REPORT_FIELDS}
        if applied:
            frappe.db.set_value("RN Community Report", sug.ref_name, applied)
    if decision == "accepted" and sug.ref_doctype == "RN Logistic Need":
        proposed = (json.loads(sug.payload or "{}")).get("proposed") or {}
        applied = {f: v for f, v in proposed.items() if f in NEED_FIELDS and v}
        if applied:
            conf = (json.loads(sug.payload or "{}")).get("confidence")
            applied.update(normalization_source="ai", normalization_status="accepted")
            if conf is not None:
                applied["normalization_confidence"] = conf
            frappe.db.set_value("RN Logistic Need", sug.ref_name, applied)
    if sug.ref_doctype == "RN Community Report":
        frappe.db.set_value("RN Community Report", sug.ref_name, "ai_status",
                            "ai_applied" if decision == "accepted" else "ai_rejected")
        if decision == "accepted":
            frappe.db.set_value("RN Community Report", sug.ref_name, "intake_parser", f"ai:{sug.provider}")
    sug.status, sug.decided_by, sug.decided_at = decision, frappe.session.user, now_datetime()
    sug.save(ignore_permissions=True)
    return {"suggestion": sug.name, "status": decision, "applied": applied}
