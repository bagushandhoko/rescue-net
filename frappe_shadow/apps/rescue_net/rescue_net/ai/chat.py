"""AI — questions and the manual analysis buttons, through services/llm.py."""

import hashlib
import json

import frappe
from frappe.rate_limiter import rate_limit
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import now_datetime

from rescue_net.access_policy import (
    can_manage_organization,
    is_system_manager,
    rn_actor,
)
from rescue_net.services import llm

from rescue_net.ai.common import (  # noqa: F401
    _assert_self,
    _model_for,
    _prov,
)
from rescue_net.ai.context import (  # noqa: F401
    context,
)
from rescue_net.ai.keys import (  # noqa: F401
    _log_ai_usage,
    _resolve_ai_key,
)
from rescue_net.ai.public import (  # noqa: F401
    _loads_json_safe,
)


@frappe.whitelist()
def ask(
    user_id,
    disaster_event_id,
    question,
    provider="auto",
):
    _actor, user_id = _assert_self(
        user_id
    )

    question = (question or "").strip()

    if not question:
        frappe.throw(
            "Question is required"
        )

    provider = _prov(provider, allow_auto=True)

    # Personal key first, then the asker's approved-organisation key (BYOK).
    api_key, model_name, key_source, key_owner_type, key_owner_id, provider = _resolve_ai_key(
        user_id, provider
    )

    if not api_key:
        frappe.throw(
            "Belum ada kunci AI aktif untuk Anda atau organisasi Anda. "
            "Tambahkan di AI Settings."
        )

    ctx = context(
        disaster_event_id
    )

    compact = {
        "summary":
            ctx.get("summary"),
        "alerts":
            ctx.get("alerts", [])[:30],
        "recommendations":
            ctx.get(
                "recommendations",
                [],
            )[:30],
        "stock_summary":
            ctx.get(
                "stock_summary",
                [],
            )[:80],
        "logistic_needs":
            ctx.get(
                "logistic_needs",
                [],
            )[:80],
        "aid_offers":
            ctx.get(
                "aid_offers",
                [],
            )[:80],
        "distribution_flows":
            ctx.get(
                "distribution_flows",
                [],
            )[:80],
        "kitchen_meal_productions":
            ctx.get(
                "kitchen_meal_productions",
                [],
            )[:50],
        "medical_cases":
            ctx.get(
                "medical_cases",
                [],
            )[:50],
        "shelter_occupancies":
            ctx.get(
                "shelter_occupancies",
                [],
            )[:50],
        "shelter_needs":
            ctx.get(
                "shelter_needs",
                [],
            )[:50],
        "missing_person_reports":
            ctx.get(
                "missing_person_reports",
                [],
            )[:50],
        "found_person_reports":
            ctx.get(
                "found_person_reports",
                [],
            )[:50],
        "search_found_matches":
            ctx.get(
                "search_found_matches",
                [],
            )[:50],
        "resource_profiles":
            ctx.get(
                "resource_profiles",
                [],
            )[:80],
        "recovery_projects":
            ctx.get(
                "recovery_projects",
                [],
            )[:80],
        "special_programs":
            ctx.get(
                "special_programs",
                [],
            )[:80],
        "community_reports_predicted_needs":
            ctx.get(
                "community_reports_predicted_needs",
                [],
            )[:50],
    }

    system_prompt = """
You are Rescue-Net AI Situation Analyst.
Analyze disaster response data operationally.
Be concise, practical, and safety-focused.
Never expose API keys or credentials.
For medical/search-found data, do not infer
or expose unnecessary personal identity.
Prioritize urgent needs, logistics gaps,
shelter capacity, medical risk, stock
shortages, resource availability and
recovery coordination.
community_reports_predicted_needs holds
heuristic equipment/logistics estimates
computed from unverified citizen reports
(damage scale or affected-people count) -
treat these as early, unconfirmed signals
to flag for follow-up, not as verified
operational facts.
"""

    answer = _llm_chat(
        api_key, model_name, system_prompt,
        ["Rescue-Net context JSON:\n" + json.dumps(compact, default=str), question],
        user_id, key_source, key_owner_type, key_owner_id, provider,
        disaster_event=disaster_event_id, q_chars=len(question), temperature=0.2,
    )

    return {
        "user_id": user_id,
        "provider": provider,
        "key_source": key_source,
        "model_name":
            model_name,
        "disaster_event_id":
            disaster_event_id,
        "question": question,
        "answer": answer,
        "context_summary":
            ctx.get("summary"),
        "alerts_count":
            len(ctx.get("alerts", [])),
        "recommendations_count":
            len(
                ctx.get(
                    "recommendations",
                    [],
                )
            ),
    }


