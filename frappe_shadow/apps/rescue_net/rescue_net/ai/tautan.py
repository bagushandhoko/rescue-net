"""Tautan objek untuk hasil AI (owner 2026-11-17: "ai analisis harus bisa di klik
sampai ke objek yang disarankan atau dikatakan"). Dibuat Suri (Claude CT105).

tautan_objek(ids, disaster_event_id) menerima ID yang muncul di teks AI dan
mengembalikan {id: {label, url, jenis}} untuk yang benar-benar ada, plus daftar
nama posko bencana itu agar nama posko di teks juga bisa diklik.
Label sengaja tanpa data pribadi (laporan warga, pasien, orang hilang hanya jenisnya);
hak lihat isi tetap dijaga halaman tujuan."""
import re
from urllib.parse import quote

import frappe

from rescue_net.ai.common import _require_login
from rescue_net.reference_resolver import resolve_disaster_event

_ID = re.compile(r"^[A-Za-z0-9_:.\-]{4,140}$")
_MAX = 400

# (doctype, jenis, field label aman atau None)
JENIS = [
    ("RN Posko", "Posko", "title"),
    ("RN Logistic Need", "Kebutuhan", "item_name"),
    ("RN Stock Observation", "Stok", "item_name"),
    ("RN Transport Space", "Armada", "title"),
    ("RN Distribution Flow", "Kiriman", "item_name"),
    ("RN Aid Offer", "Bantuan", "item_name"),
    ("RN Community Report", "Laporan warga", None),
    ("RN Shelter Need", "Kebutuhan shelter", "item_name"),
    ("RN Shelter Occupancy", "Hunian shelter", None),
    ("RN Medical Case", "Kasus medis", None),
    ("RN Kitchen Production", "Produksi dapur", None),
    ("RN Volunteer Assignment", "Penugasan relawan", "task_title"),
    ("RN Missing Person Report", "Laporan orang hilang", None),
    ("RN Found Person Report", "Laporan orang ditemukan", None),
    ("RN Recovery Project", "Proyek pemulihan", "project_name"),
    ("RN Action Plan", "Rencana aksi", "title"),
    ("RN Donor Program", "Program donasi", "title"),
    ("RN Procurement Tender", "Tender", "title"),
    ("RN Disaster Event", "Bencana", "title"),
]

_POSKO_PAGE = {
    "logistics": "posko-logistik.html", "collection_hub": "posko-logistik.html",
    "transport": "posko-distribusi.html", "medical": "posko-medis-detail.html",
    "shelter": "shelter-detail.html", "kitchen": "dapur-umum.html",
    "equipment": "posko-alat.html", "communication": "alat-komunikasi.html",
    "volunteer": "management-relawan.html", "sar": "search-found.html",
}


def _ev(v):
    return str(v or "").replace("disaster_events:", "")


def _q(v):
    return quote(str(v or ""), safe="")


def _pid(v):
    return str(v or "").replace("posko_nodes:", "")


def posko_url(pid, event=None):
    if not pid:
        return None
    row = frappe.db.get_value("RN Posko", pid, ["name", "posko_type", "disaster_event"], as_dict=True)
    if not row:
        return None
    page = _POSKO_PAGE.get(str(row.posko_type or "").lower(), "posko-detail.html")
    return f"{page}?id={_q(_pid(row.name))}&event={_q(_ev(event or row.disaster_event))}"


def _field(doctype, name, field):
    if not field or not frappe.get_meta(doctype).has_field(field):
        return None
    return frappe.db.get_value(doctype, name, field)


