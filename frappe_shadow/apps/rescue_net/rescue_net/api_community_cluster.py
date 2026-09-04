import frappe
from frappe.utils import now_datetime

from rescue_net.access_policy import rn_actor


def _actor():
    return rn_actor()


@frappe.whitelist()
def get_context():
    actor = _actor()

    memberships = frappe.get_all(
        "RN Organization Membership",
        filters={"user_account": actor.name},
        fields=["name","organization","membership_role","status"],
        order_by="creation asc",
        limit_page_length=100,
    )

    assignments = frappe.get_all(
        "RN Posko Assignment",
        filters={"user_account": actor.name},
        fields=["name","posko","assignment_role","status"],
        order_by="creation asc",
        limit_page_length=100,
    )

    return {
        "user": actor,
        "memberships": memberships,
        "assignments": assignments,
    }


@frappe.whitelist()
def list_organizations():
    _actor()
    return frappe.get_all(
        "RN Organization",
        fields=[
            "name","title","organization_type","status",
            "trust_level","verification_status"
        ],
        order_by="title asc",
        limit_page_length=500,
    )


@frappe.whitelist()
def create_organization(title, organization_type="community",
                        contact_person=None, notes=None):
    actor = _actor()

    org = frappe.new_doc("RN Organization")
    org.title = title
    org.organization_type = organization_type
    org.status = "pending"
    org.trust_level = "unverified"
    org.verification_status = "pending"
    org.identity_verification_status = "unverified"
    org.contact_person = contact_person
    org.notes = notes
    org.insert(ignore_permissions=True)

    membership = frappe.new_doc("RN Organization Membership")
    membership.user_account = actor.name
    membership.organization = org.name
    membership.membership_role = "owner"
    membership.status = "approved"
    membership.requested_at = now_datetime()
    membership.approved_at = now_datetime()
    membership.approved_by = actor.name
    membership.insert(ignore_permissions=True)


    return {
        "organization": org.name,
        "membership": membership.name,
        "status": org.status,
        "trust_level": org.trust_level,
    }


@frappe.whitelist()
def request_membership(organization):
    actor = _actor()

    existing = frappe.db.get_value(
        "RN Organization Membership",
        {"user_account": actor.name, "organization": organization},
        ["name","status"],
        as_dict=True,
    )

    if existing:
        return existing

    membership = frappe.new_doc("RN Organization Membership")
    membership.user_account = actor.name
    membership.organization = organization
    membership.membership_role = "member"
    membership.status = "pending"
    membership.requested_at = now_datetime()
    membership.insert(ignore_permissions=True)

    return {"name": membership.name, "status": membership.status}


# ============================================================
# Club membership + HQ (pusat) approval — an org's owner/admin reviews join
# requests and can attest that the member's identity is real ("diverifikasi
# oleh pusatnya"). Approved membership by a credible org = the member carries
# that org's trust.
# ============================================================

def _owns_org(actor, organization):
    from rescue_net.access_policy import can_manage_organization
    return bool(actor and organization and can_manage_organization(actor, organization))


def _owned_org_names(actor):
    if not actor or not actor.get("name"):
        return []
    rows = frappe.get_all(
        "RN Organization Membership",
        filters={"user_account": actor.name, "membership_role": "owner",
                 "status": "approved"},
        fields=["organization"], limit_page_length=200,
    )
    return sorted({r.organization for r in rows if r.organization})


