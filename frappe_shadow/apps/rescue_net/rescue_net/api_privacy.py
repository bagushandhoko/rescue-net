import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    public_posko_allowed,
    rn_actor,
)


@frappe.whitelist()
def dashboard():
    actor = rn_actor()

    if actor.role == "system_manager":
        orgs = frappe.get_all(
            "RN Organization",
            fields=[
                "name", "title", "privacy_mode",
                "allow_posko_public_choice",
                "control_centre_share",
                "public_activity_summary",
            ],
            limit_page_length=500,
        )

        poskos = frappe.get_all(
            "RN Posko",
            fields=[
                "name", "title", "organization",
                "public_detail", "public_participation",
                "accept_volunteers", "accept_goods",
                "accept_donations", "accept_partners",
                "public_service_access",
            ],
            limit_page_length=500,
        )

        return {
            "organizations": orgs,
            "poskos": poskos,
        }

    owner_memberships = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "membership_role": "owner",
            "status": "approved",
        },
        pluck="organization",
        limit_page_length=100,
    )

    assignments = frappe.get_all(
        "RN Posko Assignment",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="posko",
        limit_page_length=100,
    )

    orgs = []
    if owner_memberships:
        orgs = frappe.get_all(
            "RN Organization",
            filters={
                "name": ["in", owner_memberships]
            },
            fields=[
                "name", "title", "privacy_mode",
                "allow_posko_public_choice",
                "control_centre_share",
                "public_activity_summary",
            ],
            limit_page_length=100,
        )

    poskos = []
    if assignments:
        poskos = frappe.get_all(
            "RN Posko",
            filters={
                "name": ["in", assignments]
            },
            fields=[
                "name", "title", "organization",
                "public_detail", "public_participation",
                "accept_volunteers", "accept_goods",
                "accept_donations", "accept_partners",
                "public_service_access",
            ],
            limit_page_length=100,
        )

    return {
        "organizations": orgs,
        "poskos": poskos,
    }


@frappe.whitelist()
def update_organization(
    organization,
    privacy_mode,
    allow_posko_public_choice=0,
    control_centre_share="aggregate",
    public_activity_summary=0,
):
    actor = rn_actor()

    if not can_manage_organization(
        actor,
        organization,
    ):
        frappe.throw(
            "Anda tidak dapat mengubah kebijakan Kelompok ini",
            frappe.PermissionError,
        )

    if privacy_mode not in ("closed", "open"):
        frappe.throw("Privacy mode tidak valid")

    if control_centre_share not in (
        "aggregate",
        "full_authorized",
    ):
        frappe.throw(
            "Control Centre share tidak valid"
        )

    doc = frappe.get_doc(
        "RN Organization",
        organization,
    )

    doc.privacy_mode = privacy_mode
    doc.control_centre_share = control_centre_share
    doc.public_activity_summary = cint(
        public_activity_summary
    )
    # allow_posko_public_choice is independent of privacy_mode: a closed org may
    # still permit specific poskos to be public (see rn_organization.on_update).
    doc.allow_posko_public_choice = cint(
        allow_posko_public_choice
    )

    doc.save(ignore_permissions=True)

    return {
        "organization": doc.name,
        "privacy_mode": doc.privacy_mode,
        "allow_posko_public_choice": (
            doc.allow_posko_public_choice
        ),
        "control_centre_share": (
            doc.control_centre_share
        ),
        "public_activity_summary": (
            doc.public_activity_summary
        ),
    }


@frappe.whitelist()
def set_org_visibility(organization, open_to_public):
    """One-click Terbuka/Tertutup switch for the org-admin console.

    `open_to_public` truthy -> privacy_mode="open",   control_centre_share="full_authorized"
    `open_to_public` falsy  -> privacy_mode="closed",  control_centre_share="aggregate"

    `allow_posko_public_choice` is left untouched, so a posko the org set to
    "public" (e.g. a shared TNI ship) stays public even after the org closes.
    A closed org keeps its activity private from outsiders while its own
    members still see full detail of their poskos.
    """
    actor = rn_actor()

    if not can_manage_organization(actor, organization):
        frappe.throw(
            "Anda tidak dapat mengubah kebijakan Kelompok ini",
            frappe.PermissionError,
        )

    is_open = cint(open_to_public)

    doc = frappe.get_doc("RN Organization", organization)
    doc.privacy_mode = "open" if is_open else "closed"
    doc.control_centre_share = "full_authorized" if is_open else "aggregate"
    doc.save(ignore_permissions=True)

    return {
        "organization": doc.name,
        "privacy_mode": doc.privacy_mode,
        "control_centre_share": doc.control_centre_share,
        "allow_posko_public_choice": doc.allow_posko_public_choice,
    }


