"""Komando terpusat — API for the pusat (command centre) and for the lower levels
that file requests to it. Rules and helpers live in `rescue_net.command`;
gates in the existing endpoints (create_posko, update_posko, set_posko_functions,
api_privacy.update_posko, request_membership) only call into that module.
"""

import json

import frappe
from frappe.rate_limiter import rate_limit
from frappe.sessions import clear_sessions
from frappe.utils import now_datetime
from frappe.utils.password import update_password

from rescue_net import command
from rescue_net.access_policy import is_system_manager, rn_actor


def _titles(names):
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


def _owned_centers(actor):
    """terpusat organisations `actor` commands (owner or deputy). System Manager: all of them."""
    if is_system_manager():
        return frappe.get_all("RN Organization", filters={"coordination_scheme": "terpusat"},
                              pluck="name", limit_page_length=500)
    if not actor or not actor.get("name"):
        return []
    owned = frappe.get_all(
        "RN Organization Membership",
        filters={"user_account": actor.name, "membership_role": ["in", list(command.AUTHORITY_ROLES)], "status": "approved"},
        pluck="organization", limit_page_length=200,
    )
    return [o for o in sorted(set(owned)) if command.scheme_of(o) == command.TERPUSAT]


def _require_owner(actor, organization):
    """Pusat authority = owner or deputy (wakil pusat)."""
    if not command.command_chain(organization):
        frappe.throw("Organisasi ini tidak berada di bawah komando terpusat.")
    if not command.is_command_authority(actor, organization):
        frappe.throw("Hanya pengelola pusat komando yang dapat melakukan ini.", frappe.PermissionError)


def _require_strict_owner(actor, organization):
    """Only the pusat OWNER (not a deputy): appointing / revoking deputies."""
    if not command.is_command_owner(actor, organization):
        frappe.throw("Hanya pemilik (super admin) pusat komando yang dapat melakukan ini.", frappe.PermissionError)


def _account_org(user_account):
    """The organisation a command-created account belongs to (approved membership)."""
    return frappe.db.get_value(
        "RN Organization Membership",
        {"user_account": user_account, "status": "approved"},
        "organization", order_by="creation asc",
    ) or frappe.db.get_value("RN User Account", user_account, "organization")


# --------------------------------------------------------------------
# Read
# --------------------------------------------------------------------

@frappe.whitelist()
def command_status(organization=None):
    """Small gate for the frontend: how does the actor stand w.r.t. the command
    scheme of `organization` (default: the actor's own organisation)?"""
    actor = rn_actor()
    org = organization or (actor.get("organization") if actor else None)
    chain = command.command_chain(org) if org else []
    return {
        "organization": org,
        "scheme": command.scheme_of(org) if org else command.MANDIRI,
        "under_command": bool(chain),
        "command_organization": chain[0] if chain else None,
        "is_command_owner": bool(chain) and command.is_command_owner(actor, org),
        "is_command_authority": bool(chain) and command.is_command_authority(actor, org),
        "needs_approval": bool(chain) and command.needs_approval(actor, org),
        "owned_centers": _owned_centers(actor),
    }