@frappe.whitelist()
@rate_limit(limit=20, seconds=60 * 60)
def analyze_duplicate_candidate(user_id, object_id_a, object_id_b, provider="auto"):
    """Manual, on-demand AI judgment for one duplicate-candidate pair from
    api_frontend_bridge.duplicate_candidates() (pure geo-distance + same-
    item matching, no AI). Owner's own choice: this is deliberately
    per-pair and operator-triggered, never automatic on page load — it's
    a real paid API call against the operator's own BYOK key."""
    _actor, user_id = _assert_self(
        user_id
    )

    provider = _prov(provider, allow_auto=True)

    api_key, model_name, key_source, key_owner_type, key_owner_id, provider = _resolve_ai_key(
        user_id, provider
    )

    if not api_key:
        frappe.throw(
            "Belum ada kunci AI aktif untuk Anda atau organisasi Anda. "
            "Tambahkan di Setting."
        )

    def _need_brief(name):
        if not frappe.db.exists("RN Logistic Need", name):
            return None

        doc = frappe.db.get_value(
            "RN Logistic Need",
            name,
            [
                "item_name", "raw_item_text", "quantity", "unit",
                "posko", "disaster_event", "observed_at",
            ],
            as_dict=True,
        )

        posko_title = (
            frappe.db.get_value("RN Posko", doc.posko, "title")
            if doc.posko else None
        )

        return {
            "id": name,
            "item": doc.item_name,
            "raw_text": doc.raw_item_text,
            "quantity": doc.quantity,
            "unit": doc.unit,
            "posko": posko_title or doc.posko,
            "observed_at": str(doc.observed_at) if doc.observed_at else None,
            "disaster_event": doc.disaster_event,
        }

    need_a = _need_brief(object_id_a)
    need_b = _need_brief(object_id_b)

    if not need_a or not need_b:
        frappe.throw("Salah satu kebutuhan (RN Logistic Need) tidak ditemukan.")

    system_prompt = """
You are Rescue-Net's duplicate-need reviewer. You are given two
logistics need records already flagged as geographically close (or
same-village) candidates for the same canonical item. Judge whether
they most likely describe the SAME real-world need (should be merged /
treated as one, not summed) or are genuinely DIFFERENT needs that just
happen to be nearby. Consider the raw text, quantity, and posko.
Respond in Indonesian. The FIRST LINE of your answer must be exactly
one word: "DUPLIKAT" or "BEDA". Then 1-2 short sentences of reasoning.
Never expose API keys or credentials.
"""

    answer = _llm_chat(
        api_key, model_name, system_prompt,
        "Kebutuhan A:\n" + json.dumps(need_a, default=str)
        + "\n\nKebutuhan B:\n" + json.dumps(need_b, default=str),
        user_id, key_source, key_owner_type, key_owner_id, provider,
        disaster_event=need_a.get("disaster_event"), temperature=0.1,
    )

    first_line = (answer or "").strip().splitlines()[0].strip().upper() if answer else ""
    if "DUPLIKAT" in first_line:
        verdict = "duplicate"
    elif "BEDA" in first_line:
        verdict = "different"
    else:
        verdict = "unclear"

    return {
        "object_id_a": object_id_a,
        "object_id_b": object_id_b,
        "verdict": verdict,
        "answer": answer,
        "model_name": model_name,
        "key_source": key_source,
    }


def _llm_chat(api_key, model_name, system_prompt, user_content,
              user_id, key_source, key_owner_type, key_owner_id,
              provider, disaster_event=None, q_chars=0, temperature=0.1,
              json_mode=False):
    """One chat call for every AI feature, any provider (services/llm.py):
    request, error mapping and the RN AI Usage Log row live here once."""
    model_name = _model_for(provider, model_name)
    log = dict(owner_type=key_owner_type, owner_id=key_owner_id, user_id=user_id,
               key_source=key_source, provider=provider, model_name=model_name,
               disaster_event=disaster_event, q_chars=q_chars)
    try:
        answer, usage = llm.chat(provider, api_key, model_name, system_prompt, user_content,
                                 temperature=temperature, json_mode=json_mode)
    except llm.LLMError as e:
        _log_ai_usage(**log, outcome="auth_error" if e.kind == "auth" else "error",
                      error_note=f"{e.kind} {e.note}".strip())
        if e.kind == "auth":
            frappe.throw("Permintaan AI gagal: kunci API ditolak. Perbarui kunci di AI Settings.",
                         frappe.AuthenticationError)
        if e.kind == "refusal":
            frappe.throw("Provider AI menolak permintaan ini.")
        frappe.throw("Permintaan AI gagal. Periksa provider, model, kuota, dan jaringan.")
    _log_ai_usage(**log, a_chars=len(answer or ""), usage=usage, outcome="ok")
    return answer


