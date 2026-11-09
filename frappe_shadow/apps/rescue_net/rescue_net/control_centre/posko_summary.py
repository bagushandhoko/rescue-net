"""Ringkasan semua posko satu jenis dalam satu bencana (owner 2026-11-09 malam).

"Setelah pilih bencana, jika pilih posko yang tampil awal summary semua posko (informasi cukup lengkap
kondisi posko dalam 1 baris), karena satu jenis posko bisa banyak; publik pilih posko tertentu baru tampil
seperti sekarang (satu posko). Terapkan ke semua jenis posko."

Angka per baris diambil dari fungsi papan yang SAMA dengan halaman detail posko (logistik_board,
posko_distribusi_board, kitchen_board, shelter_board, api_medical.dashboard), jadi ringkasan selalu
cocok dengan halaman posko dan aturan visibilitas (organisasi tertutup = ringkasan) ikut terbawa.
"""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.control_centre.common import _num, _poskos_viewer_context, canonical_event
from rescue_net.control_centre.map_evidence import map_points

KINDS = ("logistik", "distribusi", "medis", "shelter", "dapur")
_MAX_ROWS = 60


def _match(kind, p):
    t = (p.get("posko_type") or "").lower()
    fns = p.get("functions") or []
    if kind == "logistik":
        return "logistics" in fns
    if kind == "distribusi":
        return t == "transport"
    if kind == "medis":
        return t == "medical"
    if kind == "shelter":
        return "shelter" in fns or t == "shelter"
    if kind == "dapur":
        return "kitchen" in fns or t == "kitchen"
    return False


def _metrics_logistik(name, event):
    from rescue_net.control_centre.posko import logistik_board
    b = logistik_board(name, event)
    k = b.get("kpi") or {}
    role = b.get("logistics_role")
    return {
        "peran": "Pengumpul" if role == "collector" else ("Penerima" if role == "receiver" else None),
        "stok_item": k.get("stok_item"),
        "stok_menipis": k.get("stok_menipis"),
        "kebutuhan_terbuka": k.get("kebutuhan_terbuka"),
        "kebutuhan_kritis": k.get("kebutuhan_kritis"),
        "bantuan_menuju": k.get("bantuan_menuju"),
        "jiwa_dilayani": k.get("jiwa_dilayani"),
    }


def _metrics_distribusi(name, event):
    from rescue_net.control_centre.distribusi import posko_distribusi_board
    b = posko_distribusi_board(name, event)
    t = b.get("totals") or {}
    aktif = sum(1 for a in (b.get("armada") or [])
                if str(a.get("status") or "") not in ("arrived", "completed", "cancelled"))
    cap = _num(t.get("kapasitas_total_kg"))
    used = _num(t.get("kapasitas_terpakai_kg"))
    return {
        "armada": t.get("armada_count"),
        "armada_aktif": aktif,
        "kapasitas_kg": cap,
        "tersedia_kg": t.get("kapasitas_tersedia_kg"),
        "terpakai_pct": round(used * 100 / cap) if cap else None,
        "booking_menunggu": t.get("booking_menunggu"),
        "booking_terkonfirmasi": t.get("booking_terkonfirmasi"),
    }


def _metrics_dapur(name, event):
    from rescue_net import api_kitchen
    b = api_kitchen.kitchen_board(posko=name, disaster_event=event)
    t = b.get("totals") or {}
    return {
        "jiwa_dilayani": t.get("jiwa_dilayani"),
        "kapasitas_porsi_hari": t.get("kapasitas_porsi_hari"),
        "produksi_hari_ini": t.get("produksi_hari_ini"),
        "distribusi_hari_ini": t.get("distribusi_hari_ini"),
        "gap_porsi": t.get("gap_porsi"),
        "bahan_kritis": t.get("bahan_kritis"),
    }


def _metrics_shelter(name, event):
    from rescue_net import api_shelter
    b = api_shelter.shelter_board(disaster_event=event, posko=name)
    t = b.get("totals") or {}
    cap = _num(t.get("kapasitas_maksimal"))
    cur = _num(t.get("total_penghuni"))
    return {
        "penghuni": t.get("total_penghuni"),
        "kapasitas": t.get("kapasitas_maksimal"),
        "okupansi_pct": round(cur * 100 / cap) if cap else None,
        "kelompok_rentan": t.get("kelompok_rentan"),
        "kebutuhan_kritis": sum(1 for k in (b.get("kebutuhan_dasar") or []) if k.get("status") == "kritis"),
    }


