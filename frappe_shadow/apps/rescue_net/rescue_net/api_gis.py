"""GIS / National Mapping (blueprint Vol. 10) — geospatial rollup across ALL
disaster events, aggregated by province (and city for drill-down). Point layer
= every posko with coordinates, coloured by its disaster's severity.
"""

import frappe
from frappe.utils import now_datetime, cint

_SEV_RANK = {"critical": 3, "urgent": 2, "high": 2, "normal": 1, "low": 0, "": 0, None: 0}
_UNSET = "Belum Terdata"


def _sev_max(a, b):
    return a if _SEV_RANK.get(a, 0) >= _SEV_RANK.get(b, 0) else b


@frappe.whitelist(allow_guest=True)
def national_situation(active_only=1):
    active_only = str(active_only).lower() in ("1", "true", "yes")

    de = {d.name: d for d in frappe.get_all(
        "RN Disaster Event",
        fields=["name", "title", "severity", "event_status", "location_summary"],
        limit_page_length=500,
    )}
    active_events = {n for n, d in de.items()
                    if (not active_only or (d.event_status or "active") == "active")}

    poskos = frappe.get_all(
        "RN Posko",
        fields=["name", "title", "posko_type", "province_name", "city_name",
                "latitude", "longitude", "verification_status",
                "trusted_verifier_count", "operational_status",
                "rn_beneficiary_count", "disaster_event"],
        limit_page_length=5000,
    )

    # open needs per posko (RN Logistic Need uses `need_status`, not `status`)
    need_by_posko = {}
    _closed = {"fulfilled", "closed", "cancelled", "done", "resolved"}
    for n in frappe.get_all("RN Logistic Need",
                            fields=["posko", "need_status"], limit_page_length=20000):
        if n.posko and str(n.need_status or "").lower() not in _closed:
            need_by_posko[n.posko] = need_by_posko.get(n.posko, 0) + 1

    prov = {}
    points = []
    for p in poskos:
        ev = p.disaster_event
        if active_only and ev and ev not in active_events and ev in de:
            continue
        pv = p.province_name or _UNSET
        d = prov.setdefault(pv, {
            "province": pv, "posko_count": 0, "with_coords": 0,
            "verified": 0, "community_verified": 0, "official_verified": 0,
            "events": set(), "severity": None, "people_served": 0,
            "open_needs": 0, "cities": {},
        })
        d["posko_count"] += 1
        if p.latitude and p.longitude:
            d["with_coords"] += 1
        vs = p.verification_status or "self_reported"
        if vs in ("community_verified",):
            d["community_verified"] += 1
        elif vs in ("official_verified", "verified"):
            d["official_verified"] += 1
        if vs not in ("self_reported", "pending", "needs_correction", "", None):
            d["verified"] += 1
        sev = (de.get(ev, {}).get("severity") if ev else None)
        d["severity"] = _sev_max(d["severity"], sev)
        if ev:
            d["events"].add(ev)
        d["people_served"] += cint(p.rn_beneficiary_count)
        d["open_needs"] += need_by_posko.get(p.name, 0)
        city = p.city_name or _UNSET
        cd = d["cities"].setdefault(city, {"city": city, "posko_count": 0, "verified": 0})
        cd["posko_count"] += 1
        if vs not in ("self_reported", "pending", "needs_correction", "", None):
            cd["verified"] += 1

        if p.latitude and p.longitude:
            points.append({
                "posko": p.name, "title": (p.title or "").replace("[SIMULASI] ", ""),
                "lat": p.latitude, "lng": p.longitude,
                "province": pv, "city": p.city_name,
                "posko_type": p.posko_type,
                "verification_status": vs,
                "trusted_verifier_count": p.trusted_verifier_count or 0,
                "severity": sev or "normal",
                "event": de.get(ev, {}).get("title") if ev else None,
                "event_id": ev,
            })

    provinces = []
    for d in prov.values():
        d["event_count"] = len(d["events"])
        d["events"] = sorted(de.get(e, {}).get("title") or e for e in d["events"])
        d["cities"] = sorted(d["cities"].values(), key=lambda c: -c["posko_count"])
        d["severity"] = d["severity"] or "normal"
        provinces.append(d)
    provinces.sort(key=lambda d: (-_SEV_RANK.get(d["severity"], 0), -d["posko_count"]))

    return {
        "generated_at": now_datetime(),
        "active_only": active_only,
        "totals": {
            "provinces_affected": sum(1 for d in provinces if d["province"] != _UNSET),
            "posko_total": sum(d["posko_count"] for d in provinces),
            "verified_total": sum(d["verified"] for d in provinces),
            "official_verified_total": sum(d["official_verified"] for d in provinces),
            "active_disasters": len(active_events),
            "people_served_total": sum(d["people_served"] for d in provinces),
            "open_needs_total": sum(d["open_needs"] for d in provinces),
        },
        "provinces": provinces,
        "points": points,
        "disasters": [
            {"id": n, "title": d.get("title"), "severity": d.get("severity"),
             "status": d.get("event_status"), "location": d.get("location_summary")}
            for n, d in de.items() if (not active_only or n in active_events)
        ],
    }
