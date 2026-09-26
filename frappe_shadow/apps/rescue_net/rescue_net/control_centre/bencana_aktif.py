"""Control Centre — public Bencana Aktif board (per-event regions, jiwa berisiko, critical issues)."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    JIWA_ASPECTS,
    _CLOSED_NEED,
    _CRIT_URGENCY,
    _DRILL_BLOCKED_FLOW,
    _JIWA_NON_POSKO,
    _MEDICAL_CLOSED_CASE,
    _MEDICAL_CRIT_SEVERITY,
    _MEDICAL_CRIT_TRIAGE,
    _OPS_CRITICAL,
    _OPS_WARNING,
    _SEV_STATUS,
    _SIT_RANK,
    _SIT_STATUS,
    _fmt,
    _num,
    _operate_href,
    _sf,
    cols,
    event_filters,
)
from rescue_net.control_centre.critical import (  # noqa: F401
    _derived_critical_reasons,
    _jiwa_berisiko_by_posko,
    _reasons_visible_to_viewer,
    jiwa_aspect_totals,
)
from rescue_net.control_centre.map_evidence import (  # noqa: F401
    reports,
)


def _ba_region_key(posko):
    return (
        (posko.get("city_name") or "").strip()
        or (posko.get("province_name") or "").strip()
        or "Wilayah lain"
    )


def _ba_situation(value):
    v = str(value or "").lower()
    if v in _OPS_CRITICAL:
        return "critical"
    if v in _OPS_WARNING:
        return "warning"
    return "safe"


def _ba_max_dt(a, b):
    if b is None:
        return a
    if a is None:
        return b
    try:
        return a if a >= b else b
    except TypeError:
        return a


def _ba_iso(v):
    if not v:
        return None
    try:
        return frappe.utils.get_datetime(v).isoformat()
    except Exception:
        return str(v)


def _ba_dominant_area(poskos):
    from collections import Counter

    counter = Counter(
        (p.get("city_name") or p.get("province_name") or "").strip()
        for p in poskos
        if (p.get("city_name") or p.get("province_name"))
    )
    return counter.most_common(1)[0][0] if counter else None


def _kebutuhan_href(posko_row, posko_id, event, item_name):
    """Route a critical-need item to its REPORTING posko's own type
    (medis/shelter/dapur/logistik/dll) via _operate_href() — a critical
    need isn't always logistics just because it's stored in RN Logistic
    Need. Only a logistics-type posko gets &penuhi= appended, since only
    posko-logistik.html's own JS reads that deep-link param."""
    row = posko_row or {"name": posko_id}
    href = _operate_href(row, event)
    ptype = str((posko_row or {}).get("posko_type") or "").lower()
    if ptype in ("logistics", "collection_hub"):
        href += "&penuhi=" + (item_name or "")
    return href


def _ba_jiwa_by_posko(categories):
    """"Jiwa Berisiko" drill, one row per posko: the same posko used to show
    up once per category (aspect medis, kasus kritis, kekurangan obat,
    kekurangan nakes, ...) and read as duplicates. Here each posko appears
    once, with its jiwa count (aspect categories only — indicator counts are
    cases/needs, not people) and every problem as a line under it."""
    rows = {}
    for cat in categories:
        if cat["key"] in _JIWA_NON_POSKO:
            continue
        is_jiwa = cat["key"].startswith("jiwa_")
        label = cat["label"].split(" — ")[0]
        for it in cat.get("items") or []:
            key = it.get("href") or it.get("title")
            row = rows.setdefault(key, {
                "title": it.get("title"), "region": it.get("region"), "href": it.get("href"),
                "jiwa": 0, "problems": [],
            })
            if is_jiwa:
                row["jiwa"] += int(it.get("count") or 0)
            row["problems"].append({"key": cat["key"], "label": label, "detail": it.get("detail"),
                                    "count": it.get("count"), "is_jiwa": is_jiwa})
    out = list(rows.values())
    out.sort(key=lambda r: (-r["jiwa"], -len(r["problems"]), r["title"] or ""))
    return out


