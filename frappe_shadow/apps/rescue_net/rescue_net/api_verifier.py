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
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, cint

from rescue_net.access_policy import rn_actor, is_system_manager, can_manage_posko
from rescue_net.services import reporter


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


def _manages_target(user_account, posko):
    """True when the account runs the posko or belongs to its organisation."""
    from rescue_net.access_policy import approved_member, approved_posko_assignment
    if not user_account or not posko:
        return False
    if approved_posko_assignment(user_account, posko):
        return True
    org = frappe.db.get_value("RN Posko", posko, "organization")
    return bool(org and approved_member(user_account, org))


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
    # VF-3: only endorsements from verifiers that are still active count
    ends = [e for e in _active_endorsements(posko)
            if not e.verifier
            or frappe.db.get_value("RN Verifier Profile", e.verifier, "verifier_status") == "active"]
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

    cur, prev_n = frappe.db.get_value(
        "RN Posko", posko, ["verification_status", "trusted_verifier_count"]) or (None, 0)
    cur = cur or "self_reported"
    new = cur
    if cur in ("rejected", "needs_correction"):
        pass  # a reviewer's decision is not overruled by endorsements
    elif n == 0:
        # only a status that came from endorsements falls back; an official
        # status set by an admin (no endorsements behind it) stays
        if cur in ("community_verified", "official_verified") and cint(prev_n) > 0:
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
@rate_limit(limit=120, seconds=60)
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

    if not sm:
        # VF-6: a sponsor never acts on their own profile, never revives a
        # revoked verifier, and grants less trust than their own
        if doc.name == mine["name"]:
            frappe.throw("Tidak bisa memutuskan profil verifikator Anda sendiri.", frappe.PermissionError)
        if doc.verifier_status == "revoked" and action == "approve":
            frappe.throw("Verifikator yang dicabut hanya bisa diaktifkan lagi oleh System Manager.",
                         frappe.PermissionError)
        if trust_level not in (None, "") and cint(trust_level) >= cint(mine.get("trust_level")):
            frappe.throw("Trust level harus di bawah trust level Anda.", frappe.PermissionError)

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


# --- Pelapor Terverifikasi accounts -----------------------------------------

def _may_decide_reporters(actor):
    if is_system_manager():
        return None
    mine = _my_verifier(actor)
    if not (mine and not mine.get("_inactive") and cint(mine.get("trust_level")) >= 2):
        frappe.throw("Hanya System Manager atau verifikator senior (trust ≥ 2) yang dapat memverifikasi pelapor.",
                     frappe.PermissionError)
    return mine


@frappe.whitelist()
def reporter_requests(include_decided=0):
    """Pending Pelapor Terverifikasi sign-ups (services/reporter.py) for a
    System Manager or a senior verifier; requests in the verifier's own
    wilayah first. Contact + reference are included — the reviewer has to
    reach the person (or their reference) before approving."""
    actor = _actor()
    mine = _may_decide_reporters(actor)
    filters = {"requested_role": reporter.SIGNUP_KEY}
    if not cint(include_decided):
        filters["role_request_status"] = "pending"
    rows = frappe.get_all(
        "RN User Account", filters=filters,
        fields=["name", "title", "email", "phone", "reporter_agency", "reporter_position",
                "reporter_area", "role_request_status", "reporter_verified_by", "creation"],
        order_by="creation desc", limit_page_length=200,
    )
    refs = {}
    for r in frappe.get_all("RN User Reference", filters={"user_account": ["in", [x.name for x in rows] or ["-"]]},
                            fields=["user_account", "reference_name", "reference_relation", "reference_contact", "status"]):
        refs.setdefault(r.user_account, r)
    for r in rows:
        r["reference"] = refs.get(r.name)
        r["in_my_area"] = bool(mine and _wilayah_match(mine.get("wilayah"), r.reporter_area))
    rows.sort(key=lambda r: not r["in_my_area"])
    return {"requests": rows, "count": len(rows)}


