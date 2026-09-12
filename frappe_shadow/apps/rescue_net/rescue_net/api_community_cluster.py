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
            "trust_level","verification_status","parent_organization"
        ],
        order_by="title asc",
        limit_page_length=500,
    )


@frappe.whitelist()
def create_organization(title, organization_type="community",
                        contact_person=None, notes=None,
                        parent_organization=None):
    actor = _actor()

    parent_organization = (parent_organization or "").strip() or None
    if parent_organization and not frappe.db.exists(
        "RN Organization", parent_organization
    ):
        frappe.throw("Organisasi induk tidak ditemukan.")

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

    # Claiming a parent at registration is a REQUEST, not a fact — the parent's
    # own owner must accept it (see set_org_parent below). Only bypassed when
    # the creator already owns that parent org (e.g. an admin opening a branch
    # of their own org), in which case it's attached immediately.
    link_result = None
    if parent_organization:
        link_result = set_org_parent(
            org.name, parent_organization,
            note="Diajukan saat pendaftaran organisasi baru.",
        )

    link_pending = bool(link_result and link_result.get("pending"))
    return {
        "organization": org.name,
        "membership": membership.name,
        "status": org.status,
        "trust_level": org.trust_level,
        "parent_organization": (link_result or {}).get("parent_organization") if not link_pending else None,
        "parent_link_pending": link_pending,
        "parent_link_request": (link_result or {}).get("request") if link_pending else None,
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
# Organisation hierarchy ("satu komando").
# The org created first is NOT automatically the induk. Linking always
# touches only `RN Organization.parent_organization`; nothing is absorbed or
# deleted. Every change (pending, rejected, withdrawn, or executed) is a row
# on `RN Org Merge Request`, which doubles as the audit trail.
#
# Consent model (revised 2026-09-12 — supersedes the earlier "no approval"
# rule): whichever side did NOT initiate the change must approve it, with
# real contact-person data shown so both sides can verify who they're
# dealing with, and a required reason on reject:
#   - attach: if the CHILD's owner asks to join a parent, the PARENT's owner
#     must approve/reject. If the PARENT's owner pulls in a standalone org,
#     the CHILD's owner must approve/reject.
#   - detach: the CHILD's owner may ask to leave, but the CURRENT parent's
#     owner must approve/reject (a chapter can no longer just walk out
#     unilaterally).
#   - Only when the SAME actor manages both sides (or a System Manager acts)
#     is the change applied immediately with no pending step — there is
#     nobody else who needs to consent.
# ============================================================

_ORG_HIER_LOG_FIELDS = [
    "name", "requester_organization", "target_organization", "status",
    "note", "requested_by", "requested_at",
]


def _org_titles(names):
    names = sorted({n for n in names if n})
    if not names:
        return {}
    return {
        r.name: r.title
        for r in frappe.get_all(
            "RN Organization", filters={"name": ["in", names]},
            fields=["name", "title"], limit_page_length=len(names),
        )
    }


def _hier_log_row(r, titles):
    # requester_organization holds the parent, target_organization the child.
    return {
        "name": r.name,
        "parent_organization": r.requester_organization,
        "parent_title": titles.get(r.requester_organization, r.requester_organization),
        "child_organization": r.target_organization,
        "child_title": titles.get(r.target_organization, r.target_organization),
        "action": r.status,
        "note": r.note,
        "by": r.requested_by,
        "at": r.requested_at,
    }


def _org_descendants(root):
    """Set of every org at or below `root` (cycle-safe)."""
    seen, stack = set(), [root]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for c in frappe.get_all(
            "RN Organization", filters={"parent_organization": cur},
            pluck="name", limit_page_length=500,
        ):
            stack.append(c)
    return seen


@frappe.whitelist()
def org_coordination():
    """One payload for the "Organisasi Saya" panel on Koordinasi Organisasi:
    the org(s) the caller owns (each with parent + direct children), a flat
    {name,title} list of every org for the pickers, the recent hierarchy
    change log touching the caller's orgs, and any pending attach/detach
    requests awaiting a decision (with contact-person data for both sides
    so the decider can verify who's actually asking)."""
    actor = _actor()
    from rescue_net.access_policy import is_system_manager

    owned = _owned_org_names(actor)
    all_orgs = frappe.get_all(
        "RN Organization",
        fields=["name", "title", "parent_organization", "contact_person", "organization_type"],
        order_by="title asc", limit_page_length=2000,
    )
    all_orgs_min = [{"name": o.name, "title": o.title or o.name,
                     "parent_organization": o.parent_organization,
                     "contact_person": o.contact_person,
                     "organization_type": o.organization_type} for o in all_orgs]

    if not owned:
        return {"is_org_admin": False, "organizations": [],
                "all_orgs": all_orgs_min, "hierarchy_log": [], "pending_requests": []}

    by_name = {o.name: o for o in all_orgs}
    children_by_parent = {}
    for o in all_orgs:
        if o.parent_organization:
            children_by_parent.setdefault(o.parent_organization, []).append(
                {"name": o.name, "title": o.title or o.name}
            )

    owned_set = set(owned)
    log_rows = frappe.get_all(
        "RN Org Merge Request",
        filters={"status": ["in", ["attached", "detached"]]},
        or_filters={"requester_organization": ["in", owned],
                    "target_organization": ["in", owned]},
        fields=_ORG_HIER_LOG_FIELDS, order_by="requested_at desc",
        limit_page_length=50,
    )
    pending_rows = frappe.get_all(
        "RN Org Merge Request",
        filters={"status": "pending"},
        or_filters={"requester_organization": ["in", owned],
                    "target_organization": ["in", owned]},
        fields=["name", "requester_organization", "target_organization", "action",
                "note", "requested_by", "requested_at"],
        order_by="requested_at desc", limit_page_length=50,
    )
    titles = _org_titles(
        [o.name for o in all_orgs]
        + [r.requester_organization for r in log_rows]
        + [r.target_organization for r in log_rows]
        + [r.requester_organization for r in pending_rows]
        + [r.target_organization for r in pending_rows]
    )

    orgs = []
    for name in owned:
        o = by_name.get(name)
        if not o:
            continue
        orgs.append({
            "name": o.name,
            "title": o.title,
            "parent_organization": o.parent_organization,
            "parent_title": titles.get(o.parent_organization) if o.parent_organization else None,
            "children": children_by_parent.get(o.name, []),
        })

    return {
        "is_org_admin": True,
        "is_system_manager": bool(is_system_manager()),
        "owned": sorted(owned_set),
        "organizations": orgs,
        "all_orgs": all_orgs_min,
        "hierarchy_log": [_hier_log_row(r, titles) for r in log_rows],
        "pending_requests": _pending_org_link_rows(pending_rows, titles, owned_set, actor),
    }


def _pending_org_link_rows(pending_rows, titles, owned_set, actor):
    involved = {r.requester_organization for r in pending_rows} | {r.target_organization for r in pending_rows}
    involved.discard(None)
    contacts = {}
    if involved:
        for o in frappe.get_all(
            "RN Organization", filters={"name": ["in", list(involved)]},
            fields=["name", "contact_person", "contact_summary", "organization_type"],
            limit_page_length=len(involved),
        ):
            contacts[o.name] = {"contact_person": o.contact_person,
                                 "contact_summary": o.contact_summary,
                                 "organization_type": o.organization_type}

    requesters = sorted({r.requested_by for r in pending_rows if r.requested_by})
    users = {}
    if requesters:
        for u in frappe.get_all(
            "RN User Account", filters={"name": ["in", requesters]},
            fields=["name", "username", "email", "phone"], limit_page_length=len(requesters),
        ):
            users[u.name] = {"name": u.name, "username": u.username, "email": u.email, "phone": u.phone}

    out = []
    for r in pending_rows:
        out.append({
            "name": r.name,
            "action": r.action,
            "parent_organization": r.requester_organization,
            "parent_title": titles.get(r.requester_organization, r.requester_organization),
            "parent_contact": contacts.get(r.requester_organization),
            "child_organization": r.target_organization,
            "child_title": titles.get(r.target_organization, r.target_organization),
            "child_contact": contacts.get(r.target_organization),
            "note": r.note,
            "requested_by": r.requested_by,
            "requested_by_contact": users.get(r.requested_by),
            "requested_at": r.requested_at,
            "can_decide": (r.requested_by != actor.name) and
                bool({r.requester_organization, r.target_organization} & owned_set),
            "can_withdraw": r.requested_by == actor.name,
        })
    return out


def _apply_org_link(organization, parent_organization, old_parent, note, actor):
    """Actually write `parent_organization` and log the executed change.
    Shared by the immediate path in `set_org_parent` and by `decide_org_link`
    approving a pending request."""
    frappe.db.set_value(
        "RN Organization", organization, "parent_organization", parent_organization
    )
    log = frappe.new_doc("RN Org Merge Request")
    log.requester_organization = parent_organization or old_parent or organization
    log.target_organization = organization
    log.action = "attach" if parent_organization else "detach"
    log.note = note
    log.status = "attached" if parent_organization else "detached"
    log.requested_by = actor.name
    log.requested_at = now_datetime()
    log.decided_by = actor.name
    log.decided_at = now_datetime()
    log.insert(ignore_permissions=True)
    return {
        "organization": organization,
        "parent_organization": parent_organization,
        "previous_parent": old_parent,
        "action": log.status,
        "pending": False,
    }


@frappe.whitelist()
def set_org_parent(organization, parent_organization=None, note=None):
    """Attach `organization` under `parent_organization`, or detach it when
    `parent_organization` is empty.

    Whoever does NOT already manage the "other side" of the change must
    consent — this call files a pending `RN Org Merge Request` for them to
    decide via `decide_org_link` instead of writing anything. It only
    executes immediately when nobody else needs to be asked: a System
    Manager, or an actor who manages BOTH the org and the other side
    (current parent for a detach, new parent for an attach).

    Permission to even file/execute: system manager, OR the caller owns
    `organization`, OR (for an attach) the caller owns the new
    `parent_organization`.
    """
    actor = _actor()
    from rescue_net.access_policy import is_system_manager

    organization = (organization or "").strip()
    parent_organization = (parent_organization or "").strip() or None

    if not organization or not frappe.db.exists("RN Organization", organization):
        frappe.throw("Organisasi tidak ditemukan.")
    if parent_organization:
        if parent_organization == organization:
            frappe.throw("Organisasi tidak bisa menjadi induk dirinya sendiri.")
        if not frappe.db.exists("RN Organization", parent_organization):
            frappe.throw("Organisasi induk tidak ditemukan.")

    owns_child = _owns_org(actor, organization)
    owns_parent = bool(parent_organization) and _owns_org(actor, parent_organization)
    sysmgr = is_system_manager()
    if not (sysmgr or owns_child or owns_parent):
        frappe.throw(
            "Anda harus pengelola organisasi ini atau pengelola organisasi induk.",
            frappe.PermissionError,
        )

    old_parent = frappe.db.get_value(
        "RN Organization", organization, "parent_organization"
    )
    if (old_parent or None) == parent_organization:
        return {"organization": organization,
                "parent_organization": parent_organization, "unchanged": True}

    # cycle guard: the new parent must not sit at/below `organization`
    if parent_organization and parent_organization in _org_descendants(organization):
        frappe.throw("Tidak bisa: akan membentuk lingkaran hierarki.")

    action = "attach" if parent_organization else "detach"
    # Whoever does NOT already manage `other_side` is the one who must
    # consent. For an attach, that's the child unless the actor only owns
    # the prospective parent (an induk pulling a standalone org) — then it's
    # the child's owner who must consent instead.
    if action == "attach":
        other_side = organization if (owns_parent and not owns_child) else parent_organization
    else:
        other_side = old_parent

    if sysmgr or not other_side or _owns_org(actor, other_side):
        return _apply_org_link(organization, parent_organization, old_parent, note, actor)

    # the other side must consent — reuse an existing pending request instead
    # of spamming duplicates if one is already awaiting decision.
    # requester_organization always holds the PARENT slot, target_organization
    # the CHILD slot (same convention as the executed attached/detached log
    # rows) — `other_side` above is only used to decide who must approve.
    parent_slot = parent_organization if action == "attach" else old_parent
    existing = frappe.db.get_value(
        "RN Org Merge Request",
        {"target_organization": organization, "requester_organization": parent_slot,
         "action": action, "status": "pending"},
        "name",
    )
    if existing:
        return {"organization": organization, "parent_organization": parent_organization,
                "pending": True, "request": existing, "reused_existing": True}

    req = frappe.new_doc("RN Org Merge Request")
    req.requester_organization = parent_slot
    req.target_organization = organization
    req.action = action
    req.status = "pending"
    req.note = note
    req.requested_by = actor.name
    req.requested_at = now_datetime()
    req.insert(ignore_permissions=True)

    return {"organization": organization, "parent_organization": parent_organization,
            "pending": True, "request": req.name}


@frappe.whitelist()
def decide_org_link(request, action, note=None):
    """Approve/reject/withdraw a pending attach/detach request from
    `set_org_parent`. Approve executes the change now; reject requires a
    reason (`note`, stored as `decision_note`); withdraw lets the original
    requester cancel before anyone decides."""
    actor = _actor()
    from rescue_net.access_policy import is_system_manager

    doc = frappe.get_doc("RN Org Merge Request", request)
    if doc.status != "pending":
        frappe.throw("Permintaan ini sudah diputuskan atau dibatalkan.")

    action = str(action or "").strip().lower()
    if action not in ("approve", "reject", "withdraw"):
        frappe.throw("Aksi tidak valid (approve/reject/withdraw)")

    sysmgr = is_system_manager()

    if action == "withdraw":
        if not (sysmgr or actor.name == doc.requested_by):
            frappe.throw("Hanya pengaju yang bisa membatalkan permintaan ini.", frappe.PermissionError)
        doc.status = "withdrawn"
        doc.decided_by = actor.name
        doc.decided_at = now_datetime()
        if note is not None:
            doc.decision_note = str(note)[:500]
        doc.save(ignore_permissions=True)
        return {"request": doc.name, "status": doc.status}

    can_decide = sysmgr or _owns_org(actor, doc.requester_organization) or _owns_org(actor, doc.target_organization)
    if not can_decide:
        frappe.throw("Anda bukan pengelola organisasi terkait.", frappe.PermissionError)
    if actor.name == doc.requested_by and not sysmgr:
        frappe.throw("Anda tidak bisa memutuskan permintaan yang Anda ajukan sendiri — menunggu pihak lain.", frappe.PermissionError)

    if action == "reject":
        if not note or not str(note).strip():
            frappe.throw("Alasan penolakan wajib diisi.")
        doc.status = "rejected"
        doc.decided_by = actor.name
        doc.decided_at = now_datetime()
        doc.decision_note = str(note)[:500]
        doc.save(ignore_permissions=True)
        return {"request": doc.name, "status": doc.status}

    # approve -> execute the attach/detach now, guarding against stale state
    child = doc.target_organization
    current_parent = frappe.db.get_value("RN Organization", child, "parent_organization")
    if doc.action == "attach":
        if current_parent:
            frappe.throw("Organisasi ini sudah punya induk lain sekarang — permintaan tidak berlaku lagi.")
        if doc.requester_organization in _org_descendants(child):
            frappe.throw("Tidak bisa: akan membentuk lingkaran hierarki.")
        new_parent = doc.requester_organization
    else:
        if current_parent != doc.requester_organization:
            frappe.throw("Status organisasi sudah berubah — permintaan tidak berlaku lagi.")
        new_parent = None

    frappe.db.set_value("RN Organization", child, "parent_organization", new_parent)
    doc.status = "attached" if doc.action == "attach" else "detached"
    doc.decided_by = actor.name
    doc.decided_at = now_datetime()
    if note is not None:
        doc.decision_note = str(note)[:500]
    doc.save(ignore_permissions=True)

    return {"request": doc.name, "status": doc.status,
            "organization": child, "parent_organization": new_parent}


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

    if action in ("reject", "revoke") and (not note or not str(note).strip()):
        frappe.throw("Alasan penolakan/pencabutan wajib diisi.")

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
    officer_in_charge_whatsapp=None,
    emergency_contact=None, facilities=None, rn_beneficiary_count=None,
    public_detail=None, operational_status=None,
    active_from=None, active_until=None, notes=None,
    notify_whatsapp_enabled=None, notify_whatsapp_numbers=None,
):
    actor = _actor()
    doc = frappe.get_doc("RN Posko", posko)

    if not _can_edit_posko(actor, doc):
        frappe.throw("Akses edit posko ditolak", frappe.PermissionError)

    old_status = doc.operational_status

    for field, value in (
        ("title", title), ("posko_type", posko_type), ("address", address),
        ("operational_status", operational_status),
        ("officer_in_charge_name", officer_in_charge_name),
        ("officer_in_charge_role", officer_in_charge_role),
        ("officer_in_charge_phone", officer_in_charge_phone),
        ("officer_in_charge_whatsapp", officer_in_charge_whatsapp),
        ("officer_in_charge_email", officer_in_charge_email),
        ("emergency_contact", emergency_contact),
        ("facilities", facilities),
        ("notes", notes),
        ("notify_whatsapp_numbers", notify_whatsapp_numbers),
    ):
        if value is not None:
            setattr(doc, field, value)

    if notify_whatsapp_enabled is not None:
        doc.notify_whatsapp_enabled = 1 if str(notify_whatsapp_enabled) in ("1", "true", "True", "on", "yes") else 0

    if latitude not in (None, ""):
        doc.latitude = float(latitude)
    if longitude not in (None, ""):
        doc.longitude = float(longitude)
    if rn_beneficiary_count not in (None, ""):
        doc.rn_beneficiary_count = int(rn_beneficiary_count)
    if public_detail in ("inherit", "private", "public"):
        doc.public_detail = public_detail
    # dates: "" clears the field, a value sets it
    if active_from is not None:
        doc.active_from = active_from or None
    if active_until is not None:
        doc.active_until = active_until or None

    doc.save(ignore_permissions=True)

    # WhatsApp notify on an operational-status change (best-effort; a gateway
    # that is not configured just logs a 'simulated' row).
    if operational_status and operational_status != old_status:
        try:
            from rescue_net import api_notify

            api_notify.notify_posko(
                doc.name,
                "Status posko %s: %s -> %s."
                % (doc.title or doc.name, old_status or "-", operational_status),
                "posko_status_change",
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "notify_posko status change")

    return {"posko": doc.name, "modified": doc.modified}


