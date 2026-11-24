"""Lengkapi AKUN DEMO agar mewakili semua jenis pengguna (owner 24 Nov 2026). Idempoten. Sandi demo = Demo12345
(sama dengan akun demo lain, sudah publik di halaman login). Semua akun hanya terhubung ke data [SIMULASI].
TIDAK membuat akun Control Centre / System Manager (peran itu berlaku juga untuk bencana riil).
Jalankan di bench console: exec(open(path).read(), {"__name__": "rn"})."""
import frappe
from frappe.utils import now_datetime

PW = "Demo12345"
EV = "disaster_events:event-sim-001"
out = []


def account(email, title, role, phone):
    if not frappe.db.exists("User", email):
        u = frappe.get_doc({"doctype": "User", "email": email, "first_name": title[:60], "user_type": "Website User",
                            "send_welcome_email": 0, "enabled": 1})
        u.flags.ignore_permissions = True
        u.insert()
        out.append("user baru " + email)
    from frappe.utils.password import update_password
    update_password(email, PW)
    acc = frappe.db.get_value("RN User Account", {"frappe_user": email})
    if not acc:
        d = frappe.get_doc({"doctype": "RN User Account", "title": title, "frappe_user": email, "email": email,
                            "role": role, "status": "active", "phone": phone, "privacy_consent_at": now_datetime()})
        d.insert(ignore_permissions=True)
        acc = d.name
        out.append("akun RN baru %s (%s)" % (email, role))
    return acc


def assign(acc, posko, arole="operator"):
    if not frappe.db.exists("RN Posko Assignment", {"user_account": acc, "posko": posko}):
        frappe.get_doc({"doctype": "RN Posko Assignment", "user_account": acc, "posko": posko,
                        "assignment_role": arole, "status": "approved"}).insert(ignore_permissions=True)
        out.append("tugas %s -> %s" % (acc, posko))
    else:
        frappe.db.set_value("RN Posko Assignment", {"user_account": acc, "posko": posko}, "status", "approved")


def member(acc, org, mrole):
    n = frappe.db.get_value("RN Organization Membership", {"user_account": acc, "organization": org})
    if n:
        frappe.db.set_value("RN Organization Membership", n, {"membership_role": mrole, "status": "approved"})
    else:
        frappe.get_doc({"doctype": "RN Organization Membership", "user_account": acc, "organization": org,
                        "membership_role": mrole, "status": "approved"}).insert(ignore_permissions=True)
        out.append("anggota %s %s %s" % (acc, org, mrole))


# 1) Akun Landrover di halaman login yang belum terhubung ke poskonya
for i in range(2, 7):
    acc = frappe.db.get_value("RN User Account", {"frappe_user": "ld%d.demo@rescue-net.local" % i})
    if acc and frappe.db.exists("RN Posko", "SIM-LR-POSKO-LD%d" % i):
        assign(acc, "SIM-LR-POSKO-LD%d" % i)

# 2) Peran yang belum terwakili
ORG = "SIM-LR-ORG"   # Komunitas Landrover (pemilik: ld1.demo)
wakil = account("wakil.demo@rescue-net.local", "[SIMULASI] Wakil Ketua Komunitas Landrover", "community_coordinator", "081200009001")
member(wakil, ORG, "deputy")
staf = account("staf.demo@rescue-net.local", "[SIMULASI] Staf Admin Komunitas Landrover", "posko_operator", "081200009002")
member(staf, ORG, "staff")

ver = account("verifikator.demo@rescue-net.local", "[SIMULASI] Keuchik Gampong (Verifikator)", "viewer", "081200009003")
if not frappe.db.exists("RN Verifier Profile", {"user": ver}):
    frappe.get_doc({"doctype": "RN Verifier Profile", "title": "[SIMULASI] Keuchik Gampong Drien Rampak", "user": ver,
                    "verifier_type": "community_leader", "position_title": "Keuchik (kepala desa) - SIMULASI",
                    "public_role_description": "Verifikator wilayah contoh untuk latihan", "wilayah": "Aceh Barat",
                    "phone": "081200009003", "email": "verifikator.demo@rescue-net.local", "verifier_status": "active",
                    "approved_at": now_datetime(), "notes": "Akun demo SIMULASI"}).insert(ignore_permissions=True)
    out.append("profil verifikator")

rel = account("relawan.demo@rescue-net.local", "[SIMULASI] Relawan Perorangan Demo", "volunteer", "081200009004")
if not frappe.db.exists("RN Volunteer Profile", {"user_account": rel}):
    frappe.get_doc({"doctype": "RN Volunteer Profile", "user_account": rel, "disaster_event": EV,
                    "volunteer_name": "[SIMULASI] Relawan Perorangan Demo", "contact": "081200009004",
                    "main_skill": "Logistik & distribusi", "skill_tags": "logistik, mengemudi, P3K",
                    "availability_status": "available", "current_location": "Meulaboh", "notes": "Akun demo SIMULASI"}
                   ).insert(ignore_permissions=True)
    out.append("profil relawan")

account("pelapor.demo@rescue-net.local", "[SIMULASI] Pelapor Terverifikasi Demo", "verified_reporter", "081200009005")
account("vendor.demo@rescue-net.local", "[SIMULASI] CV Bangun Bersama (penyedia tender)", "viewer", "081200009006")

# Pemrakarsa perorangan program Baduy (terverifikasi lewat referensi yang sudah dikonfirmasi)
bd = account("baduy.demo@rescue-net.local", "[SIMULASI] Relawan Perorangan Pemrakarsa Rumah Baduy", "donor", "081200009007")
if not frappe.db.exists("RN User Reference", {"user_account": bd, "status": "confirmed"}):
    frappe.get_doc({"doctype": "RN User Reference", "user_account": bd, "reference_name": "[SIMULASI] Jaro (tokoh adat) contoh",
                    "reference_relation": "tokoh masyarakat", "reference_contact": "081200009099", "status": "confirmed",
                    "notes": "Referensi contoh SIMULASI", "decided_at": now_datetime()}).insert(ignore_permissions=True)
    out.append("referensi pemrakarsa dikonfirmasi")

frappe.db.commit()
print(); print("AKUN_DEMO", len(out))
for o in out: print("  ", o)