@frappe.whitelist()
def decide_reporter(user_account, action="approve", note=None):
    actor = _actor()
    _may_decide_reporters(actor)
    doc = frappe.get_doc("RN User Account", user_account)
    if doc.get("requested_role") != reporter.SIGNUP_KEY:
        frappe.throw("Akun ini tidak meminta role pelapor.")
    if not is_system_manager() and doc.name == actor.name:
        frappe.throw("Tidak bisa memverifikasi akun Anda sendiri.", frappe.PermissionError)
    if doc.get("role_request_status") != "pending":
        frappe.throw(f"Permintaan ini sudah diputuskan ({doc.role_request_status}).")
    action = str(action or "").strip().lower()
    if action == "approve":
        reporter.activate(doc, actor.name or frappe.session.user)
    elif action == "reject":
        doc.role_request_status = "rejected"
    else:
        frappe.throw("Aksi tidak valid (approve/reject).")
    doc.save(ignore_permissions=True)
    _audit("reporter_account", doc.name, action, doc.role_request_status, note, actor)
    return {"user_account": doc.name, "role_request_status": doc.role_request_status, "role": doc.role}


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
        if _manages_target(frappe.db.get_value("RN Verifier Profile", verifier, "user"), posko):
            frappe.throw("Verifikator tidak boleh pengelola / anggota organisasi posko ini.")

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
        # VF-5: the endorsement answers THIS open request for THIS posko
        if req.status not in ("pending", "accepted"):
            frappe.throw(f"Permintaan verifikasi sudah berstatus '{req.status}'.")
        if req.verifier and req.verifier != mine["name"]:
            frappe.throw("Permintaan ini ditujukan ke verifikator lain.", frappe.PermissionError)
        if posko and posko != req.object_id:
            frappe.throw("Posko tidak sesuai dengan permintaan verifikasi.")
        posko = req.object_id
        method = method or req.method
    if not posko or not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko tidak ditemukan.")
    # VF-4: nobody endorses a posko they run or whose organisation they belong to
    if _manages_target(actor.name, posko):
        frappe.throw("Tidak bisa meng-endorse posko yang Anda kelola / organisasi Anda sendiri.",
                     frappe.PermissionError)

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


