"""Early warning intake (Fase 10a, tahap 1 — gempa BMKG saja).

Pulls BMKG open data, stores every quake once (dedupe by identifier), and for
quakes over the threshold creates a DRAFT RN Disaster Event and marks poskos in
radius. A human activates the event (event_status draft -> active); nothing here
notifies anyone or runs AI. A failing source is logged and shown as
"data BMKG tidak terjangkau" — it never breaks anything else.
"""

import json
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
    "https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json",
)
ALLOWED_HOST = "data.bmkg.go.id"
# Peringatan dini cuaca (nowcast) BMKG, RSS publik; owner 23 Nov: "yang bisa di konek langsung kerjakan"
NOWCAST_URL = "https://www.bmkg.go.id/alerts/nowcast/id"
NOWCAST_HOST = "www.bmkg.go.id"
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


def _get_raw(url, host=ALLOWED_HOST):
    if not url.startswith("https://" + host + "/"):
        raise ValueError("host tidak diizinkan")
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "Rescue-Net/1.0 (+early-warning)"})
    with opener.open(req, timeout=TIMEOUT) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("respons terlalu besar")
    return raw


def _get_json(url):
    return json.loads(_get_raw(url).decode("utf-8"))


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
            "potential": str(q.get("Potensi") or ("Dirasakan: " + str(q.get("Dirasakan")) if q.get("Dirasakan") else ""))[:140],
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


def nearby_poskos(q):
    """Posko dalam radius gempa. Disaring di database dengan kotak lokasi (services.geo), bukan lagi memindai
    semua posko (dulu maksimal 5.000 baris: posko ke-5.001 dst. diam-diam terlewat)."""
    from rescue_net.services import geo

    rows = geo.near("RN Posko", q["lat"], q["lng"], radius_km(q["magnitude"]), fields=["title"], limit=200)
    return [{"posko": p.name, "title": p.title, "km": round(p.km, 1)} for p in rows]


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
        # owner 2026-11-02: a BMKG notice is an ANNOUNCEMENT, not a disaster — no draft event is created.
        # A super admin turns it into a Rescue-Net disaster only when it is declared one (Kelola Bencana →
        # Pengumuman BMKG → "Jadikan bencana", api_disaster_admin.promote_warning).
        try:
            from rescue_net.services.event_merge import notify_admins

            notify_admins("Pengumuman BMKG: %s — bukan bencana; jadikan bencana di Kelola Bencana bila sudah dinyatakan" % doc.title)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bmkg notice notify")
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


_TZ = {"WIB": 7, "WITA": 8, "WIT": 9}
_BULAN = {b: i + 1 for i, b in enumerate(
    "januari februari maret april mei juni juli agustus september oktober november desember".split())}


def _until_utc(text):
    """'... hingga 23 November 2026, 22:00 WIB' -> naive UTC datetime, or None."""
    m = re.search(r"hingga\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4}),?\s+(\d{1,2})[:.](\d{2})\s*(WIB|WITA|WIT)", text or "")
    if not m or m.group(2).lower() not in _BULAN:
        return None
    from datetime import datetime
    local = datetime(int(m.group(3)), _BULAN[m.group(2).lower()], int(m.group(1)), int(m.group(4)), int(m.group(5)))
    return local - timedelta(hours=_TZ[m.group(6)])


def parse_nowcast(raw):
    """BMKG nowcast RSS (bytes) -> list of weather warnings (UTC times)."""
    from email.utils import parsedate_to_datetime
    import xml.etree.ElementTree as ET

    if b"<!ENTITY" in raw or b"<!DOCTYPE" in raw:
        raise ValueError("XML tidak diizinkan")
    out = []
    for it in ET.fromstring(raw).iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = re.sub(r"\s+", " ", it.findtext("description") or "").strip()
        guid = (it.findtext("guid") or it.findtext("link") or "").strip()
        try:
            issued = parsedate_to_datetime(it.findtext("pubDate") or "")
            issued = (issued - issued.utcoffset()).replace(tzinfo=None)
        except Exception:
            continue
        if not title or not guid:
            continue
        area = title.split(" di ", 1)[1] if " di " in title else ""
        out.append({
            "identifier": "bmkg-cuaca-" + re.sub(r"[^0-9A-Za-z.]", "", guid)[:100],
            "title": title[:140], "area": area[:140],
            "potential": desc.split(". ")[0][:140],
            "when": issued, "until": _until_utc(desc) or issued + timedelta(hours=3),
            "link": (it.findtext("link") or "")[:300],
            "raw": json.dumps({"title": title, "description": desc[:3000], "link": it.findtext("link")}, ensure_ascii=False)[:4000],
        })
    return out


def store_weather(w):
    """Idempotent. Weather warnings are informational only: no draft event, no notification."""
    if frappe.db.exists("RN Early Warning", {"identifier": w["identifier"]}):
        return None
    doc = frappe.get_doc({
        "doctype": "RN Early Warning", "source": SOURCE, "identifier": w["identifier"],
        "kind": "weather", "severity": "medium", "title": w["title"], "area_desc": w["area"],
        "potential": w["potential"], "issued_at": w["when"], "expires_at": w["until"],
        "meets_threshold": 0, "status": "new", "raw": w["raw"],
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def fetch_weather():
    try:
        items = parse_nowcast(_get_raw(NOWCAST_URL, NOWCAST_HOST))
    except (urllib.error.URLError, ValueError, OSError, SyntaxError) as e:
        return 0, ["nowcast: %s" % str(e)[:80]]
    return sum(1 for w in items if store_weather(w)), []


def fetch_and_process():
    """Scheduler entry (every 10 min)."""
    payloads, errors = [], []
    for u in URLS:
        try:
            payloads.append(_get_json(u))
        except (urllib.error.URLError, ValueError, OSError) as e:
            errors.append("%s: %s" % (u.rsplit("/", 1)[-1], str(e)[:80]))
    new = process(payloads) if payloads else 0
    new_weather, werr = fetch_weather()
    errors += werr
    frappe.cache().set_value(STATUS_KEY, {
        "ok": bool(payloads), "weather_ok": not werr, "checked_at": str(now_datetime()), "errors": errors})
    if errors:
        frappe.log_error("; ".join(errors), "RN early warning fetch")
    frappe.db.commit()
    return {"new": new, "new_weather": new_weather, "errors": errors}
