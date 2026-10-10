"""Alat Mode Latihan (Fase 10g): buat latihan dari templat, pratinjau + bersihkan.

Pembersihan MENGHAPUS data, jadi: hanya event ``is_drill=1``; menghapus per nama yang terdaftar di pratinjau
(tidak pernah filter 'in' dengan daftar kosong — pelajaran insiden 5 posko terhapus); wajib mengulang total dari
pratinjau (``confirm_total``); dan berhenti bila ada catatan keuangan/audit di event itu (ditinjau manual).
"""

import frappe

from rescue_net.services.drill import is_drill_event

# dihapus HANYA bila event latihan; urutan: anak dulu, posko, lalu event
_PROTECTED = ("RN Cash Donation", "RN Donor Program", "RN Donor Program Update", "RN Verification Action",
              "RN AI Usage Log")
LABEL = "[LATIHAN] "

TEMPLATES = {
    "banjir": {
        "title": "Banjir Bandang (Latihan)", "severity": "high", "location_summary": "Wilayah fiktif untuk latihan",
        "poskos": [("Posko Induk", "command"), ("Posko Logistik", "logistics")],
        "needs": [("Beras", 500, "kg", "critical"), ("Air minum", 2000, "liter", "high"), ("Selimut", 300, "pcs", "medium")],
    },
    "gempa": {
        "title": "Gempa Bumi (Latihan)", "severity": "critical", "location_summary": "Wilayah fiktif untuk latihan",
        "poskos": [("Posko Medis", "medical"), ("Posko Pengungsian", "shelter")],
        "needs": [("Tenda keluarga", 100, "unit", "critical"), ("Obat luka", 200, "box", "high"), ("Makanan siap saji", 800, "pcs", "high")],
    },
    "karhutla": {
        "title": "Kebakaran Hutan dan Lahan (Latihan)", "severity": "high", "location_summary": "Wilayah fiktif untuk latihan",
        "poskos": [("Posko Lapangan", "command"), ("Posko Medis", "medical")],
        "needs": [("Masker N95", 1000, "pcs", "critical"), ("Air bersih", 3000, "liter", "high")],
    },
}


def _linked_doctypes():
    """DocType yang punya kolom disaster_event, tanpa RN Posko/RN Disaster Event sendiri."""
    out = []
    for dt in frappe.get_all("DocType", filters={"module": ["like", "RN %"], "istable": 0}, pluck="name"):
        if dt in ("RN Posko", "RN Disaster Event"):
            continue
        if frappe.get_meta(dt).has_field("disaster_event"):
            out.append(dt)
    return sorted(out)


def create_drill(template="banjir"):
    """Buat event latihan + posko + kebutuhan berlabel [LATIHAN]. Mengembalikan nama event."""
    t = TEMPLATES.get(template)
    if not t:
        frappe.throw("Templat latihan tidak dikenal: {}".format(template))
    ev = frappe.get_doc({"doctype": "RN Disaster Event", "legacy_id": frappe.generate_hash(length=10),
                         "title": LABEL + t["title"], "severity": t["severity"], "event_status": "active",
                         "location_summary": t["location_summary"], "is_drill": 1,
                         "drill_label": "Latihan " + template}).insert(ignore_permissions=True)
    poskos = []
    for title, ptype in t["poskos"]:
        poskos.append(frappe.get_doc({"doctype": "RN Posko", "title": LABEL + title, "posko_type": ptype,
                                      "disaster_event": ev.name}).insert(ignore_permissions=True))
    for item, qty, unit, urgency in t["needs"]:
        frappe.get_doc({"doctype": "RN Logistic Need", "title": LABEL + item, "item_name": item, "quantity": qty,
                        "unit": unit, "urgency": urgency, "disaster_event": ev.name,
                        "posko": poskos[0].name}).insert(ignore_permissions=True)
    return ev.name


def preview_cleanup(event):
    """Daftar yang akan dihapus: {'event':, 'items': {doctype: [names]}, 'total':, 'blocked': {doctype: n}}.
    Tidak mengubah apa pun."""
    if not event or not is_drill_event(event):
        frappe.throw("Hanya event latihan (is_drill=1) yang bisa dibersihkan.")
    items, blocked = {}, {}
    for dt in _linked_doctypes():
        names = frappe.get_all(dt, filters={"disaster_event": event}, pluck="name")
        if not names:
            continue
        if dt in _PROTECTED:
            blocked[dt] = len(names)
        else:
            items[dt] = names
    posko_names = frappe.get_all("RN Posko", filters={"disaster_event": event}, pluck="name")
    if posko_names:
        items["RN Posko"] = posko_names
    items["RN Disaster Event"] = [event]
    return {"event": event, "items": items, "total": sum(len(v) for v in items.values()), "blocked": blocked}


def cleanup(event, confirm_total):
    """Hapus latihan sesuai pratinjau. ``confirm_total`` harus sama dengan total pratinjau saat ini."""
    p = preview_cleanup(event)
    if p["blocked"]:
        frappe.throw("Ada catatan keuangan/audit di event ini ({}); tinjau manual, tidak dihapus.".format(
            ", ".join("{}: {}".format(k, v) for k, v in p["blocked"].items())))
    if int(confirm_total or 0) != p["total"]:
        frappe.throw("Total konfirmasi ({}) tidak sama dengan pratinjau ({}); ulangi pratinjau.".format(confirm_total, p["total"]))
    deleted = {}
    for dt, names in p["items"].items():
        if not names:                       # daftar kosong tidak pernah memicu hapus massal
            continue
        for n in names:
            frappe.delete_doc(dt, n, ignore_permissions=True, force=True)
        deleted[dt] = len(names)
    return {"event": event, "deleted": deleted}
