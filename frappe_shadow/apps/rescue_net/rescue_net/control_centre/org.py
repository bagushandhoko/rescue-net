"""Control Centre — organisation/posko boards, posko registry and verification checklist, edit scope, org coordination."""

import frappe
from frappe.rate_limiter import rate_limit

from rescue_net.api_ai import (
    public_context,
    public_active_disasters,
)

from rescue_net.control_centre.common import (  # noqa: F401
    _ORG_BRAND_ACCENT,
    _ORG_BRAND_FIELDS,
    _ORG_PENDING_TERMS,
    _POSKO_INACTIVE_TERMS,
    _my_posko_names,
    _operate_href,
    _posko_actor_flags,
    _resolve_posko,
    _sf,
    canonical_event,
)


def _org_member_count(org_name):
    """Real member count: RN Organization Membership (formal, approved)
    union RN User Account.organization (looser but far more populated in
    the current seed data — most sim/community accounts never went through
    a formal Membership record)."""
    membership_users = set(frappe.get_all(
        "RN Organization Membership",
        filters={"organization": org_name, "status": "approved"},
        pluck="user_account",
    ))
    account_users = set(frappe.get_all(
        "RN User Account", filters={"organization": org_name}, pluck="name",
    ))
    return len(membership_users | account_users)


def _org_program_count(org_name):
    return frappe.db.count("RN Donor Program", {"owner_type": "organization", "owner_id": org_name})


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def org_posko_board(disaster_event=None):
    """Organisasi & Posko dashboard (matches the DMS mock-up), guest
    read-only. KPI totals + a tree (event -> organisasi -> posko) + a flat
    orgs list with real trust/member/program counts for the detail rail.
    """
    event = canonical_event(disaster_event) if disaster_event else None

    posko_filter = {"disaster_event": event} if event else {}
    poskos = frappe.get_all(
        "RN Posko", filters=posko_filter,
        fields=["name", "title", "organization", "posko_type", "operational_status", "verification_status"],
        limit_page_length=1000,
    )

    org_names = sorted({p.organization for p in poskos if p.organization})
    if not org_names and not event:
        org_names = frappe.get_all("RN Organization", pluck="name", limit_page_length=200)

    posko_by_org = {}
    for p in poskos:
        posko_by_org.setdefault(p.organization, []).append(p)

    orgs_raw = frappe.get_all(
        "RN Organization", filters={"name": ["in", org_names]} if org_names else {},
        fields=["name", "title", "organization_type", "verification_status",
                "trust_level", "trusted_verifier_count", "status", "modified"],
        limit_page_length=500,
    )

    orgs = []
    posko_aktif_total = 0
    pending_total = 0
    anggota_total = 0

    for o in orgs_raw:
        org_poskos = posko_by_org.get(o.name, [])
        posko_list = [
            {"name": p.name, "title": p.title, "posko_type": p.posko_type,
             "status": p.operational_status, "verification_status": p.verification_status,
             "href": "posko-detail.html?id=" + p.name + "&event=" + (event or "")}
            for p in org_poskos
        ]
        active_poskos = sum(1 for p in org_poskos if str(p.operational_status or "").lower() not in _POSKO_INACTIVE_TERMS)
        posko_aktif_total += active_poskos

        members = _org_member_count(o.name)
        anggota_total += members
        programs = _org_program_count(o.name)

        org_pending = str(o.verification_status or "") in _ORG_PENDING_TERMS
        posko_pending = sum(1 for p in org_poskos if str(p.verification_status or "") in _ORG_PENDING_TERMS)
        pending_total += posko_pending + (1 if org_pending else 0)

        orgs.append({
            "name": o.name, "title": o.title, "organization_type": o.organization_type,
            "verification_status": o.verification_status or "self_reported",
            "trust_level": o.trust_level or "unverified",
            "trusted_verifier_count": o.trusted_verifier_count or 0,
            "status": o.status or "active",
            "modified": o.modified,
            "posko_count": len(org_poskos), "posko_active_count": active_poskos,
            "member_count": members, "program_count": programs,
            "poskos": posko_list,
        })

    orgs.sort(key=lambda r: -r["posko_count"])

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "organisasi_aktif": sum(1 for o in orgs if o["status"] == "active" or o["verification_status"] not in _ORG_PENDING_TERMS),
            "posko_aktif": posko_aktif_total,
            "pending_verifikasi": pending_total,
            "anggota_terdaftar": anggota_total,
        },
        "tree": {
            "event": event,
            "orgs": [{"name": o["name"], "title": o["title"], "posko_count": o["posko_count"],
                      "verification_status": o["verification_status"], "poskos": o["poskos"]}
                     for o in orgs],
        },
        "orgs": orgs,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def org_detail(organization):
    """Detail rail for one organisasi — real fields + poskos + a simple
    member list (best-effort: RN User Account rows with this organization,
    since RN Organization Membership is sparsely populated in the seed
    data) + real RN Donor Program rows."""
    org = frappe.db.get_value(
        "RN Organization", organization,
        ["name", "title", "organization_type", "verification_status", "trust_level",
         "trusted_verifier_count", "identity_verification_status", "contact_person",
         "notes", "modified"],
        as_dict=True,
    )
    if not org:
        frappe.throw("Organisasi tidak ditemukan")

    poskos = frappe.get_all(
        "RN Posko", filters={"organization": organization},
        fields=["name", "title", "posko_type", "operational_status", "verification_status"],
        limit_page_length=200,
    )

    members = frappe.get_all(
        "RN User Account", filters={"organization": organization},
        fields=["name", "title", "role", "status"], limit_page_length=200,
    )

    programs = frappe.get_all(
        "RN Donor Program", filters={"owner_type": "organization", "owner_id": organization},
        fields=["name", "program_name", "status", "target_amount", "current_amount", "target_unit"],
        limit_page_length=200,
    )

    checklist = {
        "identitas_organisasi": bool(org.get("verification_status") not in _ORG_PENDING_TERMS),
        "kontak_person": bool(org.get("contact_person")),
        "trusted_verifier": bool((org.get("trusted_verifier_count") or 0) > 0),
    }

    return {
        "org": org,
        "poskos": poskos,
        "members": members,
        "programs": programs,
        "checklist": checklist,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_verification_checklist(posko):
    """Real checklist for the mock-up's "Status Verifikasi Posko" panel —
    every item is a literal field-filled check, not a fabricated status."""
    doc = frappe.db.get_value(
        "RN Posko", posko,
        ["name", "officer_in_charge_email", "officer_in_charge_phone",
         "officer_in_charge_name", "latitude", "longitude",
         "trusted_verifier_count", "verification_status"],
        as_dict=True,
    )
    if not doc:
        frappe.throw("Posko tidak ditemukan")

    items = [
        {"key": "email", "label": "Email", "value": doc.officer_in_charge_email,
         "done": bool(doc.officer_in_charge_email)},
        {"key": "phone", "label": "Nomor HP", "value": doc.officer_in_charge_phone,
         "done": bool(doc.officer_in_charge_phone)},
        {"key": "pic", "label": "Identitas PIC", "value": doc.officer_in_charge_name,
         "done": bool(doc.officer_in_charge_name)},
        {"key": "location", "label": "Lokasi Posko",
         "value": (f"{doc.latitude}, {doc.longitude}" if doc.latitude and doc.longitude else None),
         "done": bool(doc.latitude and doc.longitude)},
        {"key": "trusted_verifier", "label": "Trusted Verifier",
         "value": doc.trusted_verifier_count, "done": bool((doc.trusted_verifier_count or 0) > 0)},
    ]

    # The PIC's email / phone / name are shown only to viewers who may see
    # the PIC (posko_detail's rule); everyone else gets the done-flags.
    from rescue_net.access_policy import rn_actor
    from rescue_net.visibility import posko_contacts_visible
    if not posko_contacts_visible(doc.name, rn_actor(required=False)):
        for item in items:
            if item["key"] in ("email", "phone", "pic"):
                item["value"] = None

    return {
        "posko": doc.name,
        "verification_status": doc.verification_status or "self_reported",
        "items": items,
        "ready_to_submit": all(i["done"] for i in items[:4]),  # trusted_verifier comes after submission
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_registry_board(disaster_event=None, limit=200):
    """KPI totals + Daftar Posko table for the mock-up, guest read-only."""
    event = canonical_event(disaster_event) if disaster_event else None
    filters = {"disaster_event": event} if event else {}

    rows = frappe.get_all(
        "RN Posko", filters=filters,
        fields=_sf("RN Posko", ["name", "title", "posko_type", "address", "city_name",
                "organization", "officer_in_charge_name", "rn_beneficiary_count",
                "verification_status", "trusted_verifier_count",
                "operational_status", "modified"]),
        order_by="modified desc", limit_page_length=int(limit),
    )

    org_titles = {}
    _org_ids = sorted({r.get("organization") for r in rows if r.get("organization")})
    if _org_ids:
        org_titles = {
            o.name: o.title
            for o in frappe.get_all(
                "RN Organization", filters={"name": ["in", _org_ids]},
                fields=["name", "title"], limit_page_length=len(_org_ids),
            )
        }

    def _cap(r):
        try:
            return int(r.get("rn_beneficiary_count") or 0)
        except (TypeError, ValueError):
            return 0

    posko_list = [{
        "name": r.name, "title": r.title, "jenis": r.posko_type,
        "lokasi": r.city_name or r.address or "-",
        "pic": r.officer_in_charge_name or "-",
        "kapasitas": _cap(r),
        "organization": r.get("organization") or None,
        "organization_title": org_titles.get(r.get("organization")) if r.get("organization") else None,
        "status_verifikasi": r.verification_status or "self_reported",
        "trusted_verifier_count": r.trusted_verifier_count or 0,
        "terakhir_diperbarui": r.modified,
        "href": "registrasi-posko.html?id=" + r.name + "&event=" + (event or ""),
    } for r in rows]

    verif_counts = {"pending": 0, "official_verified": 0, "community_verified": 0}
    for r in rows:
        v = str(r.verification_status or "self_reported").lower()
        if v in ("pending", "self_reported", "", "needs_correction"):
            verif_counts["pending"] += 1
        elif v == "community_verified":
            verif_counts["community_verified"] += 1
        elif v in ("official_verified", "verified"):
            verif_counts["official_verified"] += 1

    return {
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "totals": {
            "posko_aktif": sum(1 for r in rows if str(r.operational_status or "").lower() not in _POSKO_INACTIVE_TERMS),
            "pending_verification": verif_counts["pending"],
            "official_verified": verif_counts["official_verified"],
            "community_verified": verif_counts["community_verified"],
        },
        "poskos": posko_list,
    }


def _org_brand(org):
    """Light per-organisation skin for the internal-coordination view.

    Prefers the org's own `brand_color` / `brand_logo` (editable in Desk);
    falls back to a small known-accent map, then to a deterministic hue
    derived from the org name — stable per org, never random.
    """
    if not org:
        return {"title": "Organisasi", "accent": "#3355aa", "initial": "?", "logo": None}

    name = org.get("name") or ""
    accent = (org.get("brand_color") or "").strip() or _ORG_BRAND_ACCENT.get(name)
    if not accent:
        h = 0
        for ch in name:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        accent = "hsl(%d, 45%%, 38%%)" % (h % 360)

    title = (org.get("title") or name or "Organisasi").replace("[SIMULASI] ", "").strip()
    return {
        "title": title,
        "accent": accent,
        "logo": (org.get("brand_logo") or "").strip() or None,
        "organization_type": org.get("organization_type") or "",
        "initial": (title[:1] or "?").upper(),
    }


def _org_brand_row(org_name):
    if not org_name:
        return None
    try:
        return frappe.db.get_value(
            "RN Organization", org_name, _ORG_BRAND_FIELDS, as_dict=True
        )
    except Exception:
        # brand_* columns may not exist yet (pre-migrate) — degrade gracefully
        return frappe.db.get_value(
            "RN Organization", org_name,
            [f for f in _ORG_BRAND_FIELDS if not f.startswith("brand_")],
            as_dict=True,
        )


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def posko_edit_scope(posko=None, disaster_event=None):
    """Tell a posko operational page how to scope itself for the viewer.

    Guests / non-members / System Managers / operators OR APPROVED MEMBERS of
    the shown posko's org are left unrestricted (`can_edit_current: true` —
    same bar as `logistik_board.can_manage` and `api_logistics._can_contribute`,
    which let an approved org member write). A logged-in org member viewing
    ANOTHER org's posko gets `can_edit_current: false` so the page hides its
    create/record forms and shows a read-only banner (relabelled "Koordinasi"
    when `can_coordinate_current`); `my_poskos` / `primary_posko` drive the
    "default to my own posko" redirect.
    """
    from rescue_net.access_policy import rn_actor, is_system_manager

    event = canonical_event(disaster_event) if disaster_event else None
    posko = _resolve_posko(posko) if posko else None

    out = {
        "logged_in": False,
        "is_org_member": False,
        "is_system_manager": False,
        "current_posko": posko,
        "can_edit_current": True,
        "can_coordinate_current": False,
        "my_poskos": [],
        "primary_posko": None,
        "brand": None,
        "coordination_href": "koordinasi-organisasi.html?event=" + (event or ""),
        "control_centre_href": "war-room.html?event=" + (event or ""),
    }

    actor = rn_actor(required=False)
    if not actor:
        return out
    out["logged_in"] = True

    if actor.get("role") == "system_manager" or is_system_manager():
        out["is_system_manager"] = True
        return out

    org_name = actor.get("organization")
    out["is_org_member"] = bool(org_name)
    if not org_name:
        return out  # logged-in donor / volunteer etc. — not scoped here

    out["brand"] = _org_brand(_org_brand_row(org_name))

    names = _my_posko_names(actor)
    if names:
        rows = frappe.get_all(
            "RN Posko", filters={"name": ["in", list(names)]},
            fields=["name", "title", "posko_type", "disaster_event"],
            limit_page_length=50,
        )
        out["my_poskos"] = [{
            "name": r.name,
            "title": (r.title or "").replace("[SIMULASI] ", "").strip(),
            "posko_type": r.posko_type,
            "operate_href": _operate_href(r, event),
        } for r in rows]
    out["primary_posko"] = actor.get("posko") or (
        out["my_poskos"][0]["name"] if out["my_poskos"] else None
    )

    if posko:
        # align with logistik_board.can_manage (share reason ∈ owner set,
        # incl. plain org membership) — the write endpoints already allow it
        _, can_mng, _ = _posko_actor_flags(posko, actor)
        out["can_edit_current"] = can_mng
        if not can_mng:
            pp, ag = frappe.db.get_value(
                "RN Posko", posko, ["public_participation", "accept_goods"]
            ) or (0, 0)
            # a member of another org may still send goods to a posko that
            # opened participation — the page keeps just that one form.
            # Same gate as api_logistics.create_aid_offer's public_ok.
            coord = bool(pp and ag)
            if coord:
                try:
                    from rescue_net.access_policy import public_posko_allowed
                    coord = bool(public_posko_allowed(posko))
                except Exception:
                    coord = False
            out["can_coordinate_current"] = coord

    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def my_org_coordination(disaster_event=None):
    """Internal-organisation coordination board for a logged-in org member."""
    from urllib.parse import quote as _urlquote

    from rescue_net.access_policy import rn_actor, can_manage_posko
    from rescue_net.visibility import effective_posko_share

    event = canonical_event(disaster_event) if disaster_event else None
    cc_href = "war-room.html?event=" + (event or "")

    actor = rn_actor(required=False)
    if not actor or not actor.get("name"):
        return {
            "logged_in": bool(actor),
            "is_org_member": False,
            "disaster_event": event,
            "control_centre_href": cc_href,
            "login_href": "auth.html?next=" + _urlquote(
                "koordinasi-organisasi.html" + (("?event=" + event) if event else "")
            ),
        }

    org_name = actor.get("organization")
    my_posko_name = actor.get("posko")

    org = _org_brand_row(org_name) if org_name else None

    posko_fields = ["name", "title", "organization", "posko_type",
                    "operational_status", "city_name", "disaster_event",
                    "public_detail", "verification_status", "trusted_verifier_count"]

    def _card(p, can_edit):
        share = effective_posko_share(p.get("name"), actor)
        return {
            "name": p.get("name"),
            "title": (p.get("title") or "").replace("[SIMULASI] ", "").strip(),
            "posko_type": p.get("posko_type"),
            "operational_status": p.get("operational_status") or "normal",
            "organization": p.get("organization"),
            "city_name": p.get("city_name") or "-",
            "disaster_event": p.get("disaster_event"),
            "verification_status": p.get("verification_status") or "self_reported",
            "trusted_verifier_count": p.get("trusted_verifier_count") or 0,
            "share_mode": share["mode"],
            "share_reason": share["reason"],
            "can_edit": bool(can_edit),
            "detail_href": "posko-detail.html?id=" + p.get("name")
                           + "&event=" + (event or p.get("disaster_event") or ""),
            "operate_href": _operate_href(p, event),
        }

    # --- my organisation's poskos -----------------------------------------
    my_posko = None
    my_org_poskos = []
    if org_name:
        of = {"organization": org_name}
        if event:
            of["disaster_event"] = event
        rows = frappe.get_all("RN Posko", filters=of, fields=posko_fields,
                              order_by="title asc", limit_page_length=300)
        for p in rows:
            card = _card(p, can_manage_posko(actor, p.get("name")))
            if my_posko_name and p.get("name") == my_posko_name:
                my_posko = card
            else:
                my_org_poskos.append(card)

    # assigned posko might sit under another event / not match the filter
    if my_posko is None and my_posko_name:
        p = frappe.db.get_value("RN Posko", my_posko_name,
                                posko_fields, as_dict=True)
        if p:
            my_posko = _card(p, can_manage_posko(actor, my_posko_name))

    # --- other orgs' poskos that share full detail -----------------------
    ef = {"disaster_event": event} if event else {}
    ext_rows = frappe.get_all("RN Posko", filters=ef, fields=posko_fields,
                              limit_page_length=800)
    open_external = []
    for p in ext_rows:
        if org_name and p.get("organization") == org_name:
            continue
        if p.get("name") == my_posko_name:
            continue
        if effective_posko_share(p.get("name"), actor)["mode"] != "full":
            continue
        open_external.append(_card(p, False))
    open_external.sort(key=lambda c: (c["organization"] or "", c["title"] or ""))

    org_count = len(my_org_poskos) + (1 if my_posko else 0)
    return {
        "logged_in": True,
        "is_org_member": bool(org_name),
        "disaster_event": event,
        "generated_at": frappe.utils.now_datetime(),
        "actor": {
            "user_account": actor.get("name"),
            "role": actor.get("role"),
            "organization": org_name,
            "posko": my_posko_name,
        },
        "organization": org,
        "brand": _org_brand(org),
        "my_posko": my_posko,
        "my_org_poskos": my_org_poskos,
        "open_external_poskos": open_external,
        "totals": {
            "org_posko_count": org_count,
            "open_external_count": len(open_external),
            "editable_count": (1 if (my_posko and my_posko["can_edit"]) else 0)
                              + sum(1 for c in my_org_poskos if c["can_edit"]),
        },
        "control_centre_href": cc_href,
    }