@frappe.whitelist()
def analyze_rollup_group(user_id, disaster_event, group_key, provider="auto"):
    """Manual, on-demand AI judgment for one Rollup Nasional group on
    Sync Data Konsolidasi's Konsolidasi Logistik tab — advisory only,
    never applied automatically. The operator reads the suggestion, then
    decides whether to leave the MAX-rule estimate as-is or use
    api_frontend_bridge.set_consolidation_override() to record their own
    judgment (see that function's docstring)."""
    _actor, user_id = _assert_self(user_id)

    provider = _prov(provider, allow_auto=True)

    api_key, model_name, key_source, key_owner_type, key_owner_id, provider = _resolve_ai_key(
        user_id, provider
    )
    if not api_key:
        frappe.throw(
            "Belum ada kunci AI aktif untuk Anda atau organisasi Anda. "
            "Tambahkan di Setting."
        )

    from rescue_net.api_intelligence import _fetch_need_rows, _group_rows
    from rescue_net.reference_resolver import resolve_disaster_event

    event = resolve_disaster_event(disaster_event) or disaster_event
    groups = _group_rows(_fetch_need_rows(disaster_event=event))
    group = next((g for g in groups if g["group_key"] == group_key), None)

    if not group:
        frappe.throw("Group kebutuhan tidak ditemukan (mungkin sudah berubah — muat ulang).")

    system_prompt = """
You are Rescue-Net's logistics-consolidation reviewer. You are given one
consolidated need group: its raw source reports (item, quantity, posko,
verification status) and the MAX-overlap-safe estimate computed from
them. Judge whether that estimate looks reasonable given the sources, or
flag a concern (e.g. sources look like they might double-count the same
delivery, or the estimate seems too low/high for the source count).
Respond in Indonesian, 2-4 short sentences. You may suggest a corrected
number but make clear it is only a suggestion — the operator decides.
Never expose API keys or credentials.
"""

    user_content = (
        "Group: " + json.dumps({
            "canonical_group": group.get("canonical_group"),
            "area": group.get("area"),
            "base_unit": group.get("base_unit"),
            "qty_measurable": group.get("qty_measurable"),
            "qty_estimated": group.get("qty_estimated"),
            "qty_total": group.get("qty_total"),
            "source_count": group.get("source_count"),
            "independent_source_count": group.get("independent_source_count"),
            "confidence_label": group.get("confidence_label"),
        }, default=str)
        + "\n\nRaw sources:\n"
        + json.dumps(group.get("sources") or [], default=str)
    )

    answer = _llm_chat(
        api_key, model_name, system_prompt, user_content,
        user_id, key_source, key_owner_type, key_owner_id, provider,
        disaster_event=event,
    )

    # Cached onto the override doctype (even with no override set yet) so
    # the suggestion survives a page reload instead of vanishing the
    # moment the operator navigates away.
    if frappe.db.exists("RN Consolidation Group Override", group_key):
        doc = frappe.get_doc("RN Consolidation Group Override", group_key)
    else:
        doc = frappe.get_doc({
            "doctype": "RN Consolidation Group Override",
            "override_key": group_key,
            "disaster_event": event,
            "group_key": group_key,
            "override_qty": group.get("qty_total"),
            "status": "cleared",
        })
    doc.ai_suggestion = answer
    doc.ai_asked_at = now_datetime()
    doc.flags.ignore_permissions = True
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"group_key": group_key, "answer": answer, "model_name": model_name}


@frappe.whitelist()
def analyze_sync_conflict(user_id, sync_log_id, provider="auto"):
    """Manual, on-demand AI judgment for one entry in "Server Sync
    Conflicts" on Sync Data Konsolidasi's Sync Offline ↔ Online tab —
    advisory only. The operator still resolves the conflict themselves
    via the existing Retry Conflicts flow; this never auto-applies
    anything."""
    _actor, user_id = _assert_self(user_id)

    provider = _prov(provider, allow_auto=True)

    api_key, model_name, key_source, key_owner_type, key_owner_id, provider = _resolve_ai_key(
        user_id, provider
    )
    if not api_key:
        frappe.throw(
            "Belum ada kunci AI aktif untuk Anda atau organisasi Anda. "
            "Tambahkan di Setting."
        )

    log = frappe.db.get_value(
        "RN Sync Log", sync_log_id,
        ["object_type", "object_id", "operation", "apply_status",
         "conflict_status", "error_message", "payload_json",
         "apply_result_json", "event_id", "source_device_id"],
        as_dict=True,
    )
    if not log:
        frappe.throw("RN Sync Log tidak ditemukan.")

    system_prompt = """
You are Rescue-Net's offline-sync conflict reviewer. You are given one
sync log entry that failed to apply cleanly (rejected or flagged for
review) when a field device pushed it to the server, including the
payload it sent and the server's error/reason. Explain in plain
Indonesian, in 2-4 short sentences, what likely went wrong and what the
operator should check or do next (e.g. "retry once online data
refreshed", "check if the resource is already booked", "data device
mungkin sudah usang, tarik ulang dulu"). Never expose API keys or
credentials.
"""

    user_content = json.dumps({
        "object_type": log.object_type,
        "object_id": log.object_id,
        "operation": log.operation,
        "apply_status": log.apply_status,
        "conflict_status": log.conflict_status,
        "error_message": log.error_message,
        "payload": _loads_json_safe(log.payload_json),
        "apply_result": _loads_json_safe(log.apply_result_json),
    }, default=str)

    answer = _llm_chat(
        api_key, model_name, system_prompt, user_content,
        user_id, key_source, key_owner_type, key_owner_id, provider,
        disaster_event=log.event_id,
    )

    return {"sync_log_id": sync_log_id, "answer": answer, "model_name": model_name}
