"""Pick the posko a citizen report belongs to.

Deterministic and explainable (KPI-consistency rule: the conclusion is a
stored per-report value with its reason, never only an AI remark):

    score = area match + distance + function fit

* area: same village 40 · district 30 · city 20 · province 5
  (admin_area_id prefix or area names)
* distance (both have coordinates): up to 40, falling to 0 at 50 km;
  +10 inside the posko's coverage radius
* function: +15 when the posko's type/functions fit the report type

Only open poskos of the report's disaster event are candidates (any active
event's poskos when the report names no event). Below MIN_SCORE the report
stays unrouted for Control Centre triage.
"""

import math
import re

import frappe

MIN_SCORE = 20
FAR_KM = 50.0
INACTIVE = {"offline", "inactive", "closed", "non_aktif", "nonaktif", "ditutup"}

# report_type -> posko types / function flags that serve it
FUNCTION_FIT = {
    "medical_case": ({"medical", "medis", "kesehatan"}, ("rn_fn_medical",)),
    "shelter_need": ({"shelter", "pengungsian"}, ("rn_fn_shelter",)),
    "affected_need_help": ({"logistics", "logistik", "general", "umum"}, ("rn_fn_logistics", "rn_fn_kitchen")),
    "location_needs_help": ({"logistics", "logistik", "general", "umum"}, ("rn_fn_logistics",)),
    "water_shortage": ({"logistics", "logistik", "general", "umum", "wash"}, ("rn_fn_logistics",)),
    "blocked_access": ({"logistics", "logistik", "transport", "alat_kerja", "general"}, ("rn_fn_logistics",)),
    "missing_or_found": ({"search_found", "sar", "general", "umum"}, ()),
}


def _km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _same(a, b):
    return bool(a and b and a.strip().lower() == b.strip().lower())


def _candidates(report):
    fields = ["name", "title", "disaster_event", "posko_type", "operational_status", "latitude", "longitude",
              "coverage_radius_meters", "admin_area_id", "province_name", "city_name", "district_name",
              "village_name"]
    meta = frappe.get_meta("RN Posko")
    flags = [f for f in ("rn_fn_medical", "rn_fn_shelter", "rn_fn_logistics", "rn_fn_kitchen") if meta.has_field(f)]
    filters = {}
    if report.get("disaster_event"):
        filters["disaster_event"] = report.get("disaster_event")
    else:
        active = frappe.get_all("RN Disaster Event", filters={"event_status": "active"}, pluck="name")
        if not active:
            return []
        filters["disaster_event"] = ["in", active]
    rows = frappe.get_all("RN Posko", filters=filters, fields=fields + flags, limit_page_length=500)
    return [r for r in rows if (r.operational_status or "").strip().lower() not in INACTIVE]


def score(report, posko):
    """(points, [reasons]) for one posko."""
    pts, why = 0.0, []

    area_r, area_p = (report.get("admin_area_id") or ""), (posko.get("admin_area_id") or "")
    if _same(report.get("village_name"), posko.get("village_name")) or (area_r and area_r == area_p and len(area_r) >= 10):
        pts += 40
        why.append(f"desa sama ({posko.get('village_name') or report.get('village_name')})")
    elif _same(report.get("district_name"), posko.get("district_name")):
        pts += 30
        why.append(f"kecamatan sama ({posko.get('district_name')})")
    elif _same(report.get("city_name"), posko.get("city_name")):
        pts += 20
        why.append(f"kabupaten/kota sama ({posko.get('city_name')})")
    elif _same(report.get("province_name"), posko.get("province_name")):
        pts += 5
        why.append("provinsi sama")
    else:
        # no admin area picked (e.g. a narrative): the place names the
        # reporter wrote count a little less than a picked area
        text = " ".join(str(report.get(f) or "") for f in ("location_text", "description", "title")).lower()
        for field, points, label in (("village_name", 35, "desa"), ("district_name", 25, "kecamatan"),
                                     ("city_name", 15, "kabupaten/kota")):
            name = (posko.get(field) or "").strip().lower()
            if len(name) >= 3 and re.search(r"\b" + re.escape(name) + r"\b", text):
                pts += points
                why.append(f"lokasi laporan menyebut {label} {posko.get(field)}")
                break

    if report.get("latitude") is not None and report.get("longitude") is not None \
            and posko.get("latitude") and posko.get("longitude"):
        d = _km(float(report["latitude"]), float(report["longitude"]), float(posko.latitude), float(posko.longitude))
        pts += max(0.0, 40.0 * (1 - d / FAR_KM))
        why.append(f"{d:.1f} km")
        radius = float(posko.get("coverage_radius_meters") or 0) / 1000
        if radius and d <= radius:
            pts += 10
            why.append("dalam radius layanan")

    types, flags = FUNCTION_FIT.get(report.get("report_type") or "", (set(), ()))
    if (posko.get("posko_type") or "").strip().lower() in types or any(posko.get(f) for f in flags):
        pts += 15
        why.append(f"fungsi posko cocok ({posko.get('posko_type') or 'fungsi'})")

    return round(pts, 1), why


def best_posko(report):
    """(posko_name, score, reason) or (None, 0, reason) — `report` is a dict
    or document with the report's area/coordinate/type fields."""
    ranked = []
    for p in _candidates(report):
        pts, why = score(report, p)
        ranked.append((pts, p, why))
    if not ranked:
        return None, 0, "Belum ada posko aktif pada kejadian ini."
    ranked.sort(key=lambda x: (-x[0], x[1].name))
    pts, p, why = ranked[0]
    if pts < MIN_SCORE:
        return None, pts, "Tidak ada posko yang cukup dekat/relevan — menunggu triase Control Centre."
    return p.name, pts, f"{p.title}: " + ", ".join(why)