@frappe.whitelist()
def command_overview(organization=None):
    """Everything the pusat needs on one screen: its tree of organisations,
    poskos, accounts, and the request queue."""
    actor = rn_actor()
    centers = _owned_centers(actor)
    if not centers:
        frappe.throw("Anda bukan pengelola pusat komando.", frappe.PermissionError)
    center = organization if organization in centers else centers[0]

    tree = sorted(command.command_tree(center))
    titles = _titles(tree)

    orgs = frappe.get_all(
        "RN Organization", filters={"name": ["in", tree]},
        fields=["name", "title", "parent_organization", "coordination_scheme", "status"],
        order_by="title asc", limit_page_length=500,
    )
    poskos = frappe.get_all(
        "RN Posko", filters={"organization": ["in", tree]},
        fields=["name", "title", "organization", "posko_type", "operational_status", "disaster_event"],
        order_by="title asc", limit_page_length=1000,
    )
    posko_title = {p.name: p.title for p in poskos}

    memberships = frappe.get_all(
        "RN Organization Membership",
        filters={"organization": ["in", tree], "status": "approved"},
        fields=["user_account", "organization", "membership_role"], limit_page_length=2000,
    )
    account_ids = sorted({m.user_account for m in memberships})
    acc_rows = {
        a.name: a for a in frappe.get_all(
            "RN User Account", filters={"name": ["in", account_ids or [""]]},
            fields=["name", "title", "email", "role", "status", "posko", "frappe_user"],
            limit_page_length=2000,
        )
    }
    assign = {}
    for a in frappe.get_all(
        "RN Posko Assignment",
        filters={"user_account": ["in", account_ids or [""]], "status": "approved"},
        fields=["user_account", "posko"], limit_page_length=4000,
    ):
        assign.setdefault(a.user_account, a.posko)

    accounts = []
    for m in memberships:
        a = acc_rows.get(m.user_account)
        if not a:
            continue
        posko = a.posko or assign.get(a.name)
        accounts.append({
            "user_account": a.name, "name": a.title, "email": a.email, "role": a.role,
            "status": a.status, "membership_role": m.membership_role,
            "organization": m.organization, "organization_title": titles.get(m.organization, m.organization),
            "posko": posko, "posko_title": posko_title.get(posko) or posko,
        })

    reqs = frappe.get_all(
        "RN Command Change Request",
        filters={"command_organization": ["in", command.command_chain(center) or [center]]},
        fields=["name", "command_organization", "organization", "action", "target_posko", "summary",
                "status", "requested_by", "requested_at", "decided_by", "decided_at", "decision_note",
                "apply_result"],
        order_by="creation desc", limit_page_length=100,
    )
    requester_names = {
        r.name: r.title for r in frappe.get_all(
            "RN User Account", filters={"name": ["in", sorted({r.requested_by for r in reqs if r.requested_by}) or [""]]},
            fields=["name", "title"], limit_page_length=200,
        )
    }
    for r in reqs:
        r["organization_title"] = titles.get(r.organization) or r.organization
        r["requested_by_name"] = requester_names.get(r.requested_by) or r.requested_by
        # never echo an apply_result that could carry a credential: it never does, but keep it short
        r["apply_result"] = (r.apply_result or "")[:300]

    return {
        "centers": [{"organization": c, "title": _titles([c]).get(c, c)} for c in centers],
        "center": {"organization": center, "title": titles.get(center, center)},
        "organizations": [dict(o, is_center=o.name == center, posko_count=sum(1 for p in poskos if p.organization == o.name),
                               account_count=sum(1 for a in accounts if a["organization"] == o.name)) for o in orgs],
        "poskos": poskos,
        "accounts": accounts,
        "requests": reqs,
        "pending_count": sum(1 for r in reqs if r.status == "pending"),
        "account_roles": list(command.ACCOUNT_ROLES),
        "viewer_is_owner": command.is_command_owner(actor, center),
        "notify_recipients": [{"name": a["name"], "role": a["role"], "has_phone": bool((a["phone"] or "").strip())}
                              for a in command.authorities(center)],
    }


@frappe.whitelist()
def my_command_requests():
    """Requests the caller filed to a pusat (so lower levels can see the outcome)."""
    actor = rn_actor()
    if not actor or not actor.get("name"):
        return {"requests": []}
    rows = frappe.get_all(
        "RN Command Change Request", filters={"requested_by": actor.name},
        fields=["name", "command_organization", "organization", "action", "summary", "status",
                "requested_at", "decided_at", "decision_note"],
        order_by="creation desc", limit_page_length=50,
    )
    titles = _titles([r.command_organization for r in rows] + [r.organization for r in rows])
    for r in rows:
        r["command_title"] = titles.get(r.command_organization) or r.command_organization
        r["organization_title"] = titles.get(r.organization) or r.organization
    return {"requests": rows}


# --------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------

@frappe.whitelist()
@rate_limit(limit=60, seconds=3600)
def create_command_account(organization, full_name, email, posko=None, role="posko_operator",
                           phone=None, username=None, password=None):
    """The pusat creates a posko account. Ready to log in immediately; if no
    password is given a temporary one is generated and returned ONCE."""
    actor = rn_actor()
    _require_owner(actor, organization)
    return command.create_account(organization, full_name, email, posko=posko, role=role,
                                  phone=phone, username=username, password=password)


@frappe.whitelist()
@rate_limit(limit=30, seconds=3600)
def request_command_account(organization, full_name, email, posko=None, role="posko_operator",
                            phone=None, username=None):
    """A lower level asks the pusat to add an account. Nothing is created until approved."""
    actor = rn_actor()
    if not command.command_chain(organization):
        frappe.throw("Organisasi ini tidak berada di bawah komando terpusat.")
    if command.is_command_authority(actor, organization):
        frappe.throw("Anda pengelola pusat: buat akun langsung, tidak perlu pengajuan.")
    if not command.is_account_member(actor, organization):
        frappe.throw("Anda bukan anggota organisasi ini.", frappe.PermissionError)
    if not (email or "").strip() or not (full_name or "").strip():
        frappe.throw("Nama lengkap dan email wajib diisi.")
    return command.file_request(
        actor, organization, "create_account",
        {"full_name": full_name, "email": email, "posko": posko, "role": role,
         "phone": phone, "username": username},
        "Tambah akun: %s (%s)" % (full_name, (email or "").strip().lower()),
        target_posko=posko,
    )