@frappe.whitelist(allow_guest=True)
def get_posko_settings(posko):
    """Prefill payload + edit gate for the shared "Pengaturan Posko" panel on
    a posko workspace page. Mirrors `update_posko`'s `_can_edit_posko` gate.
    Guest-safe: returns `{can_edit: False}` without a 403 so the shared JS can
    call it unconditionally."""
    actor = rn_actor(required=False)
    if not actor:
        return {"can_edit": False, "posko": None}
    doc = frappe.get_doc("RN Posko", posko)
    fields = [
        "name", "title", "posko_type", "operational_status", "address",
        "latitude", "longitude", "active_from", "active_until",
        "officer_in_charge_name", "officer_in_charge_role",
        "officer_in_charge_phone", "officer_in_charge_whatsapp",
        "officer_in_charge_email", "emergency_contact", "facilities", "notes",
        "notify_whatsapp_enabled", "notify_whatsapp_numbers",
        "rn_beneficiary_count", "public_detail", "public_participation",
        "accept_volunteers", "accept_goods", "accept_donations",
        "province_name", "city_name", "district_name", "village_name",
        "organization", "disaster_event", "verification_status",
    ]
    return {
        "can_edit": bool(_can_edit_posko(actor, doc)),
        "posko": {f: doc.get(f) for f in fields},
    }


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
