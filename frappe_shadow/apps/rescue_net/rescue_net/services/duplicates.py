"""Rule-based duplicate judgement for two logistic needs (ADR-0002 section 5 fallback).

The pair already arrives flagged as close + same canonical item
(api_frontend_bridge.duplicate_candidates), so the rule only looks at what the AI
would weigh next: how far apart in time the two reports are and how close the
quantities are in the same unit."""

from frappe.utils import get_datetime

SAME_QTY = 0.10  # within 10% = same quantity
FAR_QTY = 3.0  # more than 3x apart = a different need
WINDOW_HOURS = 48


def rule_verdict(a, b):
    """-> {"verdict": duplicate | different | unclear, "answer": text, "reasons": [...]}"""
    reasons = []
    qa, qb = float(a.get("quantity") or 0), float(b.get("quantity") or 0)
    same_unit = (a.get("unit") or "").strip().lower() == (b.get("unit") or "").strip().lower()
    hours = None
    if a.get("observed_at") and b.get("observed_at"):
        hours = abs((get_datetime(a["observed_at"]) - get_datetime(b["observed_at"])).total_seconds()) / 3600
    same_posko = a.get("posko") and a.get("posko") == b.get("posko")

    close_qty = same_unit and qa > 0 and qb > 0 and abs(qa - qb) / max(qa, qb) <= SAME_QTY
    far_qty = same_unit and qa > 0 and qb > 0 and max(qa, qb) / min(qa, qb) > FAR_QTY
    close_time = hours is not None and hours <= WINDOW_HOURS

    if same_posko:
        reasons.append("posko sama")
    if close_qty:
        reasons.append("jumlah hampir sama")
    if far_qty:
        reasons.append("jumlah berbeda jauh")
    if hours is not None:
        reasons.append(f"selisih waktu {hours:.0f} jam")
    if not same_unit:
        reasons.append("satuan berbeda")

    if close_qty and close_time:
        verdict = "duplicate"
    elif far_qty or (hours is not None and not close_time and not same_posko):
        verdict = "different"
    else:
        verdict = "unclear"
    text = {"duplicate": "DUPLIKAT", "different": "BEDA", "unclear": "TIDAK JELAS"}[verdict]
    return {"verdict": verdict, "reasons": reasons,
            "answer": f"{text} (aturan, tanpa AI): " + (", ".join(reasons) or "data pembanding terbatas") + "."}