def _ba_jiwa_categories(event_id, short_ev, posko_by_name, posko_title, posko_region):
    """"Jiwa Berisiko" drill, level 1 — owner: a raw beneficiary count
    with nowhere to click into "posko medis mana yang bermasalah" isn't
    good enough. WHAT is critical, grouped from real records, so level 2
    (frontend) can drill straight to the specific posko/laporan with the
    problem: kasus medis kritis, kekurangan obat/alkes, kekurangan
    tenaga medis, shelter kondisi kritis, laporan korban masyarakat."""

    def _norm_posko(raw):
        # Some legacy rows store `posko` with a stray pre-cutover
        # `posko_nodes:` prefix that doesn't match RN Posko's real
        # docname — but for some events (e.g. Aceh/Luwu-era imports) the
        # real docname itself legitimately starts with `posko_nodes:`.
        # Try the raw value first (covers the real-docname case), only
        # stripping the prefix as a fallback for the stray-artifact case.
        raw = str(raw or "")
        return raw if raw in posko_by_name else raw.replace("posko_nodes:", "")

    def _group_by_posko(rows, detail_fn):
        buckets = {}
        for r in rows:
            posko = _norm_posko(r.get("posko")) or None
            # Drop a dangling reference to a posko that no longer exists
            # for this event — a dead-end link with a raw ID as its title
            # is worse than just not showing that one row.
            if not posko or posko not in posko_by_name:
                continue
            buckets.setdefault(posko, []).append(r)
        items = [
            {
                "title": posko_title.get(posko) or posko,
                "region": posko_region.get(posko) or "Lintas wilayah",
                "detail": detail_fn(rows),
                "count": len(rows),
                "href": _operate_href(posko_by_name.get(posko, {"name": posko}), short_ev),
            }
            for posko, rows in buckets.items()
        ]
        items.sort(key=lambda it: -it["count"])
        return items

    categories = []

    # 1) Kasus medis kritis — triase merah/hitam atau severity berat/kritis,
    # masih ditangani (belum discharged/closed/meninggal).
    cases = frappe.get_all(
        "RN Medical Case",
        filters=event_filters(cols("RN Medical Case"), event_id),
        fields=_sf("RN Medical Case", ["name", "posko", "severity", "triage_status", "case_status"]),
        limit_page_length=500,
    )
    crit_cases = [
        c for c in cases
        if (
            str(c.get("severity") or "").lower() in _MEDICAL_CRIT_SEVERITY
            or str(c.get("triage_status") or "").lower() in _MEDICAL_CRIT_TRIAGE
        )
        and str(c.get("case_status") or "active").lower() not in _MEDICAL_CLOSED_CASE
    ]
    categories.append({
        "key": "medis_kritis",
        "label": "Kasus Medis Kritis",
        "count": len(crit_cases),
        "items": _group_by_posko(
            crit_cases,
            lambda rows: "%d kasus triase merah/hitam atau severity berat/kritis" % len(rows),
        ),
    })

    # 2) Kekurangan obat/alkes — kebutuhan logistik kritis yang dilaporkan
    # posko bertipe medical (subset dari kebutuhan_items di atas).
    needs = frappe.get_all(
        "RN Logistic Need",
        filters=event_filters(cols("RN Logistic Need"), event_id),
        fields=_sf("RN Logistic Need", ["name", "item_name", "urgency", "need_status", "posko"]),
        limit_page_length=500,
    )
    med_needs = [
        n for n in needs
        if str(n.get("urgency") or "").lower() in _CRIT_URGENCY
        and str(n.get("need_status") or "open").lower() not in _CLOSED_NEED
        and str((posko_by_name.get(n.get("posko")) or {}).get("posko_type") or "").lower() == "medical"
    ]
    categories.append({
        "key": "kekurangan_obat",
        "label": "Kekurangan Obat & Alat Kesehatan",
        "count": len(med_needs),
        "items": _group_by_posko(
            med_needs,
            lambda rows: ", ".join(sorted({r.get("item_name") or "-" for r in rows})[:4]),
        ),
    })

    # 3) Kekurangan tenaga medis — permintaan relawan medis prioritas
    # urgent/kritis yang belum terisi (planned/cancelled = belum jalan).
    assigns = frappe.get_all(
        "RN Volunteer Assignment",
        filters=event_filters(cols("RN Volunteer Assignment"), event_id),
        fields=_sf("RN Volunteer Assignment", ["name", "posko", "assignment_type", "priority", "assignment_status"]),
        limit_page_length=500,
    )
    nakes_gaps = [
        a for a in assigns
        if str(a.get("assignment_type") or "").lower() == "medical"
        and str(a.get("priority") or "").lower() in ("urgent", "critical")
        and str(a.get("assignment_status") or "planned").lower() in ("planned", "cancelled")
    ]
    categories.append({
        "key": "kekurangan_nakes",
        "label": "Kekurangan Tenaga Medis",
        "count": len(nakes_gaps),
        "items": _group_by_posko(
            nakes_gaps,
            lambda rows: "%d permintaan relawan medis belum terisi" % len(rows),
        ),
    })

    # 4) Shelter kondisi kritis — melebihi kapasitas, atau kebutuhan
    # shelter berstatus kritis & masih terbuka.
    occs = frappe.get_all(
        "RN Shelter Occupancy",
        filters=event_filters(cols("RN Shelter Occupancy"), event_id),
        fields=_sf("RN Shelter Occupancy", ["name", "posko", "capacity_total", "current_occupancy"]),
        limit_page_length=500,
    )
    over_capacity = {
        _norm_posko(o.get("posko")): o for o in occs
        if o.get("posko")
        and _num(o.get("capacity_total")) > 0
        and _num(o.get("current_occupancy")) > _num(o.get("capacity_total"))
    }
    # RN Shelter Need has NO disaster_event column at all (checked the
    # doctype meta) — event_filters() would silently return {} and every
    # shelter need across EVERY event leaked into this one's drill. Scope
    # by posko membership in this event's own poskos instead.
    shelter_needs_all = frappe.get_all(
        "RN Shelter Need",
        fields=_sf("RN Shelter Need", ["name", "posko", "item_name", "priority", "need_status"]),
        limit_page_length=2000,
    )
    shelter_needs = [
        n for n in shelter_needs_all
        if _norm_posko(n.get("posko")) in posko_by_name
    ]
    crit_shelter_needs = [
        n for n in shelter_needs
        if str(n.get("priority") or "").lower() == "critical"
        and str(n.get("need_status") or "open").lower() == "open"
        and n.get("posko")
    ]
    # Only poskos that still resolve to a real RN Posko doc for this event —
    # a dangling `posko` reference (renamed/deleted record; seen live for
    # one legacy shelter-need row) would otherwise show a dead-end link
    # with the raw internal ID as its title instead of a real posko name.
    shelter_posko_ids = (set(over_capacity) | {
        _norm_posko(n["posko"]) for n in crit_shelter_needs
    }) & set(posko_by_name)
    shelter_items = []
    for posko in shelter_posko_ids:
        occ = over_capacity.get(posko)
        needs_hit = [
            n for n in crit_shelter_needs
            if _norm_posko(n.get("posko")) == posko
        ]
        details = []
        if occ:
            details.append(
                "Kapasitas %d, terisi %d (penuh)"
                % (int(_num(occ.get("capacity_total"))), int(_num(occ.get("current_occupancy"))))
            )
        if needs_hit:
            details.append(
                "%d kebutuhan kritis (%s)"
                % (len(needs_hit), ", ".join(sorted({n.get("item_name") or "-" for n in needs_hit})[:3]))
            )
        shelter_items.append({
            "title": posko_title.get(posko) or posko,
            "region": posko_region.get(posko) or "Lintas wilayah",
            "detail": " · ".join(details),
            "count": (1 if occ else 0) + len(needs_hit),
            "href": _operate_href(posko_by_name.get(posko, {"name": posko}), short_ev),
        })
    shelter_items.sort(key=lambda it: -it["count"])
    categories.append({
        "key": "shelter_kritis",
        "label": "Shelter Kondisi Kritis",
        "count": len(shelter_items),
        "items": shelter_items,
    })

    # 5) Laporan korban dari masyarakat — laporan warga yang mencatat
    # jiwa terdampak, terbaru dulu.
    reports = frappe.get_all(
        "RN Community Report",
        filters=event_filters(cols("RN Community Report"), event_id),
        fields=_sf("RN Community Report", [
            "name", "title", "report_type", "affected_people_count",
            "reporter_name", "city_name", "district_name", "village_name",
        ]),
        order_by="creation desc",
        limit_page_length=200,
    )
    victim_reports = [r for r in reports if _num(r.get("affected_people_count")) > 0]
    categories.append({
        "key": "laporan_korban",
        "label": "Laporan Korban dari Masyarakat",
        "count": len(victim_reports),
        "items": [
            {
                "title": r.get("title") or r.get("report_type") or "Laporan Masyarakat",
                "region": r.get("village_name") or r.get("district_name") or r.get("city_name") or "-",
                "detail": "%d jiwa terdampak · pelapor: %s" % (
                    int(_num(r.get("affected_people_count"))), r.get("reporter_name") or "warga",
                ),
                "count": int(_num(r.get("affected_people_count"))),
                "href": "laporan-masyarakat.html?report=" + str(r["name"]) + "&event=" + short_ev,
            }
            for r in victim_reports[:30]
        ],
    })

    return categories


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def active_disasters_board(limit=60):
    """Public 'Bencana Aktif' dashboard feed: every active RN Disaster Event
    with a per-region (kabupaten/kota) breakdown, rolled-up KPI totals, and a
    short 'isu kritis teratas' list per event. Read-only, guest-safe."""
    events = frappe.get_all(
        "RN Disaster Event",
        filters={"event_status": "active"},
        fields=_sf("RN Disaster Event", [
            "name", "legacy_id", "title", "severity", "event_status",
            "started_at", "location_summary", "modified",
        ]),
        order_by="started_at desc",
        limit_page_length=int(limit),
    )

    posko_cols = cols("RN Posko")
    need_cols = cols("RN Logistic Need")
    flow_cols = cols("RN Distribution Flow")

    out_events = []
    tot_jiwa = tot_krit = tot_hambat = tot_pkritis = 0

    for ev in events:
        event_id = ev["name"]

        poskos = frappe.get_all(
            "RN Posko",
            filters=event_filters(posko_cols, event_id),
            fields=_sf("RN Posko", [
                "name", "title", "city_name", "province_name", "address",
                "posko_type", "operational_status", "organization",
                "rn_beneficiary_count", "rn_fn_shelter", "modified",
            ]),
            limit_page_length=500,
        )
        needs = frappe.get_all(
            "RN Logistic Need",
            filters=event_filters(need_cols, event_id),
            fields=_sf("RN Logistic Need", [
                "name", "item_name", "urgency", "need_status", "posko", "modified",
            ]),
            limit_page_length=500,
        )
        flows = frappe.get_all(
            "RN Distribution Flow",
            filters=event_filters(flow_cols, event_id),
            fields=_sf("RN Distribution Flow", [
                "name", "item_name", "flow_status", "destination_posko", "modified",
            ]),
            limit_page_length=500,
        )

        posko_region = {p["name"]: _ba_region_key(p) for p in poskos}
        posko_title = {p["name"]: (p.get("title") or p["name"]) for p in poskos}
        posko_by_name = {p["name"]: p for p in poskos}

        derived = _derived_critical_reasons([p["name"] for p in poskos])
        # Situation uses every derived signal; the *reasons* are posko-level
        # detail and only go to viewers allowed that posko's full share mode.
        reasons_ok = _reasons_visible_to_viewer(list(derived))

        def _ba_situation_of(p):
            sit = _ba_situation(p.get("operational_status"))
            if p["name"] in derived:
                sit = "critical"
            return sit

        crit_needs = [
            n for n in needs
            if str(n.get("urgency") or "").lower() in _CRIT_URGENCY
            and str(n.get("need_status") or "open").lower() not in _CLOSED_NEED
        ]
        blocked_flows = [
            f for f in flows
            if str(f.get("flow_status") or "").lower() in _DRILL_BLOCKED_FLOW
        ]

        short_ev = str(ev["name"]).replace("disaster_events:", "")

        kebutuhan_items = [
            {
                "item": n.get("item_name") or "Kebutuhan logistik",
                "urgency": str(n.get("urgency") or "").lower(),
                "posko": n.get("posko"),
                "posko_title": posko_title.get(n.get("posko")) or n.get("posko") or "-",
                "region": posko_region.get(n.get("posko")) or "Lintas wilayah",
                # A "kebutuhan kritis" isn't always a logistics need from a
                # logistics posko — e.g. KH-POSKO-ISPA is posko_type
                # "medical" but its critical needs (masker, oksigen) used to
                # hardcode a posko-logistik.html link anyway. Route by the
                # REPORTING posko's actual type instead, via _kebutuhan_href().
                "href": (
                    _kebutuhan_href(posko_by_name.get(n.get("posko")), n.get("posko"), short_ev, n.get("item_name"))
                    if n.get("posko") else ("war-room.html?event=" + short_ev)
                ),
            }
            for n in sorted(
                crit_needs,
                key=lambda n: 0
                if str(n.get("urgency") or "").lower() == "critical" else 1,
            )
        ]
        distribusi_items = [
            {
                "item": f.get("item_name") or "Distribusi",
                "status": str(f.get("flow_status") or "").lower(),
                "posko": f.get("destination_posko"),
                "posko_title": posko_title.get(f.get("destination_posko"))
                or f.get("destination_posko") or "-",
                "region": posko_region.get(f.get("destination_posko")) or "Lintas wilayah",
                # Deep-link to the destination posko's own board (where the
                # backlog actually is) instead of the generic module page —
                # same "route by what the item actually points to" rule
                # kebutuhan_items already follows below.
                "href": (
                    "posko-distribusi.html?id="
                    + str(f.get("destination_posko") or "").replace("posko_nodes:", "")
                    + "&event=" + short_ev
                ) if f.get("destination_posko") else ("management-distribusi.html?event=" + short_ev),
            }
            for f in blocked_flows
        ]
        posko_kritis_items = [
            {
                "posko": p["name"],
                "posko_title": p.get("title") or p["name"],
                "region": posko_region[p["name"]],
                "type": p.get("posko_type"),
                "reasons": derived.get(p["name"], []) if p["name"] in reasons_ok else [],
                "reasons_hidden": p["name"] in derived and p["name"] not in reasons_ok,
                "href": (
                    "posko-detail.html?id="
                    + str(p["name"]).replace("posko_nodes:", "")
                    + "&event=" + short_ev
                ),
            }
            for p in poskos
            if _ba_situation_of(p) == "critical"
        ]
        # Jiwa Berisiko drill previously showed only a region rollup table
        # with one blanket "Buka Control Centre" link — no way to reach the
        # actual posko carrying the people (medis/shelter/dapur/etc). One
        # row per posko with beneficiaries, routed by type via the same
        # _operate_href() every other "go operate this posko" link in this
        # module already uses (posko-medis-detail / shelter-detail /
        # dapur-umum / posko-logistik / posko-distribusi / posko-detail).
        # People at risk (not people served): same per-posko model as the
        # Control Centre KPI / "jiwa" drill — _jiwa_berisiko_by_posko.
        jiwa_by = _jiwa_berisiko_by_posko([p["name"] for p in poskos])

        def _jiwa_item(pname, detail):
            return {
                "title": posko_title.get(pname) or pname,
                "region": posko_region.get(pname) or "Lintas wilayah",
                "detail": detail,
                "count": jiwa_by[pname]["jiwa"],
                "href": _operate_href(posko_by_name.get(pname, {"name": pname}), short_ev),
            }

        no_data = [p for p, j in jiwa_by.items() if j["missing"] and not j["jiwa"]]
        aspect_why = {
            "logistik": "jiwa yang kebutuhan mendesaknya belum dikirim",
            "shelter": "penghuni shelter yang melebihi kapasitas",
            "medis": "pasien yang masih ditangani",
        }
        jiwa_categories = []
        for key, label in JIWA_ASPECTS:
            members = sorted((p for p, j in jiwa_by.items() if j["aspects"].get(key)),
                             key=lambda p: -jiwa_by[p]["aspects"][key])
            items = []
            for p in members:
                it = _jiwa_item(p, "%s jiwa (%s) · %s" % (
                    _fmt(jiwa_by[p]["aspects"][key]), aspect_why[key], "; ".join(jiwa_by[p]["reasons"])))
                it["count"] = jiwa_by[p]["aspects"][key]
                items.append(it)
            jiwa_categories.append({
                "key": "jiwa_" + key,
                "label": "Aspek %s — %s jiwa" % (label, _fmt(sum(i["count"] for i in items))),
                "count": sum(i["count"] for i in items),
                "items": items,
            })
        jiwa_categories.append({
            "key": "jiwa_belum_lapor",
            "label": "Posko Belum Melaporkan Jumlah Jiwa",
            "count": len(no_data),
            "items": [_jiwa_item(p, "; ".join(jiwa_by[p]["reasons"])) for p in no_data],
        })
        jiwa_categories = jiwa_categories + _ba_jiwa_categories(
            event_id, short_ev, posko_by_name, posko_title, posko_region
        )
        jiwa_poskos = _ba_jiwa_by_posko(jiwa_categories)
        jiwa = sum(j["jiwa"] for j in jiwa_by.values())
        jiwa_missing = sum(1 for j in jiwa_by.values() if j["missing"] and not j["jiwa"])
        pengungsi = sum(
            int(_num(p.get("rn_beneficiary_count")))
            for p in poskos
            if p.get("rn_fn_shelter")
            or str(p.get("posko_type") or "").lower() == "shelter"
        )

        regions = {}
        for p in poskos:
            key = posko_region[p["name"]]
            row = regions.setdefault(key, {
                "name": key, "jiwa_berisiko": 0, "kebutuhan_kritis": 0,
                "distribusi": 0, "situation": "safe", "posko_count": 0,
                "last_updated": None,
            })
            row["posko_count"] += 1
            row["jiwa_berisiko"] += (jiwa_by.get(p["name"]) or {}).get("jiwa", 0)
            sit = _ba_situation_of(p)
            if _SIT_RANK[sit] > _SIT_RANK[row["situation"]]:
                row["situation"] = sit
            row["last_updated"] = _ba_max_dt(row["last_updated"], p.get("modified"))

        for n in crit_needs:
            key = posko_region.get(n.get("posko"))
            if key in regions:
                regions[key]["kebutuhan_kritis"] += 1
                regions[key]["last_updated"] = _ba_max_dt(
                    regions[key]["last_updated"], n.get("modified"))
        for f in flows:
            key = posko_region.get(f.get("destination_posko"))
            if key in regions:
                regions[key]["distribusi"] += 1

        region_rows = sorted(
            regions.values(),
            key=lambda r: (-_SIT_RANK[r["situation"]], -r["jiwa_berisiko"]),
        )
        for row in region_rows:
            row["status_label"] = _SIT_STATUS[row["situation"]]
            row["last_updated"] = _ba_iso(row["last_updated"])

        isu = []
        for it in kebutuhan_items[:6]:
            isu.append({
                "kind": "kebutuhan",
                "title": it["item"],
                "detail": it["region"],
                "level": "Sangat Tinggi" if it["urgency"] == "critical" else "Tinggi",
                "href": it["href"],
            })
        for it in posko_kritis_items:
            isu.append({
                "kind": "posko",
                "title": it["posko_title"] + " berstatus kritis",
                "detail": it["region"] + (" · " + "; ".join(it["reasons"]) if it.get("reasons") else ""),
                "level": "Sangat Tinggi",
                "href": it["href"],
            })
        isu = isu[:6]

        last_updated = ev.get("modified")
        for coll in (poskos, needs, flows):
            for row in coll:
                last_updated = _ba_max_dt(last_updated, row.get("modified"))

        sev = str(ev.get("severity") or "normal").lower()
        out_events.append({
            "id": ev.get("legacy_id") or ev["name"],
            "event_id": ev["name"],
            "name": ev.get("title") or ev["name"],
            "location": ev.get("location_summary")
            or _ba_dominant_area(poskos) or "Indonesia",
            "severity": sev,
            "status_label": _SEV_STATUS.get(sev, "Waspada"),
            "started_at": _ba_iso(ev.get("started_at")),
            "last_updated": _ba_iso(last_updated),
            "jiwa_berisiko": jiwa,
            "jiwa_missing_poskos": jiwa_missing,
            "jiwa_aspects": jiwa_aspect_totals(jiwa_by),
            "pengungsi": pengungsi,
            "kebutuhan_kritis": len(crit_needs),
            "distribusi_terhambat": len(blocked_flows),
            "distribusi_total": len(flows),
            "posko_count": len(poskos),
            "posko_kritis": len(posko_kritis_items),
            "regions": region_rows,
            "isu_kritis": isu,
            "kebutuhan_items": kebutuhan_items,
            "distribusi_items": distribusi_items,
            "posko_kritis_items": posko_kritis_items,
            "jiwa_categories": jiwa_categories,
            "jiwa_poskos": jiwa_poskos,
        })

        tot_jiwa += jiwa
        tot_krit += len(crit_needs)
        tot_hambat += len(blocked_flows)
        tot_pkritis += len(posko_kritis_items)

    return {
        "generated_at": _ba_iso(frappe.utils.now_datetime()),
        "totals": {
            "bencana_aktif": len(out_events),
            "jiwa_berisiko": tot_jiwa,
            "kebutuhan_kritis": tot_krit,
            "distribusi_terhambat": tot_hambat,
            "posko_kritis": tot_pkritis,
        },
        "events": out_events,
    }
