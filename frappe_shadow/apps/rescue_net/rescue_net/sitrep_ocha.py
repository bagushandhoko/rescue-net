"""Tambahan SITREP format OCHA (owner 2026-11-12: "cek laporan sitrep ... sesuai template international" + "lengkapi
dengan API protokol untuk pelaporan ini"). Dipanggil dari api_sitrep.sitrep; semua bagian aman untuk publik
(tanpa nomor HP/kontak pribadi, organisasi tertutup tetap ringkasan). Dibuat Suri (Claude CT105)."""

import re

import frappe
from frappe.utils import add_to_date, cint, flt, get_datetime

_TEST = re.compile(r"smoke test|\[uji|uji-beban|uji beban|\btest\b", re.I)
_PRIO = {"critical": "kritis", "urgent": "mendesak", "high": "tinggi", "medium": "sedang", "low": "rendah"}
_STATUS = {"planned": "direncanakan", "in_progress": "berjalan", "done": "selesai", "completed": "selesai",
           "active": "aktif", "closed": "ditutup", "monitoring": "pemantauan", "stabilized": "stabil", "treated": "ditangani",
           "referred": "dirujuk", "discharged": "pulang", "logistics": "logistik", "distribution": "distribusi",
           "transport": "transportasi", "shelter": "shelter", "health": "kesehatan"}
# sektor/klaster OCHA -> kata kunci barang kebutuhan
_SEKTOR = [
    ("wash", "Air bersih, sanitasi & higiene (WASH)", r"air|toren|jerigen|sanitasi|toilet|sabun|higien|hygiene|kebersihan|pembalut|popok"),
    ("pangan", "Pangan", r"beras|makan|mie|porsi|lauk|susu|gizi|minyak|gula|telur|roti|biskuit|sembako"),
    ("kesehatan", "Kesehatan", r"obat|masker|medis|oksigen|p3k|vitamin|infus|perban|alat kesehatan"),
    ("shelter", "Hunian sementara (Shelter/NFI)", r"shelter|terpal|tenda|selimut|matras|tikar|kasur|pakaian|kelambu|lampu|terminal|nfi"),
    ("logistik", "Logistik & transportasi", r"solar|bensin|bbm|pertalite|genset|truk|perahu|kendaraan|oli"),
]


def clean_recommendations(recs):
    out = []
    for r in recs or []:
        t = "%s %s" % (r.get("title") or "", r.get("reason") or "")
        if _TEST.search(t):
            continue
        reason = r.get("reason") or ""
        for k, v in _STATUS.items():
            reason = re.sub(r"\b%s\b" % k, v, reason)
        for k, v in _PRIO.items():
            reason = re.sub(r"\b%s\b" % k, v, reason)
        out.append({"judul": r.get("title"), "alasan": reason.strip(" -"),
                    "prioritas": _PRIO.get(str(r.get("priority") or "").lower(), r.get("priority"))})
    return out


def sektor(event, layanan, logistik):
    """Per sektor: kebutuhan terbuka (jumlah item & kekurangan kritis), respons, kesenjangan."""
    try:
        from rescue_net.api_public_needs import board
        needs = (board(event=event) or {}).get("needs") or []
    except Exception:
        needs = []
    rows = {k: {"kode": k, "nama": n, "kebutuhan": 0, "kritis": 0, "kesenjangan": [], "respons": ""} for k, n, _ in _SEKTOR}
    rows["lainnya"] = {"kode": "lainnya", "nama": "Lainnya", "kebutuhan": 0, "kritis": 0, "kesenjangan": [], "respons": ""}
    for n in needs:
        item = str(n.get("item") or "")
        if _TEST.search(item):
            continue
        key = next((k for k, _, rx in _SEKTOR if re.search(rx, item, re.I)), "lainnya")
        r = rows[key]
        r["kebutuhan"] += 1
        if n.get("critical"):
            r["kritis"] += 1
        if n.get("gap") not in (None, "", 0) and len(r["kesenjangan"]) < 3:
            r["kesenjangan"].append("%s: kurang %s %s" % (item, _fmt(n.get("gap")), n.get("unit") or ""))
    sh = (layanan or {}).get("shelter") or {}
    med = (layanan or {}).get("medis_per_status") or {}
    rows["shelter"]["respons"] = "%s pengungsi di %s titik shelter (kapasitas %s)" % (
        _fmt(sh.get("penghuni")), _fmt(sh.get("titik")), _fmt(sh.get("kapasitas")))
    rows["pangan"]["respons"] = "%s porsi dapur umum tercatat" % _fmt((layanan or {}).get("porsi_dapur"))
    rows["kesehatan"]["respons"] = ", ".join("%s pasien %s" % (_fmt(v), _STATUS.get(k, k)) for k, v in med.items()) or "belum ada data pasien"
    rows["logistik"]["respons"] = "%s kiriman tercatat, %s terhambat, %s tawaran bantuan" % (
        _fmt((logistik or {}).get("kiriman_total")), _fmt((logistik or {}).get("kiriman_terhambat")),
        _fmt((logistik or {}).get("tawaran_bantuan")))
    rows["wash"]["respons"] = "lihat kebutuhan air & sanitasi di posko"
    return [r for r in rows.values() if r["kebutuhan"] or r["respons"]]


