import frappe
from frappe.utils import now_datetime

# Seeds the external-verifier network (api_verifier) so the verifikator.html
# surface + posko credibility badges are not empty. Idempotent: a verifier
# profile with the same `title` or a pending request for the same posko is left
# as it is. Simulation figures only ([SIMULASI] context) — not real officials.

VERIFIERS = [
    {
        "title": "[SIMULASI] Keuchik Gampong - Kec. Johan Pahlawan",
        "verifier_type": "government",
        "position_title": "Keuchik (Kepala Desa)",
        "public_role_description": "Kepala pemerintahan gampong; memverifikasi keberadaan & aktivitas posko warga di wilayahnya.",
        "wilayah": "Johan Pahlawan, Aceh Barat",
        "trust_level": 2,
        "verifier_status": "active",
        "user": "rn-user-882e42b193c522caa04881a2",
    },
    {
        "title": "[SIMULASI] Kapolsek Kaway XVI",
        "verifier_type": "government",
        "position_title": "Kapolsek",
        "public_role_description": "Kepolisian setempat; memverifikasi posko lewat kunjungan langsung.",
        "wilayah": "Kaway XVI, Aceh Barat",
        "trust_level": 2,
        "verifier_status": "active",
    },
    {
        "title": "[SIMULASI] Tgk. Imam Masjid - Meulaboh",
        "verifier_type": "religious_leader",
        "position_title": "Imam Masjid / Tokoh Masyarakat",
        "public_role_description": "Tokoh masyarakat yang bersedia menjadi verifikator relawan & posko.",
        "wilayah": "Meulaboh, Aceh Barat",
        "trust_level": 1,
        "verifier_status": "active",
    },
    {
        "title": "[SIMULASI] Ketua Karang Taruna Samatiga",
        "verifier_type": "community_leader",
        "position_title": "Ketua Karang Taruna",
        "public_role_description": "Diajukan lewat rekomendasi Keuchik (member-get-member).",
        "wilayah": "Samatiga, Aceh Barat",
        "trust_level": 0,
        "verifier_status": "pending",
        "user": "SIM-VOL-YUSUF",
        "sponsor_title": "[SIMULASI] Keuchik Gampong - Kec. Johan Pahlawan",
    },
]

# posko -> {verifier_title | None (open), method}
REQUESTS = [
    {"posko": "SIM-NS-POSKO-WARGA", "verifier_title": "[SIMULASI] Keuchik Gampong - Kec. Johan Pahlawan",
     "method": "site_visit", "wilayah": "Johan Pahlawan, Aceh Barat",
     "note": "Mohon verifikasi posko logistik warga di Gedung Serbaguna."},
    {"posko": "SIM-NS-POSKO-PELAJAR", "verifier_title": None,
     "method": "network_vouch", "wilayah": "Kaway XVI, Aceh Barat",
     "note": "Posko motor pelajar last-mile; minta endorsement verifikator wilayah Kaway XVI."},
]


def _get_verifier_by_title(title):
    return frappe.db.get_value("RN Verifier Profile", {"title": title}, "name")


def _mk_verifier(cfg):
    if _get_verifier_by_title(cfg["title"]):
        return "skip"
    user = cfg.get("user")
    if user and not frappe.db.exists("RN User Account", user):
        user = None
    if user and frappe.db.exists("RN Verifier Profile", {"user": user}):
        user = None  # that account is already a verifier
    doc = frappe.new_doc("RN Verifier Profile")
    doc.title = cfg["title"]
    doc.verifier_type = cfg["verifier_type"]
    doc.position_title = cfg.get("position_title")
    doc.public_role_description = cfg.get("public_role_description")
    doc.wilayah = cfg["wilayah"]
    doc.trust_level = cfg.get("trust_level", 0)
    doc.verifier_status = cfg.get("verifier_status", "pending")
    doc.user = user
    sp = cfg.get("sponsor_title")
    if sp:
        doc.sponsor_verifier = _get_verifier_by_title(sp)
    if doc.verifier_status == "active":
        doc.approved_by = "membership_defaults"
        doc.approved_at = now_datetime()
    doc.insert(ignore_permissions=True)
    return doc.name


def _mk_request(cfg):
    posko = cfg["posko"]
    if not frappe.db.exists("RN Posko", posko):
        return "skip"
    if frappe.db.exists("RN Verification Request",
                        {"object_type": "posko", "object_id": posko,
                         "status": ["in", ["pending", "accepted"]]}):
        return "skip"
    verifier = _get_verifier_by_title(cfg["verifier_title"]) if cfg.get("verifier_title") else None
    doc = frappe.new_doc("RN Verification Request")
    title_posko = frappe.db.get_value("RN Posko", posko, "title") or posko
    doc.title = f"Verifikasi: {title_posko}"[:140]
    doc.object_type = "posko"
    doc.object_id = posko
    doc.verifier = verifier
    doc.method = cfg.get("method", "site_visit")
    doc.wilayah = cfg.get("wilayah")
    doc.status = "pending"
    doc.notes = cfg.get("note")
    doc.insert(ignore_permissions=True)
    return doc.name


def install_defaults():
    if not frappe.db.exists("DocType", "RN Verifier Profile"):
        print("[verifier_defaults] doctypes not migrated yet — skip")
        return {"created": 0, "skipped": 0}

    made = skipped = 0
    for cfg in VERIFIERS:
        r = _mk_verifier(cfg)
        skipped += 1 if r == "skip" else 0
        made += 1 if r not in ("skip", None) else 0
    for cfg in REQUESTS:
        r = _mk_request(cfg)
        skipped += 1 if r == "skip" else 0
        made += 1 if r not in ("skip", None) else 0

    frappe.db.commit()
    print(f"[verifier_defaults] created {made}, skipped {skipped}")
    return {"created": made, "skipped": skipped}
