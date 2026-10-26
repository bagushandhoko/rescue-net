"""Laporan Situasi (SITREP) otomatis (2026-10-26, rencana pembenahan tahap 3).

A situation report for one disaster and one operational period (default the
last 24 hours), in the order an incident command expects: identity, current
situation, what changed in the period, urgent needs, logistics, services,
alerts/recommendations. The snapshot comes from the guest-safe Control Centre
dashboard (so closed organisations stay summarised); "changed in the period"
is counts only. Same response for every viewer of the public dashboard."""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, cint, flt, now_datetime

from rescue_net.control_centre.common import canonical_event, cols, event_filters, serving_posko_names

# (key, DocType, label, extra filters) counted as "baru dalam periode"
_PERIOD_COUNTS = [
    ("laporan_masyarakat", "RN Community Report", "Laporan masyarakat baru", {}),
    ("kebutuhan_baru", "RN Logistic Need", "Kebutuhan baru dicatat", {}),
    ("kiriman_baru", "RN Distribution Flow", "Kiriman logistik dibuat", {}),
    ("kasus_medis_baru", "RN Medical Case", "Pasien baru di posko medis", {}),
    ("relawan_ditugaskan", "RN Volunteer Assignment", "Penugasan relawan baru", {}),
    ("produksi_dapur", "RN Kitchen Production", "Produksi dapur umum", {}),
    ("orang_hilang", "RN Missing Person Report", "Laporan orang hilang baru", {}),
]


def _scope(doctype, event, poskos):
    c = cols(doctype)
    f = event_filters(c, event)
    if f:
        return f
    if "posko" in c and poskos:
        return {"posko": ["in", poskos]}
    return None


def _count(doctype, scope, since, until, field="creation", extra=None):
    if scope is None:
        return None
    f = dict(scope)
    f[field] = ["between", [since, until]]
    if extra:
        f.update(extra)
    return frappe.db.count(doctype, f)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=60)
def sitrep(disaster_event, hours=24):
    from rescue_net.control_centre.kpi import public_dashboard

    event = canonical_event(disaster_event)
    if not event or not frappe.db.exists("RN Disaster Event", event):
        frappe.throw("Bencana tidak ditemukan.", frappe.DoesNotExistError)
    hours = max(1, min(cint(hours) or 24, 168))
    until = now_datetime()
    since = add_to_date(until, hours=-hours)

    dash = public_dashboard(event) or {}
    ctx = dash.get("context") or {}
    summary = ctx.get("summary") or {}
    kpi = ctx.get("kpi_totals") or {}
    dis = ctx.get("disaster") or {}
    poskos = serving_posko_names(event) or []

    changes = []
    for key, dt, label, extra in _PERIOD_COUNTS:
        if not frappe.db.table_exists(dt):
            continue
        n = _count(dt, _scope(dt, event, poskos), since, until, extra=extra)
        if n is not None:
            changes.append({"key": key, "label": label, "value": n})
    flows = _scope("RN Distribution Flow", event, poskos)
    for key, field, label in (("kiriman_diterima", "received_at", "Kiriman diterima posko tujuan"),
                              ("kiriman_berangkat", "dispatched_at", "Kiriman berangkat")):
        if field in cols("RN Distribution Flow"):
            changes.append({"key": key, "label": label, "value": _count("RN Distribution Flow", flows, since, until, field=field) or 0})

    occ = ctx.get("shelter_occupancies") or []
    shelter = {
        "titik": len(occ),
        "penghuni": int(sum(flt(o.get("current_occupancy")) for o in occ)),
        "kapasitas": int(sum(flt(o.get("capacity_total")) for o in occ)),
        "keluarga": int(sum(flt(o.get("families_count")) for o in occ)),
    }
    med = {}
    for c in ctx.get("medical_cases") or []:
        st = c.get("case_status") or "lainnya"
        med[st] = med.get(st, 0) + 1
    portions = int(sum(flt(k.get("portions")) for k in ctx.get("kitchen_productions") or []))

    quakes = []
    try:
        from rescue_net.api_early_warning import banner
        b = banner() or {}
        quakes = [{"title": w.get("title"), "issued_at": w.get("issued_at"), "besar": bool(w.get("severity"))}
                  for w in (b.get("warnings") or b.get("latest") or [])][:3]
    except Exception:
        quakes = []

    return {
        "judul": "Laporan Situasi (SITREP)",
        "bencana": {"id": event, "title": dis.get("title") or event, "status": dis.get("event_status"),
                    "severity": dis.get("severity"), "mulai": str(dis.get("started_at") or "")[:16]},
        "periode": {"jam": hours, "dari": str(since)[:16], "sampai": str(until)[:16]},
        "dibuat": str(until)[:19],
        "situasi": {
            "jiwa_terdampak": kpi.get("jiwa"),
            "jiwa_per_layanan": kpi.get("jiwa_aspects") or {},
            "orang_hilang": kpi.get("jiwa_missing"),
            "posko_aktif": summary.get("posko_count"),
            "posko_kritis": kpi.get("posko_kritis"),
            "kebutuhan_terbuka": summary.get("open_need_count"),
            "relawan": kpi.get("relawan"),
        },
        "perubahan_periode": changes,
        "kebutuhan_mendesak": [{"judul": r.get("title"), "alasan": r.get("reason"), "prioritas": r.get("priority")}
                               for r in (ctx.get("recommendations") or [])][:8],
        "logistik": {"kiriman_total": kpi.get("distribusi"), "kiriman_terhambat": kpi.get("distribusi_terhambat"),
                     "tawaran_bantuan": summary.get("aid_offer_count")},
        "layanan": {"shelter": shelter, "medis_per_status": med, "porsi_dapur": portions},
        "peringatan": [a.get("message") for a in (ctx.get("alerts") or []) if a.get("message")],
        "gempa_bmkg": quakes,
        "catatan": "Disusun otomatis dari data Rescue-Net. Organisasi tertutup hanya terhitung sebagai ringkasan.",
    }