def pendanaan(event):
    if not frappe.db.exists("DocType", "RN Donor Program"):
        return {}
    meta = frappe.get_meta("RN Donor Program")
    if not meta.has_field("disaster_event"):
        return {}
    fields = ["name", "program_name", "status"] + [f for f in ("budget_target", "budget_received", "kitabisa_collected", "current_amount", "target_amount")
                                             if meta.has_field(f)]
    progs = frappe.get_all("RN Donor Program", filters={"disaster_event": ["in", [event, "disaster_events:" + event]]},
                           fields=fields, limit_page_length=500, ignore_permissions=True)
    progs = [p for p in progs if not _TEST.search(p.get("program_name") or "")]
    target = sum(flt(p.get("budget_target")) for p in progs)
    masuk = sum(flt(p.get("budget_received")) + flt(p.get("kitabisa_collected")) for p in progs)
    return {"program": len(progs), "target_rp": int(target), "terkumpul_rp": int(masuk),
            "persen": round(masuk * 100 / target) if target else None}


def koordinasi(event, poskos):
    if not poskos:
        return {}
    rows = frappe.get_all("RN Posko", filters={"name": ["in", poskos]}, fields=["name", "organization", "posko_type", "operational_status"],
                          limit_page_length=1000, ignore_permissions=True)
    orgs = {r.organization for r in rows if r.organization}
    per = {}
    for r in rows:
        per[r.posko_type or "lainnya"] = per.get(r.posko_type or "lainnya", 0) + 1
    return {"organisasi": len(orgs), "posko": len(rows), "posko_per_jenis": per,
            "pusat_kendali": "Control Centre Rescue-Net (rescue-net.online/rescue-net/pages/war-room.html)"}


def nomor(dis, until, hours):
    start = dis.get("started_at") or dis.get("creation")
    try:
        days = (get_datetime(until) - get_datetime(start)).days
        return max(1, int(days * 24 / max(1, cint(hours))) + 1)
    except Exception:
        return 1


def highlights(situasi, layanan, perubahan, kebutuhan, dana):
    h = []
    sh = (layanan or {}).get("shelter") or {}
    if situasi.get("jiwa_terdampak"):
        h.append("%s jiwa terdampak; %s orang dilaporkan hilang." % (_fmt(situasi.get("jiwa_terdampak")), _fmt(situasi.get("orang_hilang") or 0)))
    if sh.get("penghuni"):
        pct = round(flt(sh.get("penghuni")) * 100 / flt(sh.get("kapasitas"))) if sh.get("kapasitas") else None
        h.append("%s pengungsi di %s titik shelter%s." % (_fmt(sh.get("penghuni")), _fmt(sh.get("titik")),
                                                        (" (%s%% kapasitas)" % pct) if pct is not None else ""))
    if situasi.get("posko_kritis"):
        h.append("%s dari %s posko aktif berstatus kritis." % (_fmt(situasi.get("posko_kritis")), _fmt(situasi.get("posko_aktif"))))
    if kebutuhan:
        h.append("Kesenjangan utama: %s." % (kebutuhan[0].get("judul") or "").replace("Tutup gap: ", ""))
    baru = [c for c in perubahan or [] if c.get("value")]
    if baru:
        h.append("Dalam periode ini: " + ", ".join("%s %s" % (_fmt(c["value"]), c["label"].lower()) for c in baru[:3]) + ".")
    if dana and dana.get("target_rp"):
        h.append("Pendanaan program khusus: Rp %s dari target Rp %s (%s%%)." % (_fmt(dana["terkumpul_rp"]), _fmt(dana["target_rp"]), dana.get("persen") or 0))
    return h[:6]


def _fmt(v):
    try:
        return "{:,}".format(int(round(flt(v)))).replace(",", ".")
    except Exception:
        return str(v if v is not None else "-")


def gambaran(event, dis, hours):
    """Situasi umum (OCHA "Situation overview"): jenis, lokasi, tingkat, sejak kapan — dari data bencana."""
    row = frappe.db.get_value("RN Disaster Event", event, ["title", "location_summary", "severity", "started_at", "event_status"],
                              as_dict=True) or {}
    sev = {"critical": "kritis", "high": "tinggi", "medium": "sedang", "low": "rendah"}.get(str(row.get("severity") or "").lower(),
                                                                                         row.get("severity") or "belum ditetapkan")
    hari = None
    try:
        if row.get("started_at"):
            hari = (frappe.utils.now_datetime() - get_datetime(row.get("started_at"))).days
    except Exception:
        hari = None
    teks = "%s%s. Tingkat keparahan: %s. Status: %s%s." % (
        row.get("title") or event, (" di " + row.get("location_summary")) if row.get("location_summary") else "",
        sev, _STATUS.get(str(row.get("event_status") or ""), row.get("event_status") or "-"),
        ("; berlangsung %s hari sejak %s" % (hari, str(row.get("started_at"))[:10])) if hari is not None else "")
    return teks


def kontak(poskos):
    """Kontak koordinasi untuk SITREP publik: nama posko & PIC (tanpa nomor — nomor hanya di halaman posko setelah login)."""
    if not poskos:
        return []
    rows = frappe.get_all("RN Posko", filters={"name": ["in", poskos], "posko_type": ["in", ["org_admin", "posko_operator", "field_assessment"]]},
                          fields=["name", "title", "posko_type", "officer_in_charge_name", "officer_in_charge_role"],
                          limit_page_length=10, ignore_permissions=True)
    return [{"posko": r.title, "peran": r.officer_in_charge_role or "", "pic": r.officer_in_charge_name or "",
             "tautan": "posko-detail.html?id=%s" % r.name} for r in rows if not _TEST.search(r.title or "")]
