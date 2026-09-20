import frappe
from frappe.utils import cint


def is_system_manager(user=None):
    user = user or frappe.session.user
    return (
        user == "Administrator"
        or "System Manager" in frappe.get_roles(user)
    )


def rn_actor(required=True):
    user = frappe.session.user

    if user == "Guest":
        if required:
            frappe.throw("Login diperlukan")
        return None

    if (
        user == "Administrator"
        or "System Manager" in frappe.get_roles(user)
    ):
        return frappe._dict({
            "name": None,
            "frappe_user": user,
            "role": "system_manager",
            "organization": None,
            "posko": None,
        })

    actor = frappe.db.get_value(
        "RN User Account",
        {"frappe_user": user, "status": "active"},
        [
            "name", "frappe_user", "role",
            "organization", "posko"
        ],
        as_dict=True,
    )

    if required and not actor:
        frappe.throw("Akun Rescue-Net aktif tidak ditemukan")

    # RN User Account.organization/posko are a legacy direct field that
    # most real accounts never have set — org/posko affiliation normally
    # lives on RN Organization Membership / RN Posko Assignment instead
    # (e.g. every account created via api_community_cluster.
    # create_organization). approved_member()/approved_posko_assignment()
    # and api_auth._primary_organization()/_primary_posko() already fall
    # back to those; rn_actor() didn't, so every caller that reads
    # actor.organization/actor.posko directly (most of the app) saw None
    # for an otherwise fully org-affiliated user.
    if actor and not actor.get("organization"):
        actor["organization"] = frappe.db.get_value(
            "RN Organization Membership",
            {"user_account": actor.name, "status": "approved"},
            "organization",
            order_by="creation asc",
        )
    if actor and not actor.get("posko"):
        actor["posko"] = frappe.db.get_value(
            "RN Posko Assignment",
            {"user_account": actor.name, "status": "approved"},
            "posko",
            order_by="creation asc",
        )

    return actor


def approved_member(user_account, organization):
    if not user_account or not organization:
        return False

    direct = frappe.db.get_value(
        "RN User Account",
        user_account,
        "organization",
    )

    if direct == organization:
        return True

    return bool(
        frappe.db.exists(
            "RN Organization Membership",
            {
                "user_account": user_account,
                "organization": organization,
                "status": "approved",
            },
        )
    )


def approved_posko_assignment(user_account, posko):
    if not user_account or not posko:
        return False

    direct = frappe.db.get_value(
        "RN User Account",
        user_account,
        "posko",
    )

    if direct == posko:
        return True

    return bool(
        frappe.db.exists(
            "RN Posko Assignment",
            {
                "user_account": user_account,
                "posko": posko,
                "status": "approved",
            },
        )
    )


def can_manage_organization(actor, organization):
    if is_system_manager():
        return True

    if not actor or not actor.name:
        return False

    if frappe.db.exists(
        "RN Organization Membership",
        {
            "user_account": actor.name,
            "organization": organization,
            "membership_role": "owner",
            "status": "approved",
        },
    ):
        return True

    # Komando terpusat: the owner of a `terpusat` pusat is super admin of every
    # organisation below it. No-op for `mandiri` organisations.
    from rescue_net.command import is_command_owner
    return is_command_owner(actor, organization)


# Roles that coordinate an organisation's whole response instead of running a
# single posko. A coordinator has no posko of their own but edits every posko
# their organisation runs (owner decision 2026-09-04 — "Koordinasi Internal
# Organisasi" phase 3 open item).
ORG_COORDINATOR_ROLES = {"community_coordinator"}


def is_org_coordinator(actor):
    return bool(
        actor
        and actor.name
        and (actor.get("role") if hasattr(actor, "get") else getattr(actor, "role", None))
        in ORG_COORDINATOR_ROLES
    )


def can_coordinate_posko(actor, posko):
    """True when `actor` is an org-level coordinator and `posko` belongs to the
    actor's own organisation."""
    if not is_org_coordinator(actor):
        return False

    actor_org = (
        actor.get("organization") if hasattr(actor, "get")
        else getattr(actor, "organization", None)
    )

    if not actor_org or not posko:
        return False

    posko_org = frappe.db.get_value("RN Posko", posko, "organization")

    return bool(posko_org) and posko_org == actor_org


def can_manage_posko(actor, posko):
    if is_system_manager():
        return True

    if not actor or not actor.name:
        return False

    if approved_posko_assignment(actor.name, posko):
        return True

    if can_coordinate_posko(actor, posko):
        return True

    # Komando terpusat: the pusat's owner manages every posko in the tree.
    from rescue_net.command import is_command_owner_of_posko
    return is_command_owner_of_posko(actor, posko)


def editable_disaster_events(actor):
    """Which RN Disaster Event names `actor` may edit Data Konsolidasi
    for. `None` = every event (System Manager). Otherwise a set
    (possibly empty) derived from `RN Posko.organization`/`.disaster_event`
    — an org's editable events are whichever events it actually runs a
    posko in; a lone posko-assignment actor with no org gets just their
    posko's event.

    Runs every event value through `resolve_disaster_event()` — RN Posko
    rows aren't guaranteed to store the disaster_event reference in the
    same canonical form callers resolve a user-supplied event ID to (seen
    before: the Krakatau sim's bare-vs-`disaster_events:`-prefixed
    mismatch), so a raw un-normalized comparison here would silently
    deny an org edit access to its own event."""
    from rescue_net.reference_resolver import resolve_disaster_event

    if is_system_manager():
        return None

    if not actor or not actor.name:
        return set()

    raw_events = set()

    org = (
        actor.get("organization") if hasattr(actor, "get")
        else getattr(actor, "organization", None)
    )
    if org:
        raw_events |= {
            e for e in frappe.get_all(
                "RN Posko",
                filters={"organization": org},
                pluck="disaster_event",
            )
            if e
        }

    posko = (
        actor.get("posko") if hasattr(actor, "get")
        else getattr(actor, "posko", None)
    )
    if posko:
        ev = frappe.db.get_value("RN Posko", posko, "disaster_event")
        if ev:
            raw_events.add(ev)

    return {
        resolve_disaster_event(e) or e
        for e in raw_events
    }


def can_edit_event(actor, event):
    events = editable_disaster_events(actor)
    return events is None or event in events


def public_posko_allowed(posko_name):
    posko = frappe.db.get_value(
        "RN Posko",
        posko_name,
        [
            "organization",
            "public_detail",
        ],
        as_dict=True,
    )

    if not posko:
        return False

    if posko.organization:
        org = frappe.db.get_value(
            "RN Organization",
            posko.organization,
            [
                "privacy_mode",
                "allow_posko_public_choice",
            ],
            as_dict=True,
        )

        if org:
            if org.privacy_mode != "open":
                return False

            if not cint(org.allow_posko_public_choice):
                return False

    return posko.public_detail == "public"