def _managed_account(actor, user_account):
    org = _account_org(user_account)
    if not org:
        frappe.throw("Akun tidak ditemukan di organisasi mana pun.")
    _require_owner(actor, org)
    if frappe.db.exists("RN Organization Membership", {"user_account": user_account, "membership_role": "owner",
                                                        "status": "approved"}):
        frappe.throw("Akun pemilik organisasi tidak bisa dikelola dari sini.")
    if frappe.db.exists("RN Organization Membership", {"user_account": user_account,
                                                        "membership_role": command.DEPUTY_ROLE, "status": "approved"}):
        # a deputy can be suspended / reset only by the owner, never by another deputy
        _require_strict_owner(actor, org)
    if actor and actor.get("name") == user_account:
        frappe.throw("Anda tidak bisa mengelola akun Anda sendiri dari sini.")
    return org


@frappe.whitelist()
def set_command_account_active(user_account, active=1, note=None):
    """The pusat suspends / reactivates a posko account (and blocks its login)."""
    actor = rn_actor()
    _managed_account(actor, user_account)
    on = str(active).lower() in ("1", "true", "yes")
    if not on and not (note or "").strip():
        frappe.throw("Alasan penonaktifan wajib diisi.")
    frappe.db.set_value("RN User Account", user_account, "status", "active" if on else "suspended")
    fu = frappe.db.get_value("RN User Account", user_account, "frappe_user")
    if fu:
        frappe.db.set_value("User", fu, "enabled", 1 if on else 0)
        if not on:
            clear_sessions(fu, force=True)
    return {"user_account": user_account, "status": "active" if on else "suspended"}


@frappe.whitelist()
@rate_limit(limit=30, seconds=3600)
def reset_command_account_password(user_account, new_password=None):
    """The pusat resets a posko account's password. Temporary password returned ONCE."""
    actor = rn_actor()
    _managed_account(actor, user_account)
    fu = frappe.db.get_value("RN User Account", user_account, "frappe_user")
    if not fu:
        frappe.throw("Akun belum punya pengguna login.")
    temporary = None
    if (new_password or "").strip():
        from rescue_net.api_auth import _check_password_strength
        _check_password_strength(new_password)
    else:
        new_password = temporary = command.generate_password()
    update_password(fu, new_password)
    clear_sessions(fu, force=True)
    return {"user_account": user_account, "temporary_password": temporary}


@frappe.whitelist()
def set_command_deputy(organization, user_account, active=1):
    """The pusat OWNER appoints / revokes a deputy (wakil pusat): an approved
    member of the pusat org who may then decide requests, create accounts and
    administer the tree — but cannot appoint deputies or touch the owner.
    `organization` must be the pusat itself (a terpusat organisation)."""
    actor = rn_actor()
    if command.scheme_of(organization) != command.TERPUSAT:
        frappe.throw("Wakil hanya bisa diangkat pada organisasi pusat (skema komando terpusat).")
    _require_strict_owner(actor, organization)
    row = frappe.db.get_value(
        "RN Organization Membership",
        {"user_account": user_account, "organization": organization, "status": "approved"},
        ["name", "membership_role"], as_dict=True,
    )
    if not row:
        frappe.throw("Akun itu belum menjadi anggota organisasi pusat ini.")
    if row.membership_role == "owner":
        frappe.throw("Pemilik pusat tidak bisa dijadikan atau dicabut sebagai wakil.")
    on = str(active).lower() in ("1", "true", "yes")
    frappe.db.set_value("RN Organization Membership", row.name, "membership_role",
                        command.DEPUTY_ROLE if on else "member")
    return {"user_account": user_account, "organization": organization,
            "membership_role": command.DEPUTY_ROLE if on else "member"}


# --------------------------------------------------------------------
# Requests: decide / withdraw
# --------------------------------------------------------------------

def _requester_actor(account_name):
    if not account_name:
        return None
    return frappe.db.get_value("RN User Account", account_name,
                               ["name", "frappe_user", "role", "organization", "posko"], as_dict=True)