@frappe.whitelist()
def org_membership_admin(organization=None):
    """Join-request + member roster for the org(s) the caller owns."""
    actor = _actor()
    from rescue_net.access_policy import is_system_manager

    if organization:
        if not (is_system_manager() or _owns_org(actor, organization)):
            frappe.throw("Anda bukan pengelola organisasi ini", frappe.PermissionError)
        orgs = [organization]
    else:
        orgs = _owned_org_names(actor)

    if not orgs:
        return {"is_org_admin": False, "organizations": [], "memberships": []}

    rows = frappe.get_all(
        "RN Organization Membership",
        filters={"organization": ["in", orgs]},
        fields=["name", "user_account", "organization", "membership_role",
                "status", "member_verified", "requested_at", "approved_at",
                "approved_by", "verified_at", "decision_note"],
        order_by="requested_at desc, creation desc",
        limit_page_length=1000,
    )

    uids = sorted({r.user_account for r in rows if r.user_account})
    udet = {}
    if uids:
        for u in frappe.get_all(
            "RN User Account", filters={"name": ["in", uids]},
            fields=["name", "username", "email", "phone", "role", "organization"],
            limit_page_length=len(uids),
        ):
            udet[u.name] = u

    org_titles = {o.name: o.title for o in frappe.get_all(
        "RN Organization", filters={"name": ["in", orgs]},
        fields=["name", "title"], limit_page_length=len(orgs))}

    out = []
    for r in rows:
        u = udet.get(r.user_account) or {}
        out.append({
            "name": r.name,
            "user_account": r.user_account,
            "user_name": (u.get("username") or r.user_account),
            "user_email": u.get("email"),
            "user_phone": u.get("phone"),
            "user_role": u.get("role"),
            "organization": r.organization,
            "organization_title": org_titles.get(r.organization, r.organization),
            "membership_role": r.membership_role,
            "status": r.status,
            "member_verified": bool(r.member_verified),
            "requested_at": r.requested_at,
            "approved_at": r.approved_at,
            "verified_at": r.verified_at,
            "decision_note": r.decision_note,
        })

    return {
        "is_org_admin": True,
        "organizations": [{"name": n, "title": org_titles.get(n, n)} for n in orgs],
        "memberships": out,
        "pending_count": sum(1 for m in out if m["status"] == "pending"),
        "member_count": sum(1 for m in out if m["status"] == "approved"),
    }


@frappe.whitelist()
def decide_membership(membership, action, member_verified=None, note=None):
    """Org owner approves / rejects a join request, and may attest that the
    member's identity is verified by the club HQ."""
    actor = _actor()
    from rescue_net.access_policy import is_system_manager

    doc = frappe.get_doc("RN Organization Membership", membership)

    if not (is_system_manager() or _owns_org(actor, doc.organization)):
        frappe.throw("Anda bukan pengelola organisasi ini", frappe.PermissionError)

    action = str(action or "").strip().lower()
    if action not in ("approve", "reject", "revoke"):
        frappe.throw("Aksi tidak valid (approve/reject/revoke)")

    if doc.membership_role == "owner" and action in ("reject", "revoke"):
        frappe.throw("Owner organisasi tidak bisa ditolak/dicabut di sini")

    if action == "approve":
        doc.status = "approved"
        doc.approved_at = now_datetime()
        doc.approved_by = actor.name
    elif action == "reject":
        doc.status = "rejected"
    else:  # revoke
        doc.status = "revoked"

    want_verified = str(member_verified).lower() in ("1", "true", "yes") if member_verified is not None else None
    if action == "approve" and want_verified:
        doc.member_verified = 1
        doc.verified_at = now_datetime()
    elif action in ("reject", "revoke"):
        doc.member_verified = 0
        doc.verified_at = None

    if note is not None:
        doc.decision_note = str(note)[:500]

    doc.save(ignore_permissions=True)

    return {
        "membership": doc.name,
        "status": doc.status,
        "member_verified": bool(doc.member_verified),
    }


@frappe.whitelist()
def set_member_verified(membership, verified=1):
    """Toggle the HQ identity attestation on an already-approved member."""
    actor = _actor()
    from rescue_net.access_policy import is_system_manager

    doc = frappe.get_doc("RN Organization Membership", membership)
    if not (is_system_manager() or _owns_org(actor, doc.organization)):
        frappe.throw("Anda bukan pengelola organisasi ini", frappe.PermissionError)
    if doc.status != "approved":
        frappe.throw("Hanya anggota yang sudah disetujui yang bisa diverifikasi")

    on = str(verified).lower() in ("1", "true", "yes")
    doc.member_verified = 1 if on else 0
    doc.verified_at = now_datetime() if on else None
    doc.save(ignore_permissions=True)
    return {"membership": doc.name, "member_verified": bool(doc.member_verified)}


