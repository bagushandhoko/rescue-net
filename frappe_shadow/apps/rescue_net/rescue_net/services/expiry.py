"""Kedaluwarsa stok (Fase 10d): lot per penerimaan + stok efektif.

Stok = rangkaian snapshot (lihat services/stock.py), jadi lot dicatat terpisah di RN Stock Batch (append-only) saat
barang bertanggal kedaluwarsa diterima. Sisa stok dialokasikan ke lot secara FEFO: yang paling dulu kedaluwarsa
keluar dulu, jadi sisa stok berada di lot yang paling akhir kedaluwarsa. Stok yang melebihi jumlah lot dianggap tanpa
tanggal. Kuantitas kedaluwarsa = bagian sisa stok yang dialokasikan ke lot yang sudah lewat tanggalnya — dihitung
saat dibaca, tidak menulis ulang data apa pun.
"""

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

SOON_DAYS = 30
SOON_DAYS_MEDICAL = 60
_MEDICAL = ("obat", "medis", "kesehatan", "vaksin", "infus", "antibiotik")


def window_days(item_name, category=None):
    text = "{} {}".format(item_name or "", category or "").lower()
    return SOON_DAYS_MEDICAL if any(k in text for k in _MEDICAL) else SOON_DAYS


def record_lot(posko, item_name, unit, qty, expiry_date, batch_no=None, disaster_event=None, source=None):
    """Catat lot; tanpa tanggal kedaluwarsa tidak ada yang dicatat. Mengembalikan nama lot atau None."""
    if not expiry_date or flt(qty) <= 0:
        return None
    from frappe.utils import now_datetime

    return frappe.get_doc({
        "doctype": "RN Stock Batch", "posko": posko, "disaster_event": disaster_event, "item_name": item_name,
        "unit": unit, "quantity": flt(qty), "expiry_date": getdate(expiry_date), "batch_no": (batch_no or None),
        "source": source, "received_at": now_datetime(),
    }).insert(ignore_permissions=True).name


def _remaining_stock(posko, item_name, unit):
    """Stok efektif saat ini tanpa mengunci/melempar (snapshot terakhir dikurangi pemakaian dapur sesudahnya)."""
    from rescue_net.services.stock import consumed_after

    latest = frappe.db.sql(
        "SELECT quantity, unit, observed_at, source_updated_at, creation FROM `tabRN Stock Observation` "
        "WHERE posko=%s AND item_name=%s ORDER BY observed_at DESC, creation DESC LIMIT 1",
        (posko, item_name), as_dict=True)
    if not latest or (latest[0].unit or "").strip() not in ("", unit):
        return None
    s = latest[0]
    baseline = s.observed_at or s.source_updated_at or s.creation
    return max(flt(s.quantity) - consumed_after(posko, item_name, unit, baseline), 0.0)


def lots_status(posko, item_name, unit, today=None):
    """Lot dengan sisa hasil alokasi FEFO, terurut paling dulu kedaluwarsa. Lot habis tidak ditampilkan."""
    today = getdate(today or nowdate())
    lots = frappe.get_all("RN Stock Batch", filters={"posko": posko, "item_name": item_name, "unit": unit},
                          fields=["name", "quantity", "expiry_date", "batch_no"], order_by="expiry_date asc, creation asc",
                          limit_page_length=500)
    remaining = _remaining_stock(posko, item_name, unit)
    if remaining is None:
        return []
    out = []
    for lot in reversed(lots):                      # alokasikan dari lot yang paling akhir kedaluwarsa
        take = min(remaining, flt(lot.quantity))
        remaining -= take
        if take > 0:
            days = (getdate(lot.expiry_date) - today).days
            out.append({"lot": lot.name, "batch_no": lot.batch_no, "expiry_date": str(lot.expiry_date),
                        "quantity": take, "days_left": days})
    out.sort(key=lambda r: r["expiry_date"])
    return out


def _state(days, soon):
    return "expired" if days < 0 else ("soon" if days <= soon else "ok")


def expired_quantity(posko, item_name, unit):
    return sum(r["quantity"] for r in lots_status(posko, item_name, unit) if r["days_left"] < 0)


def expiring_report(posko, days=None):
    """Semua lot bersisa di posko dengan status (expired/soon/ok), urut FEFO; plus ringkasan."""
    items = frappe.get_all("RN Stock Batch", filters={"posko": posko}, fields=["item_name", "unit"], distinct=True,
                           limit_page_length=500)
    rows = []
    for it in items:
        cat = frappe.db.get_value("RN Stock Observation", {"posko": posko, "item_name": it.item_name}, "canonical_category")
        soon = days or window_days(it.item_name, cat)
        for r in lots_status(posko, it.item_name, it.unit):
            rows.append(dict(r, item_name=it.item_name, unit=it.unit, state=_state(r["days_left"], soon)))
    rows.sort(key=lambda r: r["expiry_date"])
    return {"posko": posko, "rows": rows,
            "expired": sum(1 for r in rows if r["state"] == "expired"),
            "soon": sum(1 for r in rows if r["state"] == "soon")}


def daily_expiry_notify():
    """Terjadwal harian: satu pesan per posko yang punya stok kedaluwarsa/segera kedaluwarsa (berbatas laju: sekali sehari)."""
    from rescue_net.api_notify import notify_posko

    for posko in frappe.get_all("RN Stock Batch", pluck="posko", distinct=True, limit_page_length=1000):
        rep = expiring_report(posko)
        if not (rep["expired"] or rep["soon"]):
            continue
        notify_posko(posko, "Rescue-Net: {} barang kedaluwarsa dan {} segera kedaluwarsa di posko Anda. Cek stok.".format(
            rep["expired"], rep["soon"]), "stock_expiry")
