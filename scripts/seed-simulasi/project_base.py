"""Detail Proyek (Project Base) realistis: visualisasi FOTO AI bercap SIMULASI untuk tender program UI Peduli (owner 24 Nov:
"tinggal gambar project base direalistiskan"). Idempoten. Aset di /tmp/pb."""
import os, frappe
from frappe.utils.file_manager import save_file
SET = [("pur8kre3or", "pb-kalianda-ai.jpg", {}),
       ("oq9k6g4kv8", "pb-meulaboh-ai.jpg", {"rab_total": 611912000})]
for tender, fn, extra in SET:
    if not frappe.db.exists("RN Procurement Tender", tender): print("TEMUAN tender hilang", tender); continue
    cur = frappe.db.get_value("RN Procurement Tender", tender, "design_image_url") or ""
    if fn.rsplit(".", 1)[0] in cur: continue
    f = save_file(fn, open(os.path.join("/tmp/pb", fn), "rb").read(), "RN Procurement Tender", tender, is_private=0)
    vals = {"design_image_url": f.file_url, **extra}
    if tender == "oq9k6g4kv8":
        wd = frappe.db.get_value("RN Donor Program", "rn-donor-f5fa707a9c62", "rab_file_url")
        if wd: vals["rab_document_url"] = wd
    frappe.db.set_value("RN Procurement Tender", tender, vals); print("DONE", tender, f.file_url)
frappe.db.commit(); print("PB selesai")
