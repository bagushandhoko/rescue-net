"""Foto AI bercap SIMULASI untuk UI Peduli — Rekonstruksi Fasilitas Belajar (rn-donor-f5fa707a9c62). Jalankan SETELAH
ui_rekonstruksi.py (Nala). Idempoten. Aset di /tmp/ui-rekonstruksi."""
import base64, json, os
import frappe
A, PROG, PIC = "/tmp/ui-rekonstruksi", "rn-donor-f5fa707a9c62", "sim-ui-peduli@example.org"
from rescue_net import api_donor_program as dp
done = []
def wd(): return json.loads(frappe.db.get_value("RN Donor Program", PROG, "work_drawings") or "[]")
FOTO = [("cover", "Selasar blok kelas setelah rehabilitasi — rencana (FOTO AI simulasi)"),
        ("kondisi", "Kondisi awal: kelas & perpustakaan rusak berat akibat gempa (FOTO AI simulasi)"),
        ("pondasi", "Progres: penyanggaan & perkuatan kolom jaket beton (FOTO AI simulasi)"),
        ("rangka", "Siswa belajar bergiliran di blok aman (FOTO AI simulasi)")]
frappe.set_user(PIC)
try:
    for k, label in FOTO:
        fn = "rek-foto-ai-%s.jpg" % k
        if not any(fn.rsplit(".", 1)[0] in d["url"] for d in wd()):
            dp.upload_program_file(PROG, "gambar", fn, base64.b64encode(open(os.path.join(A, fn), "rb").read()).decode(), label=label)
            done.append("unggah " + fn)
    frappe.db.commit()
finally:
    frappe.set_user("Administrator")
url = {k: next((d["url"] for d in wd() if "rek-foto-ai-" + k in d["url"]), None) for k, _ in FOTO}
if url["cover"] and frappe.db.get_value("RN Donor Program", PROG, "cover_image_url") != url["cover"]:
    frappe.db.set_value("RN Donor Program", PROG, "cover_image_url", url["cover"]); done.append("sampul")
ev = frappe.db.get_value("RN Donor Program", PROG, "disaster_event")
for k, ts in (("kondisi", "2026-11-05 09:00"), ("pondasi", "2026-11-20 15:00"), ("rangka", "2026-11-22 10:00")):
    n = "evidence-sim-uirek-" + k
    if url[k] and not frappe.db.exists("RN Evidence File", n):
        e = frappe.get_doc({"doctype": "RN Evidence File", "legacy_id": n, "legacy_source": "seed-simulasi", "title": dict(FOTO)[k].replace("FOTO AI simulasi", "FOTO AI SIMULASI"),
                            "disaster_event": ev, "linked_object_type": "RN Donor Program", "linked_object_id": PROG, "evidence_type": "photo",
                            "filename": url[k].rsplit("/", 1)[-1], "file_path": url[k], "mime_type": "JPG", "verification_status": "verified", "visibility": "public"}).insert(ignore_permissions=True)
        frappe.db.sql("update `tabRN Evidence File` set creation=%s where name=%s", (ts, e.name)); done.append("bukti " + k)
frappe.db.commit()
print("\nREK_FOTO selesai")
for d in done: print("DONE", d)
