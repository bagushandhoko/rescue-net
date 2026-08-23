import frappe
from frappe.utils import now_datetime


def _actor():
    if frappe.session.user in ("Guest", "Administrator"):
        frappe.throw("Login diperlukan")

    actor = frappe.db.get_value(
        "RN User Account",
        {"frappe_user": frappe.session.user, "status": "active"},
        [
            "name", "title", "email", "role",
            "requested_role", "role_request_status",
            "organization", "posko"
        ],
        as_dict=True,
    )

    if not actor:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan")

    return actor


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
def create_posko(title, posko_type, address, organization=None):
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

    posko = frappe.new_doc("RN Posko")
    posko.title = title
    posko.posko_type = posko_type
    posko.address = address
    posko.organization = organization
    posko.operational_status = "active"
    posko.verification_status = "self_reported"
    posko.identity_verification_status = "self_reported"
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
