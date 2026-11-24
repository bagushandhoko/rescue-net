"""Foto AI bercap SIMULASI untuk program Baduy (rn-donor-fc5d3f8cd6c3). Jalankan SETELAH baduy_realistis.py (Nala).
Idempoten. Aset di /tmp/baduy-foto."""
import base64, json, os
import frappe
from frappe.utils.file_manager import save_file
A, PROG, PIC, TENDER = "/tmp/baduy-foto", "rn-donor-fc5d3f8cd6c3", "baduy.demo@rescue-net.local", "4pa993bumh"
from rescue_net import api_donor_program as dp
done = []
def wd(): return json.loads(frappe.db.get_value("RN Donor Program", PROG, "work_drawings") or "[]")
FOTO = [("pb-baduy", "Rencana rumah panggung adat setelah dibangun kembali (FOTO AI simulasi)"),
        ("baduy-kondisi", "Kondisi pasca-kebakaran (FOTO AI simulasi)"),
        ("baduy-rangka", "Progres: rumah tahap 1 berdiri, gotong royong (FOTO AI simulasi)"),
        ("baduy-atap", "Progres: pemasangan atap kiray & ijuk (FOTO AI simulasi)"),
        ("baduy-bahan", "Bahan dipikul warga tanpa kendaraan (FOTO AI simulasi)")]
# lepas gambar kartun lama bila masih ada
OLD = ("sampul-sim-baduy", "kondisi-sim-baduy", "progres-rangka-sim-baduy", "progres-atap-sim-baduy", "rumah-jadi-sim-baduy")
frappe.set_user(PIC)
try:
    for d in wd():
        if not d.get("kind") and str(d.get("name") or "").startswith(OLD):
            dp.remove_program_file(PROG, "gambar", d["url"]); done.append("lepas " + d["name"])
    for k, label in FOTO:
        fn = k + "-ai.jpg"
        if not any(k + "-ai" in d["url"] for d in wd()):
            dp.upload_program_file(PROG, "gambar", fn, base64.b64encode(open(os.path.join(A, fn), "rb").read()).decode(), label=label)
            done.append("unggah " + fn)
    frappe.db.commit()
finally:
    frappe.set_user("Administrator")
url = {k: next((d["url"] for d in wd() if k + "-ai" in d["url"]), None) for k, _ in FOTO}
if url["pb-baduy"] and frappe.db.get_value("RN Donor Program", PROG, "cover_image_url") != url["pb-baduy"]:
    frappe.db.set_value("RN Donor Program", PROG, "cover_image_url", url["pb-baduy"]); done.append("sampul")
if url["baduy-atap"] and frappe.db.exists("RN Procurement Tender", TENDER):
    frappe.db.set_value("RN Procurement Tender", TENDER, "design_image_url", url["baduy-atap"]); done.append("tender atap: gambar")
ev = frappe.db.get_value("RN Donor Program", PROG, "disaster_event")
for k, ts in (("baduy-kondisi", "2026-11-21 09:00"), ("baduy-bahan", "2026-11-23 10:00"), ("baduy-rangka", "2026-11-24 11:00"), ("baduy-atap", "2026-11-24 15:00")):
    n = "evidence-sim-baduy-" + k
    if url[k] and not frappe.db.exists("RN Evidence File", n):
        e = frappe.get_doc({"doctype": "RN Evidence File", "legacy_id": n, "legacy_source": "seed-simulasi", "title": dict(FOTO)[k].replace("FOTO AI simulasi", "FOTO AI SIMULASI"),
                            "disaster_event": ev, "linked_object_type": "RN Donor Program", "linked_object_id": PROG, "evidence_type": "photo",
                            "filename": url[k].rsplit("/", 1)[-1], "file_path": url[k], "mime_type": "JPG", "verification_status": "verified", "visibility": "public"}).insert(ignore_permissions=True)
        frappe.db.sql("update `tabRN Evidence File` set creation=%s where name=%s", (ts, e.name)); done.append("bukti " + k)
frappe.db.commit()
print("\nBADUY_FOTO selesai")
for d in done: print("DONE", d)
