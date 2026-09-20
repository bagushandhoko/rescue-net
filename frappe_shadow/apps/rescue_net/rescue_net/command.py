"""Komando terpusat — an OPTIONAL coordination scheme for organisations.

`RN Organization.coordination_scheme` is `mandiri` (default: every posko /
member runs itself — the behaviour before this module existed) or `terpusat`
(an organisation whose poskos are under a central command, e.g. a TNI unit).
The choice is made when the centre first registers its organisation
(`api_community_cluster.create_organization`); afterwards only a System Manager
can change it, so an existing organisation cannot be turned into a command
organisation by its members.

Under a `terpusat` organisation (the "pusat") and every organisation attached
below it (`RN Organization.parent_organization`):

  * the pusat's OWNER is the super admin of the whole command tree — they manage
    every organisation and posko in it;
  * posko accounts are CREATED BY the pusat (`api_command.create_command_account`);
    people cannot self-join those organisations / poskos;
  * lower levels keep running their poskos, but structural changes (add a posko,
    change a posko's identity/location/functions, add an account) are not applied
    directly: they become an `RN Command Change Request` that the pusat approves,
    and only then are applied.

Everything here is a no-op for organisations that are not under a `terpusat`
organisation, so `mandiri` behaviour is unchanged.
"""

import json

import frappe
from frappe.utils import now_datetime

MANDIRI = "mandiri"
TERPUSAT = "terpusat"
SCHEMES = (MANDIRI, TERPUSAT)

# Posko fields a posko-level user may NOT change directly under a command
# organisation (identity / location / visibility / schedule). Operational
# fields (status, notes, beneficiaries, contact, facilities, WhatsApp notify)
# stay directly editable — "posko tinggal menjalankan fungsinya".
STRUCTURAL_POSKO_FIELDS = (
    "title", "posko_type", "address", "latitude", "longitude",
    "public_detail", "active_from", "active_until",
)

ACCOUNT_ROLES = (
    "posko_operator", "medical_operator", "shelter_operator", "community_coordinator",
)

REQUEST_ACTIONS = ("create_posko", "update_posko", "set_posko_functions", "create_account")


def scheme_of(org):
    if not org:
        return MANDIRI
    return frappe.db.get_value("RN Organization", org, "coordination_scheme") or MANDIRI


def command_chain(org):
    """Terpusat organisations at or above `org`, nearest first (cycle-safe).
    Empty list = `org` is not under any command."""
    chain, seen, cur = [], set(), org
    while cur and cur not in seen:
        seen.add(cur)
        if scheme_of(cur) == TERPUSAT:
            chain.append(cur)
        cur = frappe.db.get_value("RN Organization", cur, "parent_organization")
    return chain


def command_center_of(org):
    """The nearest pusat over `org` (or None)."""
    chain = command_chain(org)
    return chain[0] if chain else None


def command_tree(center):
    """Every organisation at or below `center` (cycle-safe)."""
    seen, stack = set(), [center]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(frappe.get_all(
            "RN Organization", filters={"parent_organization": cur},
            pluck="name", limit_page_length=500,
        ))
    return seen


def _is_system_manager():
    from rescue_net.access_policy import is_system_manager
    return is_system_manager()


def is_command_owner(actor, org):
    """True when `actor` is an approved OWNER of a pusat that commands `org`
    (or of `org` itself when it is a pusat) — or a System Manager — and `org`
    is under a command. Never true for `mandiri` organisations."""
    chain = command_chain(org)
    if not chain:
        return False
    if _is_system_manager():
        return True
    if not actor or not actor.get("name"):
        return False
    return bool(frappe.db.exists(
        "RN Organization Membership",
        {
            "user_account": actor.name,
            "organization": ["in", chain],
            "membership_role": "owner",
            "status": "approved",
        },
    ))


def needs_approval(actor, org):
    """True when `org` is under a command and `actor` is NOT its command owner
    — i.e. a structural change must go through the pusat."""
    return bool(command_chain(org)) and not is_command_owner(actor, org)


def is_bypassed():
    """Set only while the pusat is APPLYING an approved request server-side."""
    return bool(frappe.flags.get("command_bypass"))


def posko_org(posko):
    return frappe.db.get_value("RN Posko", posko, "organization") if posko else None


def is_command_owner_of_posko(actor, posko):
    org = posko_org(posko)
    return bool(org) and is_command_owner(actor, org)


