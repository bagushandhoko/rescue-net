"""Control Centre — KPI drilldowns, KPI totals, activity trends, public dashboard."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    KPI_DIMENSIONS,
    TREND_SOURCES,
    _DRILL_BLOCKED_FLOW,
    _DRILL_CLOSED_NEED,
    _DRILL_DELIVERED_OFFER,
    _DRILL_TITLES,
    _DRILL_URGENT,
    _fmt,
    _norm_item,
    _num,
    _sf,
    canonical_event,
    cols,
    event_filters,
    first,
)
from rescue_net.control_centre.critical import (  # noqa: F401
    _aspect_text,
    _event_posko_names,
    _jiwa_berisiko_by_posko,
    jiwa_aspect_totals,
)
from rescue_net.control_centre.map_evidence import (  # noqa: F401
    event_evidence,
    map_points,
    reports,
)


def _drill_jiwa(event, res, limit):
    """"Jiwa Berisiko" drill: one row per posko, quantity = people at risk."""
    names = _event_posko_names(event)
    titles = {p.name: p.title for p in frappe.get_all(
        "RN Posko", filters={"name": ["in", names or [""]]}, fields=["name", "title"], limit_page_length=1000)}
    rows = []
    for p, j in sorted(_jiwa_berisiko_by_posko(names).items(), key=lambda kv: -kv[1]["jiwa"]):
        rows.append({
            "id": p,
            "title": ("%s jiwa berisiko" % _fmt(j["jiwa"])) if j["jiwa"] else "Jumlah jiwa belum dilaporkan",
            "detail": ((_aspect_text(j["aspects"]) + " — ") if j["aspects"] else "") + "; ".join(j["reasons"]),
            "quantity": j["jiwa"],
            "unit": "jiwa",
            "gap": j["jiwa"],
            "status": "perlu dilengkapi" if j["missing"] and not j["jiwa"] else None,
            "priority": "critical" if j["jiwa"] else None,
            "_posko": p,
        })
    return rows[:limit]


class _OrgResolver:
    """posko name -> organisation row + effective Control Centre share mode,
    with per-call caching so a drill-down touches each posko/org once."""

    def __init__(self, actor):
        self.actor = actor
        self._posko = {}
        self._org = {}
        self._mode = {}
        try:
            from rescue_net.visibility import effective_posko_share
            self._share_fn = effective_posko_share
        except Exception:
            self._share_fn = None

    def posko(self, name):
        if name not in self._posko:
            self._posko[name] = frappe.db.get_value(
                "RN Posko", name,
                ["name", "legacy_id", "title", "organization"],
                as_dict=True,
            ) or {}
        return self._posko[name]

    def org(self, org_name):
        if not org_name:
            return {}
        if org_name not in self._org:
            self._org[org_name] = frappe.db.get_value(
                "RN Organization", org_name,
                ["name", "title", "organization_type",
                 "control_centre_share", "privacy_mode"],
                as_dict=True,
            ) or {}
        return self._org[org_name]

    def share_mode(self, posko_name):
        if not posko_name:
            return "summary"
        if posko_name not in self._mode:
            mode = "summary"
            if self._share_fn:
                try:
                    mode = self._share_fn(
                        posko_name, self.actor
                    ).get("mode", "summary")
                except Exception:
                    mode = "summary"
            self._mode[posko_name] = mode
        return self._mode[posko_name]


def _drill_kebutuhan(event, res, limit):
    import json

    rows = []
    for n in frappe.get_all(
        "RN Logistic Need",
        filters=event_filters(cols("RN Logistic Need"), event),
        fields=_sf("RN Logistic Need", [
            "name", "item_name", "quantity", "unit", "urgency",
            "need_status", "posko", "needed_before", "legacy_payload", "modified",
            "jiwa_terdampak",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        status = str(n.get("need_status") or "open").lower()
        if status in _DRILL_CLOSED_NEED:
            continue

        payload = n.get("legacy_payload")
        if isinstance(payload, str) and payload.strip():
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        if not isinstance(payload, dict):
            payload = {}

        required = _num(payload.get("required_quantity") or n.get("quantity"))
        realized = _num(payload.get("realized_quantity"))
        if realized > required > 0:
            realized = required

        rows.append({
            "id": n.get("name"),
            "title": n.get("item_name") or "Kebutuhan",
            "detail": (
                f"butuh {_fmt(required)} {n.get('unit') or ''}".strip()
                + (f" · realisasi {_fmt(realized)}" if realized else "")
                + (f" · untuk {_fmt(n.get('jiwa_terdampak'))} jiwa" if n.get("jiwa_terdampak") else "")
            ),
            "jiwa": int(_num(n.get("jiwa_terdampak"))),
            "quantity": required,
            "unit": n.get("unit"),
            "gap": max(0.0, required - realized),
            "status": status,
            "priority": n.get("urgency"),
            "when": n.get("needed_before"),
            "_posko": n.get("posko"),
        })

    if frappe.db.exists("DocType", "RN Shelter Need"):
        posko_names = _event_posko_names(event)
        if posko_names:
            for s in frappe.get_all(
                "RN Shelter Need",
                filters={"posko": ["in", posko_names]},
                fields=_sf("RN Shelter Need", [
                    "name", "item_name", "quantity_needed", "unit", "priority",
                    "need_status", "posko", "needed_before",
                ]),
                limit_page_length=limit,
            ):
                status = str(s.get("need_status") or "open").lower()
                if status in _DRILL_CLOSED_NEED:
                    continue
                req = _num(s.get("quantity_needed"))
                rows.append({
                    "id": s.get("name"),
                    "title": (s.get("item_name") or "Kebutuhan shelter") + " (shelter)",
                    "detail": f"butuh {_fmt(req)} {s.get('unit') or ''}".strip(),
                    "quantity": req,
                    "unit": s.get("unit"),
                    "gap": req,
                    "status": status,
                    "priority": s.get("priority"),
                    "when": s.get("needed_before"),
                    "_posko": s.get("posko"),
                })
    return rows


def _drill_posko_kritis(event, res, limit):
    rows = []
    for p in map_points(event):
        if p.get("situation") != "critical":
            continue
        rows.append({
            "id": p.get("posko_id"),
            "title": p.get("name"),
            "detail": " · ".join(x for x in [
                p.get("posko_type"), p.get("address"),
                "; ".join(p.get("critical_reasons") or []),
            ] if x),
            "quantity": 0,
            "unit": None,
            "gap": 0,
            "status": p.get("status"),
            "priority": "critical",
            "when": None,
            "_posko": p.get("posko_id"),
        })
    return rows


def _drill_flows(event, res, limit, only_blocked):
    rows = []
    for f in frappe.get_all(
        "RN Distribution Flow",
        filters=event_filters(cols("RN Distribution Flow"), event),
        fields=_sf("RN Distribution Flow", [
            "name", "item_name", "quantity", "unit", "flow_status",
            "source_posko", "destination_posko", "eta_final",
            "transport_provider", "transport_type", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        st = str(f.get("flow_status") or "").lower()
        if only_blocked and st not in _DRILL_BLOCKED_FLOW:
            continue
        transport = f.get("transport_type") or f.get("transport_provider")
        rows.append({
            "id": f.get("name"),
            "title": f.get("item_name") or "Distribusi",
            "detail": (
                (f.get("source_posko") or "?") + " → "
                + (f.get("destination_posko") or "?")
                + (f" · {transport}" if transport else "")
            ),
            "quantity": _num(f.get("quantity")),
            "unit": f.get("unit"),
            "gap": 0,
            "status": f.get("flow_status"),
            "priority": "urgent" if only_blocked else None,
            "when": f.get("eta_final"),
            "_posko": f.get("destination_posko") or f.get("source_posko"),
        })
    return rows


def _drill_distribusi(event, res, limit):
    return _drill_flows(event, res, limit, only_blocked=False)


def _drill_distribusi_terhambat(event, res, limit):
    return _drill_flows(event, res, limit, only_blocked=True)


def _drill_medis(event, res, limit):
    rows = []
    for m in frappe.get_all(
        "RN Medical Case",
        filters=event_filters(cols("RN Medical Case"), event),
        fields=_sf("RN Medical Case", [
            "name", "patient_code", "complaint", "severity", "triage_status",
            "case_status", "age_group", "gender", "posko", "observed_at",
        ]),
        order_by="observed_at desc",
        limit_page_length=limit,
    ):
        rows.append({
            "id": m.get("name"),
            "title": m.get("complaint") or m.get("patient_code") or "Kasus medis",
            "detail": " · ".join(x for x in [
                m.get("patient_code"), m.get("age_group"), m.get("gender"),
                (f"triase {m.get('triage_status')}" if m.get("triage_status") else None),
            ] if x),
            "quantity": 0,
            "unit": None,
            "gap": 0,
            "status": m.get("case_status") or m.get("triage_status"),
            "priority": m.get("severity"),
            "when": m.get("observed_at"),
            "_posko": m.get("posko"),
        })
    return rows


def _drill_donasi(event, res, limit):
    rows = []
    for o in frappe.get_all(
        "RN Aid Offer",
        filters=event_filters(cols("RN Aid Offer"), event),
        fields=_sf("RN Aid Offer", [
            "name", "donor_name", "item_name", "quantity", "unit",
            "offer_status", "target_posko", "ready_at", "pickup_location", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        st = str(o.get("offer_status") or "").lower()
        if st in _DRILL_DELIVERED_OFFER:
            continue
        rows.append({
            "id": o.get("name"),
            "title": o.get("item_name") or "Bantuan",
            "detail": " · ".join(x for x in [
                (f"dari {o.get('donor_name')}" if o.get("donor_name") else None),
                o.get("pickup_location"),
            ] if x),
            "quantity": _num(o.get("quantity")),
            "unit": o.get("unit"),
            "gap": 0,
            "status": o.get("offer_status"),
            "priority": None,
            "when": o.get("ready_at"),
            "_posko": o.get("target_posko"),
        })
    return rows


def _drill_stok(event, res, limit):
    rows = []
    seen = set()
    for o in frappe.get_all(
        "RN Stock Observation",
        filters=event_filters(cols("RN Stock Observation"), event),
        fields=_sf("RN Stock Observation", [
            "name", "item_name", "canonical_item", "quantity", "unit",
            "stock_state", "posko", "observed_at",
        ]),
        order_by="observed_at desc",
        limit_page_length=limit * 3,
    ):
        key = (o.get("posko"), _norm_item(o.get("canonical_item") or o.get("item_name")))
        if key in seen:
            continue
        seen.add(key)
        low = str(o.get("stock_state") or "").lower() in {
            "critical", "low", "menipis", "habis", "empty",
        }
        rows.append({
            "id": o.get("name"),
            "title": o.get("item_name") or "Barang",
            "detail": (o.get("stock_state") or "stok tercatat"),
            "quantity": _num(o.get("quantity")),
            "unit": o.get("unit"),
            "gap": 0,
            "status": o.get("stock_state"),
            "priority": "urgent" if low else None,
            "when": o.get("observed_at"),
            "_posko": o.get("posko"),
        })
    return rows


def _drill_relawan(event, res, limit):
    rows = []
    vcache = {}

    def vol_name(v):
        if not v:
            return None
        if v not in vcache:
            try:
                vcache[v] = frappe.db.get_value(
                    "RN Volunteer Profile", v, "volunteer_name"
                ) or v
            except Exception:
                vcache[v] = v
        return vcache[v]

    for a in frappe.get_all(
        "RN Volunteer Assignment",
        filters=event_filters(cols("RN Volunteer Assignment"), event),
        fields=_sf("RN Volunteer Assignment", [
            "name", "volunteer", "task_title", "assignment_type",
            "assignment_status", "required_skill", "priority", "posko", "shift_start",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        rows.append({
            "id": a.get("name"),
            "title": a.get("task_title") or a.get("assignment_type") or "Penugasan relawan",
            "detail": " · ".join(x for x in [
                vol_name(a.get("volunteer")), a.get("required_skill"),
                a.get("assignment_type"),
            ] if x),
            "quantity": 0,
            "unit": None,
            "gap": 0,
            "status": a.get("assignment_status"),
            "priority": a.get("priority"),
            "when": a.get("shift_start"),
            "_posko": a.get("posko"),
        })
    return rows


def _drill_program(event, res, limit):
    rows = []
    for d in frappe.get_all(
        "RN Donor Program",
        filters=event_filters(cols("RN Donor Program"), event),
        fields=_sf("RN Donor Program", [
            "name", "program_name", "program_type", "owner_type", "owner_id",
            "status", "target_amount", "target_unit", "current_amount",
            "location", "priority", "modified",
        ]),
        order_by="modified desc",
        limit_page_length=limit,
    ):
        tgt = _num(d.get("target_amount"))
        cur = _num(d.get("current_amount"))
        owner_is_org = str(d.get("owner_type") or "").lower() in {
            "organization", "org", "rn organization", "kelompok",
        }
        rows.append({
            "id": d.get("name"),
            "title": d.get("program_name") or "Program",
            "detail": " · ".join(x for x in [
                d.get("program_type"),
                (f"target {_fmt(tgt)} {d.get('target_unit') or ''}".strip() if tgt else None),
                (f"terkumpul {_fmt(cur)}" if cur else None),
                d.get("location"),
            ] if x),
            "quantity": tgt,
            "unit": d.get("target_unit"),
            "gap": max(0.0, tgt - cur),
            "status": d.get("status"),
            "priority": d.get("priority"),
            "when": None,
            "_posko": None,
            "_org_direct": d.get("owner_id") if owner_is_org else None,
            "_force_mode": None if owner_is_org else "full",
        })
    return rows


def _drill_search(event, res, limit):
    rows = []
    for dt, kind, loc_field, time_field in [
        ("RN Missing Person Report", "Hilang", "last_seen_location", "last_seen_time"),
        ("RN Found Person Report", "Ditemukan", "found_location", "found_time"),
    ]:
        if not frappe.db.exists("DocType", dt):
            continue
        for m in frappe.get_all(
            dt,
            filters=event_filters(cols(dt), event),
            fields=_sf(dt, [
                "name", "person_code", "person_name", loc_field, time_field,
                "report_status", "posko", "description",
            ]),
            order_by="modified desc",
            limit_page_length=limit,
        ):
            rows.append({
                "id": m.get("name"),
                "title": (m.get("person_name") or m.get("person_code") or "Orang")
                + f" ({kind})",
                "detail": " · ".join(x for x in [
                    m.get(loc_field), m.get("description"),
                ] if x),
                "quantity": 0,
                "unit": None,
                "gap": 0,
                "status": m.get("report_status"),
                "priority": "urgent" if kind == "Hilang" else None,
                "when": m.get(time_field),
                "_posko": m.get("posko"),
            })
    return rows


_DRILL_BUILDERS = {
    "jiwa": _drill_jiwa,
    "kebutuhan": _drill_kebutuhan,
    "posko_kritis": _drill_posko_kritis,
    "distribusi": _drill_distribusi,
    "distribusi_terhambat": _drill_distribusi_terhambat,
    "medis": _drill_medis,
    "donasi": _drill_donasi,
    "stok": _drill_stok,
    "relawan": _drill_relawan,
    "program": _drill_program,
    "search": _drill_search,
}


def _group_by_org(rows, dimension, res):
    groups = {}
    order = []

    for r in rows:
        posko_name = r.pop("_posko", None)
        org_direct = r.pop("_org_direct", None)
        force_mode = r.pop("_force_mode", None)

        if posko_name:
            p = res.posko(posko_name)
            org_row = res.org(p.get("organization")) if p.get("organization") else {}
            key = p.get("organization") or "__none__"
            mode = force_mode or res.share_mode(posko_name)
        else:
            p = {}
            org_row = res.org(org_direct) if org_direct else {}
            key = org_row.get("name") or "__none__"
            if force_mode:
                mode = force_mode
            else:
                share = (org_row.get("control_centre_share") or "aggregate").lower()
                mode = "full" if share == "full_authorized" else "summary"

        if key not in groups:
            order.append(key)
            groups[key] = {
                "organization": org_row.get("name"),
                "organization_title": (
                    org_row.get("title")
                    or ("Tanpa organisasi" if key == "__none__" else key)
                ),
                "organization_type": org_row.get("organization_type"),
                "control_centre_share": (
                    org_row.get("control_centre_share") or "aggregate"
                ),
                "privacy_mode": org_row.get("privacy_mode"),
                "count": 0,
                "shown_count": 0,
                "hidden_count": 0,
                "critical_count": 0,
                "total_quantity": 0.0,
                "total_gap": 0.0,
                "_poskos": set(),
                "_any_full": False,
                "items": [],
            }

        g = groups[key]
        g["count"] += 1
        if posko_name:
            g["_poskos"].add(posko_name)
        g["total_quantity"] += _num(r.get("quantity"))
        g["total_gap"] += _num(r.get("gap"))
        if (
            str(r.get("priority") or "").lower() in _DRILL_URGENT
            or str(r.get("status") or "").lower() in {"critical", "overload", "emergency"}
        ):
            g["critical_count"] += 1

        r["posko"] = posko_name
        r["posko_title"] = p.get("title")
        r["organization_title"] = g["organization_title"]

        if mode == "full":
            g["_any_full"] = True
            g["shown_count"] += 1
            g["items"].append(r)
        else:
            g["hidden_count"] += 1

    out = []
    for key in order:
        g = groups[key]
        g["posko_count"] = len(g.pop("_poskos"))
        g["share_mode"] = "full" if g.pop("_any_full") else "summary"
        g["total_quantity"] = round(g["total_quantity"], 1)
        g["total_gap"] = round(g["total_gap"], 1)
        out.append(g)

    out.sort(key=lambda x: (0 if x["share_mode"] == "full" else 1, -x["count"]))

    return {
        "dimension": dimension,
        "title": _DRILL_TITLES.get(dimension, dimension),
        "total": sum(g["count"] for g in out),
        "shown_total": sum(g["shown_count"] for g in out),
        "hidden_total": sum(g["hidden_count"] for g in out),
        "org_count": len(out),
        "groups": out,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def kpi_drilldown(disaster_event, dimension, limit=500):
    """Underlying records for one Control Centre KPI / module tile,
    grouped by the owning organisation and gated by that organisation's
    Control Centre sharing mode (open -> item rows; closed -> summary)."""
    event = canonical_event(disaster_event)
    dimension = str(dimension or "").strip().lower()

    builder = _DRILL_BUILDERS.get(dimension)
    if not builder:
        frappe.throw(f"Dimensi drill-down tidak dikenal: {dimension}")

    try:
        from rescue_net.access_policy import rn_actor
        try:
            actor = rn_actor(required=False)
        except Exception:
            actor = None
    except Exception:
        actor = None

    res = _OrgResolver(actor)
    rows = builder(event, res, int(limit))
    return _group_by_org(rows, dimension, res)


def _event_count(doctype, event):
    columns = cols(doctype)
    flt = event_filters(columns, event)
    return frappe.db.count(doctype, flt) if flt else 0


def _shelter_need_count(event):
    # same scope as _drill_kebutuhan: shelter needs of the event's poskos
    if not frappe.db.exists("DocType", "RN Shelter Need"):
        return 0
    names = _event_posko_names(event)
    return frappe.db.count("RN Shelter Need", {"posko": ["in", names]}) if names else 0


def _jiwa_dilayani_total(event):
    """People the event's poskos serve: jiwa dilayani (rn_beneficiary_count),
    else the posko's shelter occupancy, but at least its jiwa berisiko — the
    denominator of the Jiwa Berisiko bar."""
    names = _event_posko_names(event)
    if not names:
        return 0
    has_bene = "rn_beneficiary_count" in cols("RN Posko")
    bene = {r.name: int(_num(r.get("rn_beneficiary_count"))) for r in frappe.get_all(
        "RN Posko", filters={"name": ["in", names]},
        fields=["name"] + (["rn_beneficiary_count"] if has_bene else []), limit_page_length=1000)}
    occ = {}
    if frappe.db.exists("DocType", "RN Shelter Occupancy"):
        for o in frappe.get_all("RN Shelter Occupancy", filters={"posko": ["in", names]},
                                fields=["posko", "current_occupancy"], limit_page_length=2000):
            occ[o.get("posko")] = max(occ.get(o.get("posko"), 0), int(_num(o.get("current_occupancy"))))
    # people at risk at a posko are people it serves too (e.g. patients at a
    # posko that never filled jiwa dilayani) — never let the base fall below them
    risk = _jiwa_berisiko_by_posko(names)
    return sum(max(bene.get(p) or occ.get(p, 0), (risk.get(p) or {}).get("jiwa", 0)) for p in names)


def kpi_totals(event, posko_total=None):
    try:
        from rescue_net.access_policy import rn_actor
        actor = rn_actor(required=False)
    except Exception:
        actor = None
    res = _OrgResolver(actor)
    out = {}
    for dim in KPI_DIMENSIONS:
        try:
            rows = _DRILL_BUILDERS[dim](event, res, 500)
            # jiwa = people (sum of the drill rows' quantity), everything else = rows
            out[dim] = int(sum(_num(r.get("quantity")) for r in rows)) if dim == "jiwa" else len(rows)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "kpi_totals %s" % dim)
            out[dim] = None
    flows = _event_count("RN Distribution Flow", event)
    jiwa_by = _jiwa_berisiko_by_posko(_event_posko_names(event))
    out["jiwa_missing"] = sum(1 for j in jiwa_by.values() if j["missing"] and not j["jiwa"])
    out["jiwa_aspects"] = jiwa_aspect_totals(jiwa_by)
    out["base"] = {
        "jiwa": _jiwa_dilayani_total(event),
        "kebutuhan": _event_count("RN Logistic Need", event) + _shelter_need_count(event),
        "posko_kritis": posko_total if posko_total is not None else _event_count("RN Posko", event),
        "distribusi": flows,
        "distribusi_terhambat": flows,
        "medis": _event_count("RN Medical Case", event),
        "donasi": _event_count("RN Aid Offer", event),
    }
    return out


def activity_trends(event, buckets=14):
    """Records per period since the disaster started (or since its first
    record), split into up to `buckets` equal periods ending today — a
    simulated/older event still shows how activity developed instead of a
    flat "last 14 days" line. `days` = start date of each period."""
    from frappe.utils import add_days, date_diff, getdate, nowdate

    end = getdate(nowdate())
    started = None
    for field in ("started_at", "creation"):
        try:
            started = frappe.db.get_value("RN Disaster Event", event, field)
        except Exception:
            started = None
        if started:
            break
    starts = []
    for doctypes in TREND_SOURCES.values():
        for doctype in doctypes:
            columns = cols(doctype)
            if "disaster_event" in columns:
                date_col = "coalesce(`observed_at`, `creation`)" if "observed_at" in columns else "`creation`"
                first = frappe.db.sql(
                    "select min(date({d})) from `tab{t}` where `disaster_event` = %s".format(d=date_col, t=doctype), (event,))
                if first and first[0][0]:
                    starts.append(getdate(first[0][0]))
    start = getdate(started) if started else (min(starts) if starts else add_days(end, -13))
    if starts:
        start = min([start] + starts)
    span = max(1, date_diff(end, start) + 1)
    n = max(2, min(int(buckets or 14), span))
    step = span / float(n)
    edges = [add_days(start, int(round(i * step))) for i in range(n)] + [add_days(end, 1)]
    out = {"days": [str(d) for d in edges[:-1]], "period_days": round(step, 1)}
    for key, doctypes in TREND_SOURCES.items():
        series = [0] * n
        for doctype in doctypes:
            columns = cols(doctype)
            if "disaster_event" not in columns:
                continue
            date_col = "coalesce(`observed_at`, `creation`)" if "observed_at" in columns else "`creation`"
            rows = frappe.db.sql(
                "select date({d}) as d, count(*) as n from `tab{t}` "
                "where `disaster_event` = %(ev)s and date({d}) between %(start)s and %(end)s "
                "group by date({d})".format(d=date_col, t=doctype),
                {"ev": event, "start": start, "end": end}, as_dict=True,
            )
            for r in rows:
                d = getdate(r.d)
                for i in range(n):
                    if edges[i] <= d < edges[i + 1]:
                        series[i] += int(r.n or 0)
                        break
        out[key] = series
    return out


@frappe.whitelist(
    allow_guest=True
)
@rate_limit(limit=120, seconds=60)
def public_dashboard(
    disaster_event_id
):
    event = canonical_event(
        disaster_event_id
    )

    context = public_context(
        disaster_event_id
    )

    active = (
        public_active_disasters()
        or []
    )

    points = map_points(
        event
    )

    report_rows = reports(
        event
    )

    evidence_rows = event_evidence(
        event
    )

    if isinstance(context, dict):
        context["trends"] = activity_trends(event)
        context["kpi_totals"] = kpi_totals(event, posko_total=len(points))

    return {
        "viewer_mode":
            "public",

        "read_only":
            True,

        "disaster_event_id":
            event,

        "active_disasters":
            active,

        "context":
            context,

        "map": {
            "points":
                points,

            "summary": {
                "total":
                    len(points),

                "critical":
                    sum(
                        p["situation"]
                        == "critical"
                        for p in points
                    ),

                "warning":
                    sum(
                        p["situation"]
                        == "warning"
                        for p in points
                    ),

                "safe":
                    sum(
                        p["situation"]
                        == "safe"
                        for p in points
                    ),
            },
        },

        "community_reports":
            report_rows,

        "evidence":
            evidence_rows,

        "demo_mode":
            event
            == (
                "disaster_events:"
                "event-sim-001"
            ),

        "demo_source":
            (
                "Komunitas Landrover"
                if event
                == (
                    "disaster_events:"
                    "event-sim-001"
                )
                else None
            ),
    }
