"""External verifier network — independent / warga poskos become credible when
a verifier in their wilayah endorses them.

A verifier is a government officer OR a willing public figure (lurah, kapolsek,
tokoh masyarakat, ...). Onboarding is by System Manager or by an existing
trusted verifier vouching (member-get-member). Verification of a posko is done
either by a site visit or a network vouch ("via kenalan dia").

DocTypes: RN Verifier Profile / RN Verification Request /
RN Verification Endorsement / RN Verification Action.
"""

import frappe
from frappe.utils import now_datetime, cint

from rescue_net.access_policy import rn_actor, is_system_manager, can_manage_posko


# --- helpers --------------------------------------------------------------

def _actor(required=True):
    return rn_actor(required=required)


def _my_verifier(actor, statuses=("active",)):
    if not actor or not actor.get("name"):
        return None
    row = frappe.db.get_value(
        "RN Verifier Profile",
        {"user": actor.name},
        ["name", "title", "verifier_type", "wilayah", "verifier_status",
         "trust_level", "endorsement_count"],
        as_dict=True,
    )
    if not row:
        return None
    if statuses and row.verifier_status not in statuses:
        row["_inactive"] = True
    return row


def _wilayah_of_posko(posko):
    p = frappe.db.get_value(
        "RN Posko", posko,
        ["village_name", "district_name", "city_name", "province_name", "address"],
        as_dict=True,
    ) or {}
    parts = [p.get("village_name"), p.get("district_name"), p.get("city_name")]
    label = ", ".join([x for x in parts if x]) or (p.get("city_name") or p.get("address") or "")
    return label, p


def _wilayah_match(verifier_wilayah, target_wilayah):
    """Loose containment match either direction (kelurahan ⊂ kecamatan ⊂ kota)."""
    a = (verifier_wilayah or "").strip().lower()
    b = (target_wilayah or "").strip().lower()
    if not a or not b:
        return False
    a_toks = {t.strip() for t in a.replace(",", " ").split() if len(t.strip()) > 2}
    b_toks = {t.strip() for t in b.replace(",", " ").split() if len(t.strip()) > 2}
    return bool(a_toks & b_toks)


def _active_endorsements(posko):
    return frappe.get_all(
        "RN Verification Endorsement",
        filters={"target_type": "posko", "target_id": posko, "status": "active"},
        fields=["name", "verifier", "verifier_display_name", "verifier_role",
                "method", "vouched_via", "statement", "verification_level", "verified_at"],
        order_by="verified_at desc", limit_page_length=100,
    )


def _recompute_posko_credibility(posko):
    """trusted_verifier_count + verification_status from active endorsements."""
    ends = _active_endorsements(posko)
    n = len(ends)

    gov = False
    for e in ends:
        if not e.verifier:
            continue
        vt = frappe.db.get_value("RN Verifier Profile", e.verifier, "verifier_type")
        tl = cint(frappe.db.get_value("RN Verifier Profile", e.verifier, "trust_level"))
        if vt == "government" and tl >= 2:
            gov = True
            break

    cur = frappe.db.get_value("RN Posko", posko, "verification_status") or "self_reported"
    new = cur
    if n == 0:
        if cur in ("community_verified", "official_verified"):
            new = "self_reported"
    elif gov or n >= 2:
        new = "official_verified"
    else:
        new = "community_verified"

    updates = {"trusted_verifier_count": n}
    if new != cur:
        updates["verification_status"] = new
    frappe.db.set_value("RN Posko", posko, updates)
    return {"trusted_verifier_count": n, "verification_status": new}


def _audit(object_type, object_id, action_type, status=None, notes=None, actor=None):
    try:
        doc = frappe.new_doc("RN Verification Action")
        doc.title = f"{action_type} {object_type} {object_id}"[:140]
        doc.object_type = object_type
        doc.object_id = object_id
        doc.action_type = action_type
        doc.verification_status = status
        doc.reviewed_by = (actor or {}).get("name") if actor else frappe.session.user
        doc.reviewer_role = (actor or {}).get("role") if actor else None
        doc.review_notes = notes
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="rn_verifier _audit failed")


# --- become / list verifiers -------------------------------------------------