@frappe.whitelist(methods=["POST"])
def endorse_reporter(user_account, method="site_visit", statement=None, vouched_via=None, verification_level=1):
    """An active verifier (ketua organisasi, aparat, kepala desa, tokoh agama …) vouches for a reporter's
    account. The statement is required: it says how the verifier knows the person."""
    actor = _actor()
    mine = _my_verifier(actor)
    if not mine or mine.get("_inactive"):
        frappe.throw("Hanya verifikator aktif yang dapat memverifikasi pelapor.", frappe.PermissionError)
    if actor.name and actor.name == user_account:
        frappe.throw("Tidak bisa memverifikasi akun Anda sendiri.", frappe.PermissionError)
    target = frappe.db.get_value("RN User Account", user_account, ["name", "status", "title"], as_dict=True)
    if not target or target.status != "active":
        frappe.throw("Akun pelapor tidak ditemukan atau tidak aktif.")
    if len((statement or "").strip()) < 10:
        frappe.throw("Tulis pernyataan singkat: bagaimana Anda mengenal pelapor ini (min. 10 karakter).")
    method = method if method in ("site_visit", "network_vouch", "document_review") else "site_visit"
    if method == "network_vouch" and not (vouched_via and str(vouched_via).strip()):
        frappe.throw("Untuk 'rekomendasi jaringan', isi 'direkomendasikan via' (nama kenalan / verifikator).")
    if frappe.db.exists("RN Verification Endorsement", {
        "target_type": "reporter", "target_id": user_account, "verifier": mine["name"], "status": "active",
    }):
        frappe.throw("Anda sudah memverifikasi pelapor ini.")

    doc = frappe.new_doc("RN Verification Endorsement")
    doc.title = f"Verifikasi pelapor: {target.title or user_account}"[:140]
    doc.target_type = "reporter"
    doc.target_id = user_account
    doc.verifier = mine["name"]
    doc.verifier_display_name = mine["title"]
    doc.verifier_role = mine.get("verifier_type")
    doc.method = method
    doc.vouched_via = vouched_via
    doc.verification_scope = "reporter_identity"
    doc.verification_level = max(1, min(5, cint(verification_level)))
    doc.statement = statement.strip()
    doc.status = "active"
    doc.visible_on_profile = 1
    doc.verified_at = now_datetime()
    doc.insert(ignore_permissions=True)
    frappe.db.set_value("RN Verifier Profile", mine["name"], "endorsement_count",
                        cint(mine.get("endorsement_count")) + 1)
    _audit("reporter", user_account, "endorse:" + method, "active", statement, actor)
    return {"endorsement": doc.name, "user_account": user_account, "method": method}


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
@rate_limit(limit=120, seconds=60)
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


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def endorsements_overview(target_type=None, q=None, status="active", limit=200):
    """Data hasil verifikasi: every endorsement in the Jaringan Verifikator (posko + pelapor), searchable.
    Public like the posko credibility panel: verifier name / position / type are public; a reporter target
    stays 'Pelapor' and a verifier's statement about a reporter is shown only to a System Manager or an
    active verifier."""
    from rescue_net.access_policy import rn_actor
    from rescue_net.services.reporter_contact import METHOD_LABEL, TYPE_LABEL

    actor = rn_actor(required=False)
    privileged = bool(is_system_manager() or (actor and actor.get("name") and _my_verifier(actor)
                                              and not _my_verifier(actor).get("_inactive")))
    mine = _my_verifier(actor) if actor and actor.get("name") else None
    mine_name = mine["name"] if mine and not mine.get("_inactive") else None
    filters = {}
    if target_type in ("posko", "reporter"):
        filters["target_type"] = target_type
    if status in ("active", "revoked", "expired"):
        filters["status"] = status
    rows = frappe.get_all(
        "RN Verification Endorsement", filters=filters,
        fields=["name", "target_type", "target_id", "verifier", "verifier_display_name", "method", "statement",
                "verification_level", "status", "verified_at", "revoked_at"],
        order_by="verified_at desc", limit_page_length=min(cint(limit) or 200, 500))

    verifiers = {v.name: v for v in frappe.get_all(
        "RN Verifier Profile", filters={"name": ["in", list({r.verifier for r in rows if r.verifier})]},
        fields=["name", "title", "verifier_type", "position_title", "wilayah", "verifier_status"], limit_page_length=0)} \
        if rows else {}
    poskos = dict(frappe.get_all(
        "RN Posko", filters={"name": ["in", [r.target_id for r in rows if r.target_type == "posko"]]},
        fields=["name", "title"], as_list=True)) if any(r.target_type == "posko" for r in rows) else {}

    needle = (q or "").strip().lower()
    out = []
    for r in rows:
        v = verifiers.get(r.verifier)
        label = poskos.get(r.target_id, r.target_id) if r.target_type == "posko" else "Pelapor"
        if r.target_type == "reporter" and privileged:
            label = frappe.db.get_value("RN User Account", r.target_id, "title") or "Pelapor"
        item = {
            "endorsement": r.name, "target_type": r.target_type, "target_id": r.target_id if r.target_type == "posko" else None,
            "target": label, "status": r.status,
            "verifier": (v.title if v else r.verifier_display_name), "verifier_id": r.verifier,
            "verifier_type": TYPE_LABEL.get(v.verifier_type, "Verifikator") if v else None,
            "position": v.position_title if v else None, "wilayah": v.wilayah if v else None,
            "method": METHOD_LABEL.get(r.method, r.method), "level": cint(r.verification_level),
            "verified_at": str(r.verified_at)[:10] if r.verified_at else None,
            "revoked_at": str(r.revoked_at)[:10] if r.revoked_at else None,
            "statement": r.statement if (r.target_type == "posko" or privileged) else None,
            "can_revoke": bool(is_system_manager() or (mine_name and r.verifier == mine_name)),
        }
        if needle and needle not in " ".join(str(item.get(k) or "") for k in
                                              ("target", "verifier", "verifier_type", "position", "wilayah", "method", "statement")).lower():
            continue
        out.append(item)
    return {"rows": out, "total": len(out), "privileged": privileged}
