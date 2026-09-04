import frappe
from frappe.utils import now_datetime

# Seeds the club-membership + HQ-approval flow (api_community_cluster:
# request_membership / org_membership_admin / decide_membership) with demo data
# so the "Keanggotaan Organisasi" panel on koordinasi-organisasi.html is not
# empty. Idempotent: an existing (user_account, organization) membership row is
# left exactly as it is.
#
# Model:
#   owner   = pengelola pusat organisasi (menyetujui & memverifikasi anggota)
#   member  = anggota terdaftar; member_verified=1 -> identitas dikonfirmasi pusat
#   pending = permohonan bergabung yang menunggu keputusan pusat

# organization -> {owner: user_account, members: [(user_account, verified?)], pending: [user_account]}
SEED = {
    "SIM-LR-ORG": {
        "owner": "SIM-LR-USER-LD1",
        "members": [
            ("SIM-LR-USER-LD2", True),
            ("SIM-LR-USER-LD3", False),
            ("SIM-LR-USER-LD4", True),
            ("SIM-LR-USER-LD5", False),
            ("SIM-LR-USER-LD6", False),
        ],
        "pending": ["SIM-VOL-YUSUF", "rn-user-7d4b80109b90babb0d7047f3"],
    },
    "SIM-NS-BNPB": {
        "owner": "SIM-NS-USER-NASKOMANDO",
        "members": [("SIM-NS-USER-BNPB", True)],
        "pending": [],
    },
    "KH-ORG-BPBD": {
        "owner": "KH-USER-KOMANDO",
        "members": [
            ("KH-USER-ALAT", True),
            ("KH-USER-ISPA", False),
            ("KH-USER-SINGGAH", False),
        ],
        "pending": ["KH-USER-GAMBUT"],
    },
}


def _has_membership(user_account, organization):
    return frappe.db.exists(
        "RN Organization Membership",
        {"user_account": user_account, "organization": organization},
    )


def _mk(user_account, organization, role, status, verified=False, approver=None):
    if not frappe.db.exists("RN User Account", user_account):
        return None
    if not frappe.db.exists("RN Organization", organization):
        return None
    if _has_membership(user_account, organization):
        return "skip"

    doc = frappe.new_doc("RN Organization Membership")
    doc.user_account = user_account
    doc.organization = organization
    doc.membership_role = role
    doc.status = status
    doc.requested_at = now_datetime()
    if status == "approved":
        doc.approved_at = now_datetime()
        doc.approved_by = approver or user_account
    if verified:
        doc.member_verified = 1
        doc.verified_at = now_datetime()
    doc.insert(ignore_permissions=True)
    return doc.name


def install_defaults():
    made = 0
    skipped = 0
    for org, cfg in SEED.items():
        owner = cfg.get("owner")
        r = _mk(owner, org, "owner", "approved", verified=True, approver=owner)
        if r == "skip":
            skipped += 1
        elif r:
            made += 1

        for ua, verified in cfg.get("members", []):
            r = _mk(ua, org, "member", "approved", verified=verified, approver=owner)
            if r == "skip":
                skipped += 1
            elif r:
                made += 1

        for ua in cfg.get("pending", []):
            r = _mk(ua, org, "member", "pending")
            if r == "skip":
                skipped += 1
            elif r:
                made += 1

    frappe.db.commit()
    print(f"[membership_defaults] created {made}, skipped {skipped}")
    return {"created": made, "skipped": skipped}