@frappe.whitelist()
def apply_as_verifier(
    display_name,
    verifier_type,
    wilayah,
    position_title=None,
    public_role_description=None,
    phone=None,
    email=None,
    sponsor_verifier=None,
):
    """Anyone logged in can apply to be a verifier. Status starts `pending`
    until a System Manager or a sponsoring verifier approves."""
    actor = _actor()

    if frappe.db.exists("RN Verifier Profile", {"user": actor.name}):
        frappe.throw("Anda sudah terdaftar sebagai verifikator.")

    display_name = str(display_name or "").strip()
    wilayah = str(wilayah or "").strip()
    if not display_name or not wilayah:
        frappe.throw("Nama dan wilayah layanan wajib diisi.")
    if verifier_type not in ("government", "community_leader", "religious_leader",
                             "professional", "public_figure", "other"):
        verifier_type = "public_figure"

    sponsor = None
    if sponsor_verifier and frappe.db.exists(
        "RN Verifier Profile", {"name": sponsor_verifier, "verifier_status": "active"}
    ):
        sponsor = sponsor_verifier

    doc = frappe.new_doc("RN Verifier Profile")
    doc.title = display_name
    doc.user = actor.name
    doc.verifier_type = verifier_type
    doc.position_title = position_title
    doc.public_role_description = public_role_description
    doc.wilayah = wilayah
    doc.phone = phone
    doc.email = email
    doc.verifier_status = "pending"
    doc.trust_level = 0
    doc.sponsor_verifier = sponsor
    doc.insert(ignore_permissions=True)

    _audit("verifier", doc.name, "apply", "pending", actor=actor)
    return {"verifier": doc.name, "verifier_status": doc.verifier_status,
            "has_sponsor": bool(sponsor)}


@frappe.whitelist(allow_guest=True)
def verifier_directory(wilayah=None, status="active", limit=200):
    """Public list of verifiers (optionally filtered by wilayah substring)."""
    filters = {}
    if status:
        filters["verifier_status"] = status
    rows = frappe.get_all(
        "RN Verifier Profile", filters=filters,
        fields=["name", "title", "verifier_type", "position_title",
                "public_role_description", "wilayah", "verifier_status",
                "trust_level", "endorsement_count", "organization"],
        order_by="trust_level desc, endorsement_count desc",
        limit_page_length=cint(limit) or 200,
    )
    if wilayah:
        rows = [r for r in rows if _wilayah_match(r.wilayah, wilayah)] or rows
    return {"verifiers": rows, "count": len(rows)}


@frappe.whitelist()
def approve_verifier(verifier, action="approve", trust_level=None, note=None):
    """System Manager, or an active verifier with trust_level>=2 (as sponsor),
    approves / suspends / revokes a verifier profile."""
    actor = _actor()
    doc = frappe.get_doc("RN Verifier Profile", verifier)

    sm = is_system_manager()
    mine = _my_verifier(actor)
    can_sponsor = bool(mine and not mine.get("_inactive") and cint(mine.get("trust_level")) >= 2)
    if not (sm or can_sponsor):
        frappe.throw("Hanya System Manager atau verifikator senior yang dapat menyetujui.",
                     frappe.PermissionError)

    action = str(action or "").strip().lower()
    if action not in ("approve", "suspend", "revoke", "reject"):
        frappe.throw("Aksi tidak valid (approve/suspend/revoke/reject).")

    if action == "approve":
        doc.verifier_status = "active"
        doc.approved_by = actor.name
        doc.approved_at = now_datetime()
        if trust_level not in (None, ""):
            tl = max(0, min(5, cint(trust_level)))
        elif can_sponsor and not sm:
            tl = max(1, cint(mine.get("trust_level")) - 1)  # sponsee starts below sponsor
            if not doc.sponsor_verifier:
                doc.sponsor_verifier = mine["name"]
        else:
            tl = max(1, cint(doc.trust_level))
        doc.trust_level = tl
    elif action == "reject":
        doc.verifier_status = "revoked"
    elif action == "suspend":
        doc.verifier_status = "suspended"
    else:
        doc.verifier_status = "revoked"

    if note:
        doc.notes = ((doc.notes + "\n") if doc.notes else "") + str(note)[:400]
    doc.save(ignore_permissions=True)
    _audit("verifier", doc.name, action, doc.verifier_status, note, actor)
    return {"verifier": doc.name, "verifier_status": doc.verifier_status,
            "trust_level": doc.trust_level}


# --- posko asks a verifier -------------------------------------------------