@frappe.whitelist()
def my_memberships():
    """The caller's own club memberships + which orgs they can still join."""
    actor = _actor()

    mine = frappe.get_all(
        "RN Organization Membership",
        filters={"user_account": actor.name},
        fields=["name", "organization", "membership_role", "status",
                "member_verified", "requested_at", "approved_at"],
        order_by="creation desc", limit_page_length=200,
    )
    org_names = sorted({m.organization for m in mine if m.organization})
    otitle = {}
    overif = {}
    if org_names:
        for o in frappe.get_all(
            "RN Organization", filters={"name": ["in", org_names]},
            fields=["name", "title", "verification_status", "trust_level"],
            limit_page_length=len(org_names),
        ):
            otitle[o.name] = o.title
            overif[o.name] = {"verification_status": o.verification_status,
                              "trust_level": o.trust_level}

    for m in mine:
        m["organization_title"] = otitle.get(m.organization, m.organization)
        m["organization_trust"] = overif.get(m.organization, {})
        m["member_verified"] = bool(m.member_verified)

    return {
        "user_account": actor.name,
        "memberships": mine,
        "verified_member_of": [
            m["organization_title"] for m in mine
            if m["status"] == "approved" and m["member_verified"]
        ],
    }


@frappe.whitelist()
def list_poskos():
    _actor()
    return frappe.get_all(
        "RN Posko",
        fields=[
            "name","title","organization","posko_type",
            "address","operational_status","verification_status"
        ],
        order_by="title asc",
        limit_page_length=500,
    )


@frappe.whitelist()
def create_posko(
    title, posko_type, address, organization=None,
    disaster_event=None, latitude=None, longitude=None,
    officer_in_charge_name=None, officer_in_charge_role=None,
    officer_in_charge_phone=None, officer_in_charge_email=None,
    emergency_contact=None, facilities=None, rn_beneficiary_count=None,
    public_detail=None,
):
    """Also backs the "Registrasi & Verifikasi Posko" mock-up's form — the
    extra kwargs are all optional so existing callers (Organisasi & Posko's
    simpler "Tambah Posko" form) keep working unchanged.
    """
    actor = _actor()

    if organization:
        approved = (
            actor.organization == organization
            or frappe.db.exists(
                "RN Organization Membership",
                {
                    "user_account": actor.name,
                    "organization": organization,
                    "status": "approved",
                },
            )
        )

        if not approved:
            frappe.throw(
                "Posko hanya dapat dikaitkan dengan Kelompok "
                "yang sudah Anda ikuti"
            )

    from rescue_net.reference_resolver import resolve_disaster_event

    posko = frappe.new_doc("RN Posko")
    posko.title = title
    posko.posko_type = posko_type
    posko.address = address
    posko.organization = organization
    posko.disaster_event = resolve_disaster_event(disaster_event) if disaster_event else None
    posko.operational_status = "active"
    posko.verification_status = "self_reported"
    posko.identity_verification_status = "self_reported"

    if latitude not in (None, ""):
        posko.latitude = float(latitude)
    if longitude not in (None, ""):
        posko.longitude = float(longitude)

    posko.officer_in_charge_name = officer_in_charge_name
    posko.officer_in_charge_role = officer_in_charge_role
    posko.officer_in_charge_phone = officer_in_charge_phone
    posko.officer_in_charge_email = officer_in_charge_email
    posko.emergency_contact = emergency_contact
    posko.facilities = facilities

    if rn_beneficiary_count not in (None, ""):
        posko.rn_beneficiary_count = int(rn_beneficiary_count)

    if public_detail in ("inherit", "private", "public"):
        posko.public_detail = public_detail

    posko.insert(ignore_permissions=True)

    assignment = frappe.new_doc("RN Posko Assignment")
    assignment.user_account = actor.name
    assignment.posko = posko.name
    assignment.assignment_role = actor.role or "member"

    # Membuat Posko tidak menaikkan role.
    assignment.status = (
        "approved" if actor.role == "posko_operator" else "pending"
    )

    assignment.insert(ignore_permissions=True)

    return {
        "posko": posko.name,
        "verification_status": posko.verification_status,
        "assignment_status": assignment.status,
    }


def _can_edit_posko(actor, posko_doc):
    from rescue_net.access_policy import can_manage_posko, is_system_manager
    return bool(
        is_system_manager()
        or can_manage_posko(actor, posko_doc.name)
        or posko_doc.owner == frappe.session.user
    )