def is_account_member(actor, org):
    """Approved member of `org` (any role) — used so an outsider can't even file a request."""
    if not actor or not actor.get("name") or not org:
        return False
    from rescue_net.access_policy import approved_member
    return approved_member(actor.name, org) or actor.get("organization") == org


# --------------------------------------------------------------------
# Change requests
# --------------------------------------------------------------------

def file_request(actor, org, action, payload, summary, target_posko=None):
    """Park a structural change for the pusat. Returns the response dict the
    gated endpoint hands back instead of applying the change."""
    if action not in REQUEST_ACTIONS:
        frappe.throw("Jenis permintaan komando tidak dikenal.")
    center = command_center_of(org)
    if not center:
        frappe.throw("Organisasi ini tidak berada di bawah komando terpusat.")

    doc = frappe.new_doc("RN Command Change Request")
    doc.command_organization = center
    doc.organization = org
    doc.action = action
    doc.target_posko = target_posko
    doc.summary = (summary or "")[:140]
    doc.payload = json.dumps(payload, ensure_ascii=False, default=str)
    doc.status = "pending"
    doc.requested_by = actor.name if actor and actor.get("name") else None
    doc.requested_at = now_datetime()
    doc.insert(ignore_permissions=True)

    return {
        "pending": True,
        "command_request": doc.name,
        "command_organization": center,
        "message": "Perubahan ini memerlukan persetujuan pusat komando dan sudah diajukan.",
    }


def generate_password():
    """Temporary password that always satisfies api_auth._check_password_strength."""
    import secrets
    alphabet = "abcdefghjkmnpqrstuvwxyz"
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    pw = [secrets.choice(upper), secrets.choice(digits)] + [secrets.choice(alphabet + upper + digits) for _ in range(8)]
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)


def create_account(organization, full_name, email, posko=None, role="posko_operator",
                   phone=None, username=None, password=None):
    """Create a ready-to-use posko account: Frappe user + active RN User Account
    + approved Organization Membership (+ approved Posko Assignment when a
    posko is given). Caller MUST already have authorised this (pusat owner, or
    an approved request). Returns {user_account, email, temporary_password}."""
    import re
    from rescue_net.api_auth import _check_password_strength

    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    role = (role or "posko_operator").strip()
    if not full_name or not email:
        frappe.throw("Nama lengkap dan email wajib diisi.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        frappe.throw("Format email tidak valid.")
    if role not in ACCOUNT_ROLES:
        frappe.throw("Peran akun tidak valid.")
    if not frappe.db.exists("RN Organization", organization):
        frappe.throw("Organisasi tidak ditemukan.")
    if posko:
        if posko_org(posko) != organization:
            frappe.throw("Posko tersebut bukan milik organisasi ini.")
    elif role != "community_coordinator":
        frappe.throw("Akun operator harus ditempatkan pada satu posko.")
    if frappe.db.exists("User", email):
        frappe.throw("Email sudah terdaftar sebagai pengguna.")

    temporary = None
    if (password or "").strip():
        _check_password_strength(password)
    else:
        password = temporary = generate_password()

    parts = full_name.split(" ", 1)
    user = frappe.get_doc({
        "doctype": "User", "email": email, "first_name": parts[0],
        "last_name": parts[1] if len(parts) > 1 else "",
        "mobile_no": (phone or "").strip() or None,
        "send_welcome_email": 0, "user_type": "Website User", "new_password": password,
    })
    user.flags.ignore_permissions = True
    user.insert(ignore_permissions=True)

    account = frappe.get_doc({
        "doctype": "RN User Account", "frappe_user": user.name, "title": full_name,
        "username": (username or "").strip() or email.split("@")[0], "email": email,
        "phone": (phone or "").strip() or None,
        "role": role, "requested_role": "", "role_request_status": "approved",
        "organization": organization, "posko": posko or None, "status": "active",
        "consent_verification": 0,
    })
    account.flags.ignore_permissions = True
    account.insert(ignore_permissions=True)

    membership = frappe.new_doc("RN Organization Membership")
    membership.user_account = account.name
    membership.organization = organization
    membership.membership_role = "member"
    membership.status = "approved"
    membership.requested_at = membership.approved_at = now_datetime()
    membership.decision_note = "Akun dibuat oleh pusat komando."
    membership.insert(ignore_permissions=True)

    if posko:
        assignment = frappe.new_doc("RN Posko Assignment")
        assignment.user_account = account.name
        assignment.posko = posko
        assignment.assignment_role = role
        assignment.status = "approved"
        assignment.insert(ignore_permissions=True)

    return {"user_account": account.name, "email": email, "temporary_password": temporary}