@frappe.whitelist()
def request_posko_verification(posko, verifier=None, method="site_visit", note=None):
    """An independent posko's operator asks a wilayah verifier to endorse it."""
    actor = _actor()
    if not (is_system_manager() or can_manage_posko(actor, posko)):
        frappe.throw("Anda bukan pengelola posko ini.", frappe.PermissionError)

    if not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko tidak ditemukan.")

    method = method if method in ("site_visit", "network_vouch") else "site_visit"
    wilayah, _p = _wilayah_of_posko(posko)

    if verifier:
        v = frappe.db.get_value("RN Verifier Profile", verifier,
                                ["name", "verifier_status"], as_dict=True)
        if not v or v.verifier_status != "active":
            frappe.throw("Verifikator tidak aktif / tidak ditemukan.")

    dup = frappe.db.exists("RN Verification Request", {
        "object_type": "posko", "object_id": posko,
        "status": ["in", ["pending", "accepted"]],
        "verifier": verifier or "",
    })
    if dup:
        return {"request": dup, "status": "pending", "duplicate": True}

    doc = frappe.new_doc("RN Verification Request")
    title_posko = frappe.db.get_value("RN Posko", posko, "title") or posko
    doc.title = f"Verifikasi: {title_posko}"[:140]
    doc.object_type = "posko"
    doc.object_id = posko
    doc.requested_by = actor.name
    doc.verifier = verifier
    doc.method = method
    doc.wilayah = wilayah
    doc.status = "pending"
    doc.notes = note
    doc.insert(ignore_permissions=True)
    _audit("posko", posko, "request_verification", "pending", note, actor)
    return {"request": doc.name, "status": doc.status, "wilayah": wilayah}


@frappe.whitelist()
def my_verification_requests():
    """Verification requests for poskos the caller manages + the list of
    poskos they manage (so the request form can offer a first request)."""
    actor = _actor()
    from rescue_net.api_control_centre import _my_posko_names
    sm = is_system_manager()
    names = list(_my_posko_names(actor)) if not sm else None

    my_poskos = []
    if names:
        for p in frappe.get_all(
            "RN Posko", filters={"name": ["in", names]},
            fields=["name", "title", "verification_status", "trusted_verifier_count",
                    "city_name", "district_name"],
            limit_page_length=100,
        ):
            my_poskos.append(p)
    elif sm:
        my_poskos = frappe.get_all(
            "RN Posko",
            fields=["name", "title", "verification_status", "trusted_verifier_count",
                    "city_name", "district_name"],
            order_by="modified desc", limit_page_length=200,
        )

    filters = {"object_type": "posko"}
    if names is not None:
        if not names:
            return {"requests": [], "my_poskos": []}
        filters["object_id"] = ["in", names]

    rows = frappe.get_all(
        "RN Verification Request", filters=filters,
        fields=["name", "object_id", "verifier", "method", "wilayah", "status",
                "notes", "creation"],
        order_by="creation desc", limit_page_length=200,
    )
    for r in rows:
        r["posko_title"] = frappe.db.get_value("RN Posko", r.object_id, "title")
        if r.verifier:
            r["verifier_title"] = frappe.db.get_value("RN Verifier Profile", r.verifier, "title")
    return {"requests": rows, "my_poskos": my_poskos}


# --- verifier acts -------------------------------------------------------

@frappe.whitelist()
def verifier_inbox():
    """For the caller's active verifier profile: requests aimed at them +
    open requests in their wilayah."""
    actor = _actor()
    mine = _my_verifier(actor)
    if not mine or mine.get("_inactive"):
        return {"is_verifier": bool(mine), "verifier_status":
                (mine or {}).get("verifier_status"), "requests": []}

    direct = frappe.get_all(
        "RN Verification Request",
        filters={"verifier": mine["name"], "status": ["in", ["pending", "accepted"]]},
        fields=["name", "object_type", "object_id", "requested_by", "method",
                "wilayah", "status", "notes", "creation"],
        order_by="creation desc", limit_page_length=200,
    )
    seen = {r.name for r in direct}
    openreq = frappe.get_all(
        "RN Verification Request",
        filters={"verifier": ["in", ["", None]], "status": "pending"},
        fields=["name", "object_type", "object_id", "requested_by", "method",
                "wilayah", "status", "notes", "creation"],
        order_by="creation desc", limit_page_length=300,
    )
    openreq = [r for r in openreq if r.name not in seen and _wilayah_match(mine.get("wilayah"), r.wilayah)]

    for r in direct + openreq:
        if r.object_type == "posko":
            r["posko_title"] = frappe.db.get_value("RN Posko", r.object_id, "title")

    return {
        "is_verifier": True,
        "verifier": mine,
        "direct_requests": direct,
        "wilayah_open_requests": openreq,
    }