@frappe.whitelist()
def update_posko(
    posko, title=None, posko_type=None, address=None, latitude=None, longitude=None,
    officer_in_charge_name=None, officer_in_charge_role=None,
    officer_in_charge_phone=None, officer_in_charge_email=None,
    emergency_contact=None, facilities=None, rn_beneficiary_count=None,
    public_detail=None,
):
    actor = _actor()
    doc = frappe.get_doc("RN Posko", posko)

    if not _can_edit_posko(actor, doc):
        frappe.throw("Akses edit posko ditolak", frappe.PermissionError)

    for field, value in (
        ("title", title), ("posko_type", posko_type), ("address", address),
        ("officer_in_charge_name", officer_in_charge_name),
        ("officer_in_charge_role", officer_in_charge_role),
        ("officer_in_charge_phone", officer_in_charge_phone),
        ("officer_in_charge_email", officer_in_charge_email),
        ("emergency_contact", emergency_contact),
        ("facilities", facilities),
    ):
        if value is not None:
            setattr(doc, field, value)

    if latitude not in (None, ""):
        doc.latitude = float(latitude)
    if longitude not in (None, ""):
        doc.longitude = float(longitude)
    if rn_beneficiary_count not in (None, ""):
        doc.rn_beneficiary_count = int(rn_beneficiary_count)
    if public_detail in ("inherit", "private", "public"):
        doc.public_detail = public_detail

    doc.save(ignore_permissions=True)

    return {"posko": doc.name, "modified": doc.modified}


@frappe.whitelist()
def submit_posko_verification(posko):
    """"Ajukan Verifikasi" — moves a posko from self_reported/needs_correction
    into the pending queue Verification & Approval's Posko tab reads."""
    actor = _actor()
    doc = frappe.get_doc("RN Posko", posko)

    if not _can_edit_posko(actor, doc):
        frappe.throw("Akses posko ditolak", frappe.PermissionError)

    if doc.verification_status not in ("self_reported", "needs_correction", None, ""):
        frappe.throw("Posko ini sudah diajukan / sudah diverifikasi")

    doc.verification_status = "pending"
    doc.save(ignore_permissions=True)

    return {"posko": doc.name, "verification_status": doc.verification_status}


@frappe.whitelist()
def delete_posko(posko):
    """Real delete, but only when safe: refuses if any operational record
    still references this posko (needs/stock/flows/occupancy/...), so a
    click can't silently orphan data. Mark it offline instead if it has
    history worth keeping."""
    from rescue_net.access_policy import is_system_manager

    actor = _actor()
    doc = frappe.get_doc("RN Posko", posko)

    if not (is_system_manager() or doc.owner == frappe.session.user):
        frappe.throw("Hanya pembuat posko atau System Manager yang dapat menghapus", frappe.PermissionError)

    linked_checks = [
        ("RN Logistic Need", {"posko": posko}),
        ("RN Stock Observation", {"posko": posko}),
        ("RN Distribution Flow", {"source_posko": posko}),
        ("RN Distribution Flow", {"destination_posko": posko}),
        ("RN Shelter Occupancy", {"posko": posko}),
        ("RN Kitchen Production", {"posko": posko}),
        ("RN Volunteer Assignment", {"posko": posko}),
        ("RN Posko Assignment", {"posko": posko}),
    ]
    for doctype, filters in linked_checks:
        if frappe.db.exists(doctype, filters):
            frappe.throw(
                f"Posko ini sudah punya data operasional ({doctype}) — "
                "tidak bisa dihapus. Ubah status jadi 'offline' sebagai gantinya."
            )

    frappe.delete_doc("RN Posko", posko, ignore_permissions=True)
    return {"posko": posko, "deleted": True}


@frappe.whitelist()
def list_needs():
    _actor()

    return frappe.get_all(
        "RN Community Need",
        fields=[
            "name","title","source_report","requester_user",
            "community_owner","verification_status",
            "urgency","status","handling_mode",
            "handling_posko","takeover_status"
        ],
        order_by="creation desc",
        limit_page_length=200,
    )
