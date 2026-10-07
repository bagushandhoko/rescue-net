"""Search & Found: suggested matches and the board numbers.

Deterministic rules (ADR-0002: no LLM decides who is reunited with whom). A
suggestion is only a hint for an operator — it is never stored or confirmed
by itself.
"""

import re

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

SUBJECTS = ("orang", "aset", "hewan")
SUGGEST_MIN = 35
_STOP = {"dan", "yang", "di", "dengan", "warna", "ke", "dari", "the", "a", "ada", "sedang", "memakai", "baju", "pakai"}

# weights add up to 100; an unknown value on either side earns half credit
W_GENDER, W_AGE, W_CLOTHING, W_DESC, W_PLACE = 20, 25, 30, 15, 10


def _tokens(text):
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2 and t not in _STOP}


def _overlap(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return None
    return len(ta & tb) / len(ta | tb)


def match_score(missing, found):
    """0-100 likeness of a missing and a found report (rows or docs)."""
    g = lambda r, k: r.get(k) if hasattr(r, "get") else getattr(r, k, None)
    if (g(missing, "subject_type") or "orang") != (g(found, "subject_type") or "orang"):
        return 0
    total, hard_miss = 0.0, False

    gm, gf = g(missing, "gender"), g(found, "gender")
    if gm in (None, "", "unknown") or gf in (None, "", "unknown"):
        total += W_GENDER / 2
    elif gm == gf:
        total += W_GENDER
    else:
        hard_miss = True

    am, af = g(missing, "age_years"), g(found, "age_years")
    if not am or not af:
        total += W_AGE / 2
    else:
        d = abs(int(am) - int(af))
        if d <= 1:
            total += W_AGE
        elif d <= 3:
            total += W_AGE * 0.7
        elif d <= 8:
            total += W_AGE * 0.25
        elif d > 12:
            hard_miss = True

    for weight, a, b in (
        (W_CLOTHING, g(missing, "clothing_description"), g(found, "clothing_description")),
        (W_DESC, g(missing, "description"), g(found, "description")),
        (W_PLACE, g(missing, "last_seen_location"), g(found, "found_location")),
    ):
        o = _overlap(a, b)
        total += weight / 2 if o is None else weight * min(1.0, o * 2)
    score = total * (0.3 if hard_miss else 1.0)
    return max(0, min(100, int(round(score))))


def suggestions(missing, found, matches, limit=20):
    """Best open pairs that have no live match yet, highest score first."""
    taken = {(m["missing_report"], m["found_report"]) for m in matches
             if m.get("match_status") in ("proposed", "confirmed", "reunited")}
    open_f = [f for f in found if f.get("report_status") == "found"]
    out = []
    for m in missing:
        if m.get("report_status") != "missing":
            continue
        for f in open_f:
            if (m["name"], f["name"]) in taken:
                continue
            s = match_score(m, f)
            if s >= SUGGEST_MIN:
                out.append({"missing_report": m["name"], "found_report": f["name"], "score": s})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def present_fields(doctype, wanted):
    """Only the columns that exist (a deploy may reach the API before migrate)."""
    meta = frappe.get_meta(doctype)
    return [f for f in wanted if f in ("name", "creation") or meta.has_field(f)]


def last_day_count(rows, field="observed_at"):
    since = add_to_date(now_datetime(), hours=-24)
    n = 0
    for r in rows:
        v = r.get(field)
        if v and get_datetime(v) >= since:
            n += 1
    return n


def identification_counts(found):
    keys = ("belum_teridentifikasi", "proses_identifikasi", "teridentifikasi", "tidak_dapat_diidentifikasi")
    c = dict.fromkeys(keys, 0)
    for f in found:
        if (f.get("subject_type") or "orang") != "orang":
            continue
        st = f.get("identification_status")
        if f.get("report_status") == "reunited":
            st = "teridentifikasi"
        c[st if st in c else "belum_teridentifikasi"] += 1
    return c
