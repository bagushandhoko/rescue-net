"""Control Centre — per-posko critical reasons and jiwa-berisiko counts (one deterministic status per posko, used by map, KPI and Bencana Aktif)."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    JIWA_ASPECTS,
    _DRILL_BLOCKED_FLOW,
    _DRILL_CLOSED_NEED,
    _JIWA_NEED_URGENCY,
    _MEDICAL_ACTIVE_ASSIGNMENT,
    _MEDICAL_OPEN_CASE,
    _fmt,
    _num,
    cols,
    event_filters,
)


def _medical_unstaffed_poskos(posko_names):
    """Posko names with an open RN Medical Case but no currently-active
    medical RN Volunteer Assignment there — patients present, nobody
    medically staffing them.

    This is the same "korban berisiko" read a human (or the AI situation
    analyst, which sees the raw case + assignment data) makes by eye —
    it needs to land in the deterministic situation/KPI computation too
    (map_points' "critical" count, the Bencana Aktif rollup), not stay a
    conclusion only visible at the consolidation/chat level while the
    posko's own status still reads normal.
    """
    names = [n for n in (posko_names or []) if n]
    if not names or not frappe.db.exists("DocType", "RN Medical Case"):
        return set()

    case_poskos = set()
    for c in frappe.get_all(
        "RN Medical Case",
        filters={"posko": ["in", names]},
        fields=["posko", "case_status"],
        limit_page_length=5000,
    ):
        if str(c.get("case_status") or "").lower() in _MEDICAL_OPEN_CASE:
            case_poskos.add(c.get("posko"))

    if not case_poskos or not frappe.db.exists("DocType", "RN Volunteer Assignment"):
        return case_poskos

    covered = set()
    for a in frappe.get_all(
        "RN Volunteer Assignment",
        filters={"posko": ["in", list(case_poskos)]},
        fields=["posko", "assignment_status", "assignment_type", "required_skill"],
        limit_page_length=5000,
    ):
        if str(a.get("assignment_status") or "").lower() not in _MEDICAL_ACTIVE_ASSIGNMENT:
            continue
        skill_text = (
            str(a.get("assignment_type") or "") + " " + str(a.get("required_skill") or "")
        ).lower()
        if "medi" in skill_text:
            covered.add(a.get("posko"))

    return case_poskos - covered


def _shelter_overcapacity_poskos(posko_names):
    """posko name -> {capacity, occupancy} for RN Shelter Occupancy rows
    over their capacity_total, restricted to posko_names.

    Same "one real signal, used everywhere" pattern as
    _medical_unstaffed_poskos — a shelter over capacity is critical
    regardless of whether anyone remembered to set operational_status.
    """
    names = [n for n in (posko_names or []) if n]
    if not names or not frappe.db.exists("DocType", "RN Shelter Occupancy"):
        return {}

    result = {}
    for o in frappe.get_all(
        "RN Shelter Occupancy",
        filters={"posko": ["in", names]},
        fields=["posko", "capacity_total", "current_occupancy"],
        limit_page_length=2000,
    ):
        cap = _num(o.get("capacity_total"))
        occ = _num(o.get("current_occupancy"))
        if cap <= 0 or occ <= cap:
            continue
        prev = result.get(o.get("posko"))
        if not prev or occ > prev["occupancy"]:
            result[o.get("posko")] = {"capacity": cap, "occupancy": occ}

    return result


def _logistics_gap_poskos(posko_names):
    """posko name -> number of open CRITICAL RN Logistic Needs, restricted to
    poskos that have NO distribution flow actually moving towards them.

    "Moving" = any RN Distribution Flow with destination_posko == posko whose
    status is not in _DRILL_BLOCKED_FLOW (in_transit / dispatched / arrived /
    received* / stock_transferred all count; assigned_pickup, pending,
    cancelled ... do not). A critical need with nothing en route is a real
    risk that a human reads straight off the board — same "one real signal,
    used everywhere" rule as _medical_unstaffed_poskos, not something to
    leave visible only in the kebutuhan_kritis rollup.

    Only urgency == "critical" counts (not urgent/high) so this stays a
    conservative flag rather than turning most poskos red.
    """
    names = [n for n in (posko_names or []) if n]
    if not names or not frappe.db.exists("DocType", "RN Logistic Need"):
        return {}

    critical = {}
    for n in frappe.get_all(
        "RN Logistic Need",
        filters={"posko": ["in", names]},
        fields=["posko", "urgency", "need_status"],
        limit_page_length=5000,
    ):
        if str(n.get("urgency") or "").lower() != "critical":
            continue
        if str(n.get("need_status") or "open").lower() in _DRILL_CLOSED_NEED:
            continue
        critical[n.get("posko")] = critical.get(n.get("posko"), 0) + 1

    if not critical or not frappe.db.exists("DocType", "RN Distribution Flow"):
        return critical

    supplied = set()
    for f in frappe.get_all(
        "RN Distribution Flow",
        filters={"destination_posko": ["in", list(critical)]},
        fields=["destination_posko", "flow_status"],
        limit_page_length=5000,
    ):
        if str(f.get("flow_status") or "").lower() not in _DRILL_BLOCKED_FLOW:
            supplied.add(f.get("destination_posko"))

    return {p: c for p, c in critical.items() if p not in supplied}


def _derived_critical_reasons(posko_names):
    """posko name -> [human-readable reasons] for every posko that is
    critical because of a deterministic derived signal, independent of its
    manually-set operational_status. The single place the three signals
    (medical unstaffed, shelter over capacity, critical need with nothing
    en route) are combined, so map_points(), the Bencana Aktif board and the
    Posko Kritis drill can never disagree about which poskos are critical."""
    names = [n for n in (posko_names or []) if n]
    reasons = {}
    for p in _medical_unstaffed_poskos(names):
        reasons.setdefault(p, []).append("Kasus medis terbuka, belum ada tenaga medis aktif")
    # No capacity/occupancy figures in the text: these reasons also surface on
    # the guest-safe Bencana Aktif board; the numbers live on shelter-detail,
    # which has its own access control.
    for p in _shelter_overcapacity_poskos(names):
        reasons.setdefault(p, []).append("Shelter melebihi kapasitas")
    for p, c in _logistics_gap_poskos(names).items():
        reasons.setdefault(p, []).append(
            "%d kebutuhan kritis terbuka, belum ada distribusi yang bergerak" % c)
    return reasons


def _jiwa_berisiko_by_posko(posko_names):
    """posko name -> {"jiwa": people at risk, "aspects": {"medis"|"shelter"|"logistik": people},
    "reasons": [..], "missing": bool}.

    PEOPLE, not records. Per posko the largest of three deterministic signals
    (max, not sum: the same people show up in several of them):
      * medis    — open RN Medical Case rows of people (1 case = 1 patient;
                 `patient_kind` = satwa is excluded);
      * shelter  — a shelter over its capacity: all its current occupants;
      * logistik — an open critical/urgent RN Logistic Need with no
                   distribution flow moving to the posko: the people that need
                   it (`jiwa_terdampak` on the need, else the posko's jiwa
                   dilayani, else its shelter occupancy).
    `missing` = a logistics risk exists but the posko never reported how many
    people it concerns, so it counts 0 — shown as "data jiwa belum dilaporkan"
    so the posko can fix its data instead of silently disappearing.
    Used by the Control Centre KPI + drill and the Bencana Aktif board, so all
    of them show the same number."""
    names = [n for n in (posko_names or []) if n]
    out = {}
    if not names:
        return out

    def slot(p):
        return out.setdefault(p, {"jiwa": 0, "reasons": [], "missing": False, "_by": {}})

    # medis
    if frappe.db.exists("DocType", "RN Medical Case"):
        per = {}
        has_kind = "patient_kind" in cols("RN Medical Case")
        for c in frappe.get_all("RN Medical Case", filters={"posko": ["in", names]},
                                fields=["posko", "case_status"] + (["patient_kind"] if has_kind else []),
                                limit_page_length=5000):
            if str(c.get("patient_kind") or "manusia").lower() == "satwa":
                continue  # animals are treated here but are not "jiwa"
            if str(c.get("case_status") or "active").lower() in _MEDICAL_OPEN_CASE:
                per[c.get("posko")] = per.get(c.get("posko"), 0) + 1
        for p, n in per.items():
            slot(p)["_by"]["medis"] = n
            slot(p)["reasons"].append("%d pasien masih ditangani" % n)

    # shelter overload
    for p, o in _shelter_overcapacity_poskos(names).items():
        slot(p)["_by"]["shelter"] = int(o["occupancy"])
        slot(p)["reasons"].append("shelter melebihi kapasitas")

    # logistik: open critical/urgent needs with nothing en route
    needs = {}
    ncols = cols("RN Logistic Need")
    nfields = ["posko", "urgency", "need_status", "item_name"] + (["jiwa_terdampak"] if "jiwa_terdampak" in ncols else [])
    for n in frappe.get_all("RN Logistic Need", filters={"posko": ["in", names]},
                            fields=nfields, limit_page_length=5000):
        if str(n.get("urgency") or "").lower() not in _JIWA_NEED_URGENCY:
            continue
        if str(n.get("need_status") or "open").lower() in _DRILL_CLOSED_NEED:
            continue
        needs.setdefault(n.get("posko"), []).append(n)
    if needs and frappe.db.exists("DocType", "RN Distribution Flow"):
        for f in frappe.get_all("RN Distribution Flow", filters={"destination_posko": ["in", list(needs)]},
                                fields=["destination_posko", "flow_status"], limit_page_length=5000):
            if str(f.get("flow_status") or "").lower() not in _DRILL_BLOCKED_FLOW:
                needs.pop(f.get("destination_posko"), None)
    if needs:
        bene = {r.name: int(_num(r.get("rn_beneficiary_count")))
                for r in frappe.get_all("RN Posko", filters={"name": ["in", list(needs)]},
                                        fields=["name"] + (["rn_beneficiary_count"] if "rn_beneficiary_count" in cols("RN Posko") else []),
                                        limit_page_length=1000)}
        occ = {}
        if frappe.db.exists("DocType", "RN Shelter Occupancy"):
            for o in frappe.get_all("RN Shelter Occupancy", filters={"posko": ["in", list(needs)]},
                                    fields=["posko", "current_occupancy"], limit_page_length=2000):
                occ[o.get("posko")] = max(occ.get(o.get("posko"), 0), int(_num(o.get("current_occupancy"))))
        for p, rows in needs.items():
            declared = max([int(_num(r.get("jiwa_terdampak"))) for r in rows] or [0])
            people = declared or bene.get(p) or occ.get(p) or 0
            s_ = slot(p)
            items = sorted({r.get("item_name") or "-" for r in rows})
            s_["reasons"].append("%d kebutuhan mendesak belum dikirim (%s)" % (len(rows), ", ".join(items[:3])))
            if people:
                s_["_by"]["logistik"] = people
            else:
                s_["missing"] = True

    for p, s_ in out.items():
        s_["aspects"] = {k: int(v) for k, v in s_.pop("_by").items()}
        s_["jiwa"] = max(s_["aspects"].values() or [0])
        if s_["missing"] and not s_["jiwa"]:
            s_["reasons"].append("data jiwa belum dilaporkan posko")
    return out


def jiwa_aspect_totals(jiwa_by):
    """People per aspect across poskos. Aspects overlap (the same people can be
    in an overloaded shelter AND wait for an urgent need), so their sum can be
    larger than the Jiwa Berisiko total, which takes the largest aspect per posko."""
    return {k: sum(j["aspects"].get(k, 0) for j in jiwa_by.values()) for k, _ in JIWA_ASPECTS}


def _aspect_text(aspects):
    return " · ".join("%s %s" % (label, _fmt(aspects[k])) for k, label in JIWA_ASPECTS if aspects.get(k))


def _reasons_visible_to_viewer(posko_names):
    """Subset of posko_names whose derived-critical reasons the current viewer
    may see (effective share mode "full"). Fails closed: any error -> none."""
    names = [n for n in (posko_names or []) if n]
    if not names:
        return set()
    try:
        from rescue_net.visibility import effective_posko_share
        from rescue_net.access_policy import rn_actor
    except Exception:
        return set()
    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None
    visible = set()
    for n in names:
        try:
            if effective_posko_share(n, actor).get("mode") == "full":
                visible.add(n)
        except Exception:
            pass
    return visible


def _event_posko_names(event):
    return [
        p["name"]
        for p in frappe.get_all(
            "RN Posko",
            filters=event_filters(cols("RN Posko"), event),
            fields=["name"],
            limit_page_length=1000,
        )
    ]
