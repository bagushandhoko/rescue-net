"""UI Peduli Sekolah Darurat (owner 24 Nov 16:05 "gambar masih bukan foto, rab nggak keliatan"): ilustrasi diganti FOTO AI
bercap SIMULASI (pollinations FLUX), RAB gambar 1 halaman panjang diganti 2 halaman terbaca. Idempoten. Aset di /tmp/ui-sim."""
import base64, json, os
import frappe
A, PROG, PIC = "/tmp/ui-sim", "rn-donor-ddc38efbfaf6", "sim-ui-peduli@example.org"
done, found = [], []
from rescue_net import api_donor_program as dp
def as_user(email, fn, *a, **kw):
    frappe.set_user(email)
    try:
        r = fn(*a, **kw); frappe.db.commit(); return r
    except Exception as e:
        frappe.db.rollback(); found.append("%s: %s" % (getattr(fn, "__name__", fn), str(e)[:200])); return None
    finally:
        frappe.set_user("Administrator")
def wd():
    return json.loads(frappe.db.get_value("RN Donor Program", PROG, "work_drawings") or "[]")
def up(kind, fn, label):
    r = as_user(PIC, dp.upload_program_file, PROG, kind, fn, base64.b64encode(open(os.path.join(A, fn), "rb").read()).decode(), label=label)
    if r is not None: done.append("unggah " + fn)
# RAB: buang PNG panjang, pasang 2 halaman
if not any("rab-hal-1" in d["url"] for d in wd()):
    for d in wd():
        if d.get("kind") == "rab" and "rab-full" in d["url"]:
            as_user(PIC, dp.remove_program_file, PROG, "rab", d["url"]); done.append("lepas rab-full")
    up("rab", "rab-hal-1.png", "RAB halaman 1/2 — pekerjaan I–VI (simulasi)")
    up("rab", "rab-hal-2.png", "RAB halaman 2/2 — pekerjaan VII–XI + rekapitulasi Rp 756.805.000 (simulasi)")
# Foto AI menggantikan ilustrasi
MAP = [("il-cover", "foto-ai-cover.jpg", "Rencana sekolah darurat (FOTO AI simulasi)"),
       ("il-kondisi", "foto-ai-kondisi.jpg", "Kondisi awal: gedung tertutup abu, siswa di tenda (FOTO AI simulasi)"),
       ("il-p1", "foto-ai-pondasi.jpg", "Progres 18 Nov: pondasi & sloof selesai (FOTO AI simulasi)"),
       ("il-p2", "foto-ai-rangka.jpg", "Progres 24 Nov: kolom & rangka atap baja (FOTO AI simulasi)")]
if not any("foto-ai-cover" in d["url"] for d in wd()):
    for old, new, label in MAP:
        for d in wd():
            if not d.get("kind") and old in d["url"]:
                as_user(PIC, dp.remove_program_file, PROG, "gambar", d["url"])
        up("gambar", new, label)
urls = {k: next((d["url"] for d in wd() if k in d["url"]), None) for k in ("foto-ai-cover", "foto-ai-kondisi", "foto-ai-pondasi", "foto-ai-rangka")}
if urls["foto-ai-cover"] and frappe.db.get_value("RN Donor Program", PROG, "cover_image_url") != urls["foto-ai-cover"]:
    frappe.db.set_value("RN Donor Program", PROG, "cover_image_url", urls["foto-ai-cover"]); done.append("sampul = foto AI")
for ev_key, k, title in [("il-kondisi", "foto-ai-kondisi", "Kondisi awal sekolah & kelas tenda (FOTO AI SIMULASI)"),
                         ("il-p1", "foto-ai-pondasi", "Pondasi & sloof selesai (FOTO AI SIMULASI)"),
                         ("il-p2", "foto-ai-rangka", "Kolom & rangka atap terpasang (FOTO AI SIMULASI)")]:
    n = "evidence-sim-uip-" + ev_key
    if urls[k] and frappe.db.exists("RN Evidence File", n) and frappe.db.get_value("RN Evidence File", n, "file_path") != urls[k]:
        frappe.db.set_value("RN Evidence File", n, {"file_path": urls[k], "filename": urls[k].rsplit("/", 1)[-1], "mime_type": "JPG", "title": title})
        done.append("bukti " + n)
t = frappe.db.get_value("RN Procurement Tender", "pur8kre3or", "design_image_url")
frappe.db.commit()
print("\nUI_FOTO selesai")
for d in done: print("DONE", d)
for f in found: print("TEMUAN", f)