def url_for(doctype, name, event=None):
    """Halaman tujuan untuk satu objek RN (None bila tidak ada halaman)."""
    meta = frappe.get_meta(doctype)

    def f(x):
        return frappe.db.get_value(doctype, name, x) if meta.has_field(x) else None

    ev = _ev(event or f("disaster_event"))
    if doctype == "RN Posko":
        return posko_url(name, event)
    if doctype == "RN Transport Space":
        p = f("coordination_posko")
        base = f"posko-distribusi.html?id={_q(_pid(p))}&" if p else "management-distribusi.html?"
        return base + f"event={_q(ev)}&armada={_q(name)}"
    if doctype == "RN Distribution Flow":
        return f"lacak-logistik.html?flow={_q(name)}"
    if doctype == "RN Aid Offer":
        return posko_url(f("target_posko"), ev) or f"kebutuhan-publik.html?event={_q(ev)}"
    if doctype == "RN Recovery Project":
        return f"recovery-reconstruction.html?id={_q(name)}&event={_q(ev)}"
    if doctype == "RN Donor Program":
        return f"donor-program.html?id={_q(name)}"
    if doctype == "RN Procurement Tender":
        return f"pengadaan-tender.html?event={_q(ev)}"
    if doctype == "RN Disaster Event":
        return f"disaster-detail.html?id={_q(_ev(name))}"
    if doctype in ("RN Missing Person Report", "RN Found Person Report"):
        return f"search-found.html?event={_q(ev)}"
    if doctype == "RN Volunteer Assignment":
        return f"management-relawan.html?event={_q(ev)}"
    p = f("posko")
    if p:
        return posko_url(p, ev)
    if doctype == "RN Community Report":
        return f"laporan-masyarakat.html?event={_q(ev)}"
    if doctype == "RN Action Plan":
        return f"war-room.html?event={_q(ev)}"
    return None


# awalan ID -> doctype yang dicoba lebih dulu (supaya ratusan ID laporan tetap cepat)
_AWALAN = [
    ("rn-report-", "RN Community Report"), ("rn-logistic-need-", "RN Logistic Need"),
    ("rn-transport-", "RN Transport Space"), ("rn-aid-", "RN Aid Offer"), ("aid_offers:", "RN Aid Offer"),
    ("rn-posko-", "RN Posko"), ("posko_nodes:", "RN Posko"), ("rn-stock-", "RN Stock Observation"),
    ("rn-flow-", "RN Distribution Flow"), ("disaster_events:", "RN Disaster Event"), ("event-", "RN Disaster Event"),
]


def _urutan(i):
    il = i.lower()
    dulu = [dt for a, dt in _AWALAN if il.startswith(a)]
    if not dulu:
        return JENIS
    return [j for j in JENIS if j[0] in dulu] + [j for j in JENIS if j[0] not in dulu]


def resolve(ids, disaster_event_id=None):
    hasil = {}
    for raw in list(ids or [])[:_MAX]:
        i = str(raw or "").strip().strip("[]().,;`*'\"")
        if not i or i in hasil or not _ID.match(i):
            continue
        for dt, jenis, lf in _urutan(i):
            try:
                ada = frappe.db.exists(dt, i)
            except Exception:
                ada = False
            if not ada:
                continue
            url = url_for(dt, i, disaster_event_id)
            if not url:
                break
            nama = _field(dt, i, lf)
            hasil[i] = {"jenis": jenis, "label": f"{jenis}: {nama}" if nama else jenis, "url": url}
            break
    return hasil


def _varian(t):
    """Nama lengkap + nama tanpa keterangan dalam kurung di akhir (AI sering menyingkat)."""
    t = (t or "").strip()
    out = [t] if len(t) >= 6 else []
    pendek = re.sub(r"\s*\([^()]*\)\s*$", "", t).strip()
    if pendek != t and len(pendek) >= 10:
        out.append(pendek)
    return out


def posko_event(ev):
    """Nama posko dan armada bencana ini -> halaman, agar nama di teks AI ikut bisa diklik."""
    out = []
    if not ev:
        return out
    for r in frappe.get_all("RN Posko", filters={"disaster_event": ev}, fields=["name", "title"], limit=400):
        u = posko_url(r.name, ev)
        for t in _varian(r.title) if u else []:
            out.append({"title": t, "url": u, "label": "Posko: " + (r.title or "")})
    try:
        for r in frappe.get_all("RN Transport Space", filters={"disaster_event": ev}, fields=["name", "title"], limit=400):
            u = url_for("RN Transport Space", r.name, ev)
            for t in _varian(r.title) if u else []:
                out.append({"title": t, "url": u, "label": "Armada: " + (r.title or "")})
    except Exception:
        pass
    return out


@frappe.whitelist(methods=["POST"])
def tautan_objek(ids=None, disaster_event_id=None):
    _require_login()
    if isinstance(ids, str):
        s = ids.strip()
        ids = frappe.parse_json(s) if s.startswith("[") else [x for x in re.split(r"[\s,]+", s) if x]
    ev = None
    if disaster_event_id:
        try:
            ev = resolve_disaster_event(disaster_event_id)
        except Exception:
            ev = None
    return {"objek": resolve(ids or [], ev), "posko": posko_event(ev)}
