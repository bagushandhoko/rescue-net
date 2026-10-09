"""Early warning intake (Fase 10a, tahap 1 — gempa BMKG saja).

Pulls BMKG open data, stores every quake once (dedupe by identifier), and for
quakes over the threshold creates a DRAFT RN Disaster Event and marks poskos in
radius. A human activates the event (event_status draft -> active); nothing here
notifies anyone or runs AI. A failing source is logged and shown as
"data BMKG tidak terjangkau" — it never breaks anything else.
"""

import json
import math
import re
import urllib.error
import urllib.request
from datetime import timedelta

import frappe
from frappe.utils import flt, get_datetime, now_datetime

SOURCE = "BMKG"
URLS = (
    "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json",
    "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json",
)
ALLOWED_HOST = "data.bmkg.go.id"
MAX_BYTES = 512 * 1024
TIMEOUT = 10

# Initial thresholds (tuned later in settings): M >= 5.0, depth <= 100 km, inside Indonesia.
MIN_MAGNITUDE = 5.0
MAX_DEPTH_KM = 100.0
INDONESIA_BOX = (-12.0, 6.5, 94.0, 142.0)  # lat_min, lat_max, lng_min, lng_max
STATUS_KEY = "rn_early_warning_status"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def _get_json(url):
    if not url.startswith("https://" + ALLOWED_HOST + "/"):
        raise ValueError("host tidak diizinkan")
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "Rescue-Net/1.0 (+early-warning)"})
    with opener.open(req, timeout=TIMEOUT) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("respons terlalu besar")
    return json.loads(raw.decode("utf-8"))


def _num(text):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(text or ""))
    return flt(m.group(0).replace(",", ".")) if m else 0.0


def parse_quakes(payload):
    """BMKG autogempa/gempaterkini JSON -> list of normalised dicts."""
    g = ((payload or {}).get("Infogempa") or {}).get("gempa")
    items = g if isinstance(g, list) else ([g] if isinstance(g, dict) else [])
    out = []
    for q in items:
        try:
            lat, lng = (_num(x) for x in str(q.get("Coordinates", "")).split(","))
            when = get_datetime(str(q.get("DateTime", "")).replace("T", " ")[:19])
        except Exception:
            continue
        mag = _num(q.get("Magnitude"))
        if not mag or not when:
            continue
        out.append({
            "identifier": "bmkg-eq-%s-%s-%s" % (when.strftime("%Y%m%d%H%M%S"), round(lat, 2), round(lng, 2)),
            "when": when, "lat": lat, "lng": lng, "magnitude": mag,
            "depth_km": _num(q.get("Kedalaman")),
            "area": str(q.get("Wilayah") or "")[:140],
            "potential": str(q.get("Potensi") or "")[:140],
            "raw": json.dumps(q, ensure_ascii=False)[:4000],
        })
    return out


def meets_threshold(q):
    a, b, c, d = INDONESIA_BOX
    return (q["magnitude"] >= MIN_MAGNITUDE and q["depth_km"] <= MAX_DEPTH_KM
            and a <= q["lat"] <= b and c <= q["lng"] <= d)


def radius_km(magnitude):
    """100 km at M5 rising linearly to 300 km at M7 (capped)."""
    return max(100.0, min(300.0, 100.0 + (magnitude - 5.0) * 100.0))


def _km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def nearby_poskos(q):
    r = radius_km(q["magnitude"])
    out = []
    for p in frappe.get_all("RN Posko", fields=["name", "title", "latitude", "longitude"],
                            limit_page_length=5000):
        la, lo = flt(p.latitude), flt(p.longitude)
        if not (la or lo):
            continue
        d = _km(q["lat"], q["lng"], la, lo)
        if d <= r:
            out.append({"posko": p.name, "title": p.title, "km": round(d, 1)})
    return sorted(out, key=lambda x: x["km"])[:200]


def _severity(mag):
    return "critical" if mag >= 6.5 else ("high" if mag >= 5.5 else "medium")


def store_quake(q):
    """Idempotent: returns the RN Early Warning name, or None if already stored."""
    if frappe.db.exists("RN Early Warning", {"identifier": q["identifier"]}):
        return None
    hit = meets_threshold(q)
    doc = frappe.get_doc({
        "doctype": "RN Early Warning", "source": SOURCE, "identifier": q["identifier"],
        "kind": "earthquake", "severity": _severity(q["magnitude"]),
        "title": "Gempa M%s — %s" % (q["magnitude"], q["area"]),
        "area_desc": q["area"], "potential": q["potential"],
        "latitude": q["lat"], "longitude": q["lng"], "magnitude": q["magnitude"],
        "depth_km": q["depth_km"], "issued_at": q["when"],
        "expires_at": q["when"] + timedelta(hours=48), "meets_threshold": 1 if hit else 0,
        "status": "new", "raw": q["raw"],
    })
    if hit:
        doc.nearby_poskos = json.dumps(nearby_poskos(q), ensure_ascii=False)
        legacy = q["identifier"]
        if not frappe.db.exists("RN Disaster Event", legacy):
            ev = frappe.get_doc({
                "doctype": "RN Disaster Event", "legacy_id": legacy,
                "title": "[DRAF BMKG] " + doc.title, "event_status": "draft",
                "severity": doc.severity, "location_summary": q["area"], "started_at": q["when"],
            }).insert(ignore_permissions=True)
            doc.draft_event = ev.name
    doc.insert(ignore_permissions=True)
    return doc.name


def process(payloads):
    new = 0
    seen = set()
    for pl in payloads:
        for q in parse_quakes(pl):
            if q["identifier"] in seen:
                continue
            seen.add(q["identifier"])
            if store_quake(q):
                new += 1
    return new


def fetch_and_process():
    """Scheduler entry (every 10 min)."""
    payloads, errors = [], []
    for u in URLS:
        try:
            payloads.append(_get_json(u))
        except (urllib.error.URLError, ValueError, OSError) as e:
            errors.append("%s: %s" % (u.rsplit("/", 1)[-1], str(e)[:80]))
    new = process(payloads) if payloads else 0
    frappe.cache().set_value(STATUS_KEY, {
        "ok": bool(payloads), "checked_at": str(now_datetime()), "errors": errors})
    if errors:
        frappe.log_error("; ".join(errors), "RN early warning fetch")
    frappe.db.commit()
    return {"new": new, "errors": errors}