@frappe.whitelist()
def set_posko_public_choice(organization, allow):
    """Flip only `allow_posko_public_choice` — the org's permission for its
    poskos to publish their own detail. Turning it off makes any currently
    "public" posko fall back to "inherit" (rn_organization.on_update cascade)."""
    actor = rn_actor()

    if not can_manage_organization(actor, organization):
        frappe.throw(
            "Anda tidak dapat mengubah kebijakan Kelompok ini",
            frappe.PermissionError,
        )

    doc = frappe.get_doc("RN Organization", organization)
    doc.allow_posko_public_choice = cint(allow)
    doc.save(ignore_permissions=True)

    return {
        "organization": doc.name,
        "allow_posko_public_choice": doc.allow_posko_public_choice,
    }


@frappe.whitelist()
def update_posko(
    posko,
    public_detail="inherit",
    public_participation=0,
    accept_volunteers=0,
    accept_goods=0,
    accept_donations=0,
    accept_partners=0,
    public_service_access=0,
):
    actor = rn_actor()

    if not can_manage_posko(actor, posko):
        frappe.throw(
            "Anda tidak dapat mengubah kebijakan Posko ini",
            frappe.PermissionError,
        )

    if public_detail not in (
        "inherit",
        "private",
        "public",
    ):
        frappe.throw("Public detail tidak valid")

    doc = frappe.get_doc(
        "RN Posko",
        posko,
    )

    # Komando terpusat: visibility / openness of a posko is decided by the pusat.
    from rescue_net import command
    if doc.organization and not command.is_bypassed() and command.needs_approval(actor, doc.organization):
        return command.file_request(
            actor, doc.organization, "update_posko",
            {"posko": doc.name, "privacy": {
                "public_detail": public_detail,
                "public_participation": public_participation,
                "accept_volunteers": accept_volunteers,
                "accept_goods": accept_goods,
                "accept_donations": accept_donations,
                "accept_partners": accept_partners,
                "public_service_access": public_service_access,
            }},
            "Ubah kebijakan publik posko %s" % (doc.title or doc.name),
            target_posko=doc.name,
        )

    doc.public_detail = public_detail
    doc.public_participation = cint(
        public_participation
    )
    doc.accept_volunteers = cint(
        accept_volunteers
    )
    doc.accept_goods = cint(accept_goods)
    doc.accept_donations = cint(
        accept_donations
    )
    doc.accept_partners = cint(
        accept_partners
    )
    doc.public_service_access = cint(
        public_service_access
    )

    # Controller enforces Organization ceiling.
    doc.save(ignore_permissions=True)

    return {
        "posko": doc.name,
        "public_detail": doc.public_detail,
        "public_allowed": public_posko_allowed(
            doc.name
        ),
        "public_participation": (
            doc.public_participation
        ),
        "public_service_access": (
            doc.public_service_access
        ),
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_posko(posko):
    if not public_posko_allowed(posko):
        frappe.throw(
            "Detail Posko tidak dibuka untuk publik",
            frappe.PermissionError,
        )

    doc = frappe.db.get_value(
        "RN Posko",
        posko,
        [
            "name", "title", "posko_type",
            "province_name", "city_name",
            "district_name", "village_name",
            "verification_status",
            "operational_status",
            "public_participation",
            "accept_volunteers",
            "accept_goods",
            "accept_donations",
            "accept_partners",
            "public_service_access",
            "source_updated_at",
            "observed_at",
            "modified",
            "freshness_policy_minutes",
        ],
        as_dict=True,
    )

    return doc