@frappe.whitelist()
def endorse_posko(request=None, posko=None, method=None, statement=None,
                  vouched_via=None, verification_level=1):
    """An active verifier endorses a posko (from a request or directly)."""
    actor = _actor()
    mine = _my_verifier(actor)
    if is_system_manager() and not mine:
        frappe.throw("System Manager tidak punya profil verifikator; buat dulu via apply_as_verifier.")
    if not mine or mine.get("_inactive"):
        frappe.throw("Hanya verifikator aktif yang dapat memberi endorsement.", frappe.PermissionError)

    req = None
    if request:
        req = frappe.get_doc("RN Verification Request", request)
        posko = posko or req.object_id
        method = method or req.method
    if not posko or not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko tidak ditemukan.")

    method = method if method in ("site_visit", "network_vouch", "document_review") else "site_visit"
    if method == "network_vouch" and not (vouched_via and str(vouched_via).strip()):
        frappe.throw("Untuk 'network vouch', isi 'direkomendasikan via' (nama kenalan / verifikator).")

    if frappe.db.exists("RN Verification Endorsement", {
        "target_type": "posko", "target_id": posko,
        "verifier": mine["name"], "status": "active",
    }):
        frappe.throw("Anda sudah meng-endorse posko ini.")

    posko_title = frappe.db.get_value("RN Posko", posko, "title") or posko
    doc = frappe.new_doc("RN Verification Endorsement")
    doc.title = f"Endorsement: {posko_title}"[:140]
    doc.request = req.name if req else None
    doc.target_type = "posko"
    doc.target_id = posko
    doc.verifier = mine["name"]
    doc.verifier_display_name = mine["title"]
    doc.verifier_role = mine.get("verifier_type")
    doc.method = method
    doc.vouched_via = vouched_via
    doc.verification_scope = "posko_credibility"
    doc.verification_level = max(1, min(5, cint(verification_level)))
    doc.statement = statement
    doc.status = "active"
    doc.visible_on_profile = 1
    doc.verified_at = now_datetime()
    doc.insert(ignore_permissions=True)

    if req:
        req.status = "completed"
        req.save(ignore_permissions=True)

    frappe.db.set_value("RN Verifier Profile", mine["name"], "endorsement_count",
                        cint(mine.get("endorsement_count")) + 1)
    cred = _recompute_posko_credibility(posko)
    _audit("posko", posko, "endorse:" + method, cred["verification_status"],
           statement, actor)

    return {
        "endorsement": doc.name,
        "posko": posko,
        "method": method,
        "trusted_verifier_count": cred["trusted_verifier_count"],
        "verification_status": cred["verification_status"],
    }


@frappe.whitelist()
def revoke_endorsement(endorsement, reason=None):
    actor = _actor()
    doc = frappe.get_doc("RN Verification Endorsement", endorsement)
    mine = _my_verifier(actor, statuses=None)
    if not (is_system_manager() or (mine and doc.verifier == mine["name"])):
        frappe.throw("Anda tidak dapat mencabut endorsement ini.", frappe.PermissionError)

    doc.status = "revoked"
    doc.revoked_at = now_datetime()
    doc.revoked_by = actor.name
    doc.revoke_reason = reason
    doc.save(ignore_permissions=True)

    if doc.target_type == "posko":
        cred = _recompute_posko_credibility(doc.target_id)
        _audit("posko", doc.target_id, "revoke_endorsement",
               cred["verification_status"], reason, actor)
        return {"endorsement": doc.name, "status": "revoked", **cred}
    return {"endorsement": doc.name, "status": "revoked"}


@frappe.whitelist(allow_guest=True)
def posko_verification_public(posko):
    """Guest-readable credibility panel for a posko."""
    p = frappe.db.get_value(
        "RN Posko", posko,
        ["name", "title", "verification_status", "trusted_verifier_count",
         "public_verified_badge", "city_name", "district_name"],
        as_dict=True,
    )
    if not p:
        return {"found": False}
    ends = _active_endorsements(posko)
    for e in ends:
        e.pop("statement", None) if False else None
    return {
        "found": True,
        "posko": p.name,
        "title": p.title,
        "verification_status": p.verification_status or "self_reported",
        "trusted_verifier_count": p.trusted_verifier_count or 0,
        "endorsements": [
            {
                "verifier": e.verifier_display_name,
                "role": e.verifier_role,
                "method": e.method,
                "vouched_via": e.vouched_via,
                "statement": e.statement,
                "verified_at": e.verified_at,
            } for e in ends
        ],
    }