def _apply(doc):
    """Apply an approved request. Runs with command_bypass set (see command.py)."""
    payload = json.loads(doc.payload or "{}")
    if doc.action == "create_posko":
        from rescue_net.api_community_cluster import _create_posko_impl
        requester = _requester_actor(doc.requested_by)
        if not requester:
            frappe.throw("Akun pemohon tidak ditemukan.")
        res = _create_posko_impl(requester, assignment_status="approved", **payload)
        return {"posko": res.get("posko")}
    if doc.action == "update_posko":
        if payload.get("privacy"):
            from rescue_net.api_privacy import update_posko as privacy_update
            privacy_update(posko=payload["posko"], **payload["privacy"])
        if payload.get("changes"):
            from rescue_net.api_community_cluster import update_posko
            update_posko(posko=payload["posko"], **payload["changes"])
        return {"posko": payload.get("posko")}
    if doc.action == "set_posko_functions":
        from rescue_net.api_control_centre import set_posko_functions
        set_posko_functions(posko=payload["posko"], functions=payload.get("functions"),
                            logistics_role=payload.get("logistics_role"))
        return {"posko": payload.get("posko")}
    if doc.action == "create_account":
        return command.create_account(doc.organization, **payload)
    frappe.throw("Jenis permintaan tidak dikenal.")


@frappe.whitelist()
def decide_command_request(request, decision, note=None):
    """The pusat approves (applies the change) or rejects (reason required)."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Command Change Request", request)
    _require_owner(actor, doc.organization)
    if doc.status != "pending":
        frappe.throw("Permintaan ini sudah diputuskan (%s)." % doc.status)

    decision = str(decision or "").strip().lower()
    if decision not in ("approve", "reject"):
        frappe.throw("Keputusan harus approve atau reject.")
    if decision == "reject" and not (note or "").strip():
        frappe.throw("Alasan penolakan wajib diisi.")
    if doc.requested_by and actor and actor.get("name") == doc.requested_by and not is_system_manager():
        frappe.throw("Anda tidak dapat menyetujui permintaan Anda sendiri.")

    doc.decided_by = (actor.get("name") if actor and actor.get("name") else frappe.session.user)
    doc.decided_at = now_datetime()
    if note is not None:
        doc.decision_note = str(note)[:500]

    result = None
    if decision == "reject":
        doc.status = "rejected"
    else:
        frappe.flags.command_bypass = True
        frappe.db.savepoint("command_apply")
        try:
            result = _apply(doc)
            doc.status = "applied"
            safe = dict(result or {})
            safe.pop("temporary_password", None)
            doc.apply_result = json.dumps(safe, ensure_ascii=False, default=str)[:500]
        except Exception as e:
            frappe.db.rollback(save_point="command_apply")
            doc.status = "failed"
            doc.apply_result = ("Gagal diterapkan: %s" % e)[:500]
            result = None
        finally:
            frappe.flags.command_bypass = False

    doc.save(ignore_permissions=True)
    try:
        command.notify_request_decided(doc)
    except Exception:  # best-effort
        frappe.log_error(frappe.get_traceback(), "command notify_request_decided")
    out = {"request": doc.name, "status": doc.status, "apply_result": doc.apply_result}
    if result and result.get("temporary_password"):
        out["temporary_password"] = result["temporary_password"]
        out["email"] = result.get("email")
    return out


@frappe.whitelist()
def withdraw_command_request(request):
    actor = rn_actor()
    doc = frappe.get_doc("RN Command Change Request", request)
    if not actor or not actor.get("name") or doc.requested_by != actor.name:
        frappe.throw("Hanya pemohon yang dapat menarik permintaan ini.", frappe.PermissionError)
    if doc.status != "pending":
        frappe.throw("Permintaan ini sudah diputuskan (%s)." % doc.status)
    doc.status = "withdrawn"
    doc.decided_at = now_datetime()
    doc.save(ignore_permissions=True)
    return {"request": doc.name, "status": doc.status}


# --------------------------------------------------------------------
# Scheme (after registration): System Manager only
# --------------------------------------------------------------------

@frappe.whitelist()
def set_coordination_scheme(organization, scheme):
    """The scheme is chosen when the pusat registers; afterwards only a System
    Manager can change it (an existing organisation must not be turned into a
    command organisation by its own members)."""
    if not is_system_manager():
        frappe.throw("Hanya System Manager yang dapat mengubah skema koordinasi.", frappe.PermissionError)
    scheme = (scheme or "").strip().lower()
    if scheme not in command.SCHEMES:
        frappe.throw("Skema tidak valid (mandiri/terpusat).")
    if not frappe.db.exists("RN Organization", organization):
        frappe.throw("Organisasi tidak ditemukan.")
    frappe.db.set_value("RN Organization", organization, "coordination_scheme", scheme)
    return {"organization": organization, "scheme": scheme}
