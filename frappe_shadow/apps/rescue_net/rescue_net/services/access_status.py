"""Status akses & infrastruktur (Fase 10e): jalan, jembatan, listrik, air, sinyal, bandara, pelabuhan.

Riwayat append-only (RN Access Status); status SAAT INI = laporan terbaru per (jenis, nama tempat). Laporan yang
lewat ``valid_until`` dianggap basi: tampil "tidak diketahui" dengan umur data, tidak pernah dianggap masih berlaku.
Peringatan pengiriman ke wilayah tertutup bersifat nasihat (tidak melarang).
"""

import frappe
from frappe.utils import get_datetime, now_datetime

KINDS = ("road", "bridge", "power", "water", "telecom", "airport", "port")
STATUSES = ("open", "limited", "closed", "unknown")
KIND_LABEL = {"road": "Jalan", "bridge": "Jembatan", "power": "Listrik", "water": "Air", "telecom": "Sinyal",
              "airport": "Bandara", "port": "Pelabuhan"}


def _age_hours(ts):
    return max(0, round((now_datetime() - get_datetime(ts)).total_seconds() / 3600))


def current_statuses(event):
    """Laporan terbaru per (jenis, nama tempat) di event ini, dengan status efektif (basi -> unknown)."""
    rows = frappe.get_all(
        "RN Access Status", filters={"disaster_event": event},
        fields=["name", "kind", "place_name", "status", "segment", "admin_area_id", "latitude", "longitude",
                "verification_status", "observed_at", "valid_until", "note", "creation"],
        order_by="observed_at desc, creation desc", limit_page_length=2000)
    seen, out = set(), []
    for r in rows:
        key = (r.kind, (r.place_name or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        stale = get_datetime(r.valid_until) < now_datetime()
        out.append(dict(r, stale=int(stale), effective_status="unknown" if stale else r.status,
                        age_hours=_age_hours(r.observed_at)))
    return out


def _area_related(a, b):
    """True bila salah satu kode wilayah adalah awalan (induk) dari yang lain; kosong -> tidak berhubungan."""
    if not a or not b:
        return False
    a, b = str(a).split("."), str(b).split(".")
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def access_warnings(destination_posko):
    """Peringatan nasihat bila tujuan berada di wilayah dengan akses 'closed' yang masih berlaku."""
    p = frappe.db.get_value("RN Posko", destination_posko, ["disaster_event", "admin_area_id"], as_dict=True)
    if not p or not p.disaster_event or not p.admin_area_id:
        return []
    return [{"kind": r["kind"], "kind_label": KIND_LABEL.get(r["kind"], r["kind"]), "place_name": r["place_name"],
             "status": "closed", "age_hours": r["age_hours"], "verified": r["verification_status"] == "verified"}
            for r in current_statuses(p.disaster_event)
            if r["effective_status"] == "closed" and _area_related(r["admin_area_id"], p.admin_area_id)]