def _metrics_medis(name, event):
    out = {
        "kebutuhan_terbuka": frappe.db.count("RN Logistic Need", {"posko": name, "need_status": ["in", ["open", "needs_review"]]}),
        "stok_item": frappe.db.count("RN Stock Observation", {"posko": name}),
        "pasien_aktif": None,  # data pasien hanya untuk petugas posko
        "pasien_merah": None,
    }
    try:
        from rescue_net import api_medical
        d = api_medical.dashboard(posko=name)
        cases = d.get("cases") if isinstance(d, dict) else None
        if cases and any(c.get("posko") == name for c in cases):
            done = {"discharged", "deceased", "closed"}
            act = [c for c in cases if c.get("posko") == name and c.get("case_status") not in done]
            out["pasien_aktif"] = len(act)
            out["pasien_merah"] = sum(1 for c in act if c.get("triage_status") == "red")
    except Exception:
        pass
    return out


_METRICS = {
    "logistik": _metrics_logistik,
    "distribusi": _metrics_distribusi,
    "medis": _metrics_medis,
    "shelter": _metrics_shelter,
    "dapur": _metrics_dapur,
}


def _last_update(names):
    """Waktu data terakhir per posko: posko itu sendiri + stok + kebutuhan."""
    out = {}
    if not names:
        return out
    for dt, field in (("RN Posko", "name"), ("RN Stock Observation", "posko"), ("RN Logistic Need", "posko")):
        try:
            for posko, ts in frappe.db.sql(
                f"select `{field}`, max(modified) from `tab{dt}` where `{field}` in %(n)s group by `{field}`",
                {"n": tuple(names)},
            ):
                if ts and (posko not in out or ts > out[posko]):
                    out[posko] = ts
        except Exception:
            continue
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def posko_summary(disaster_event, kind):
    """Satu baris per posko jenis `kind` di bencana ini. Publik (tamu) boleh; angka mengikuti
    aturan visibilitas papan posko masing-masing."""
    kind = str(kind or "").lower()
    if kind not in KINDS:
        frappe.throw("Jenis posko tidak dikenal")
    event = canonical_event(disaster_event)
    viewer = _poskos_viewer_context()
    mine = set(viewer.get("manages") or [])

    pts = [p for p in map_points(event) if _match(kind, p)][:_MAX_ROWS]
    names = [p["posko_id"] for p in pts]
    info = {}
    if names:
        for r in frappe.get_all("RN Posko", filters={"name": ["in", names]},
                                fields=["name", "city_name", "district_name", "province_name", "verification_status",
                                        "organization", "accept_goods"],
                                limit_page_length=len(names)):
            info[r.name] = r
    orgs = {o for o in (r.organization for r in info.values()) if o}
    org_titles = dict(frappe.get_all("RN Organization", filters={"name": ["in", list(orgs)]},
                                     fields=["name", "title"], as_list=True)) if orgs else {}
    last = _last_update(names)

    rows = []
    for p in pts:
        name = p["posko_id"]
        r = info.get(name) or {}
        try:
            metrics = _METRICS[kind](name, event)
        except Exception:
            frappe.log_error(title="posko_summary metrics", message=frappe.get_traceback())
            metrics = {}
        rows.append({
            "posko": name,
            "title": p.get("name"),
            "organization": org_titles.get(r.get("organization")) or r.get("organization"),
            "lokasi": ", ".join(x for x in (r.get("district_name"), r.get("city_name")) if x) or r.get("province_name") or p.get("address"),
            "situation": p.get("situation"),
            "status": p.get("status"),
            "verification_status": r.get("verification_status"),
            "public_participation": p.get("public_participation"),
            "detail_allowed": p.get("detail_allowed"),
            "mine": name in mine,
            "last_update": last.get(name),
            "metrics": metrics,
        })

    sit_rank = {"critical": 0, "warning": 1}
    rows.sort(key=lambda x: (0 if x["mine"] else 1, sit_rank.get(x["situation"], 2), (x["title"] or "").lower()))
    return {"disaster_event": event, "kind": kind, "rows": rows, "viewer": viewer, "generated_at": frappe.utils.now()}
