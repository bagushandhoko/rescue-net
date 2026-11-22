"""Kelola Bencana — create, verify and merge disaster events (owner SOP 2026-11-01).

Who may create:
- System Manager / Control Centre, or an approved member of a VERIFIED organisation
  -> the event is active at once (admins get a notice and can demote it).
- Anyone else logged in (unverified organisation, individual) -> `proposed`: hidden
  from the public until a System Manager approves.
Before creating, the form shows events that look like the same disaster (type,
distance, time, name) so people join an existing one instead of making a twin.
Merging is System Manager only, logged, and can be undone.
"""

import json

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_datetime, now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor
from rescue_net.services import event_merge as em
from rescue_net.services.reporter_contact import VERIFIED_ORG

EVENT = em.EVENT
SEVERITIES = ("normal", "medium", "high", "urgent", "critical")
ADMIN_ROLES = {"command_center"}


def _is_admin(actor=None):
    if is_system_manager():
        return True
    actor = actor if actor is not None else rn_actor(required=False)
    return bool(actor and actor.get("role") in ADMIN_ROLES)


def _require_super_admin():
    """Verify / merge / undo: System Manager (super admin) only."""
    if not is_system_manager():
        frappe.throw("Hanya super admin yang dapat melakukan ini.", frappe.PermissionError)


def _verified_orgs(actor):
    """Verified organisations where the actor is an approved member."""
    if not actor or not actor.get("name"):
        return []
    orgs = frappe.get_all("RN Organization Membership",
                          filters={"user_account": actor.name, "status": "approved"}, pluck="organization")
    out = []
    for o in set(orgs):
        vs = str(frappe.db.get_value("RN Organization", o, "verification_status") or "").lower()
        if vs in VERIFIED_ORG:
            out.append(o)
    return sorted(out)


def _member_orgs(actor):
    if not actor or not actor.get("name"):
        return []
    return sorted(set(frappe.get_all("RN Organization Membership",
                                     filters={"user_account": actor.name, "status": "approved"},
                                     pluck="organization")))


def _probe(title=None, event_type=None, latitude=None, longitude=None, location_summary=None, started_at=None):
    return {"title": (title or "").strip(), "event_type": (event_type or "").strip().lower(),
            "latitude": latitude, "longitude": longitude, "location_summary": location_summary,
            "started_at": started_at or now_datetime()}


@frappe.whitelist()
@rate_limit(limit=60, seconds=60)
def create_options():
    """What the form needs: event types, severities, the actor's organisations and
    whether a new event from them goes live at once."""
    actor = rn_actor(required=True)
    verified = _verified_orgs(actor)
    orgs = [{"name": o, "title": frappe.db.get_value("RN Organization", o, "title") or o,
             "verified": o in verified} for o in _member_orgs(actor)]
    return {"event_types": [t for t in em.EVENT_TYPES], "severities": list(SEVERITIES), "organizations": orgs,
            "goes_live": bool(_is_admin(actor) or verified), "is_super_admin": is_system_manager()}


@frappe.whitelist()
@rate_limit(limit=60, seconds=60)
def check_duplicates(title=None, event_type=None, latitude=None, longitude=None, location_summary=None,
                     started_at=None):
    """Events that look like the one being typed. Non-admins only see public (active)
    events; admins also see proposals and BMKG drafts."""
    actor = rn_actor(required=True)
    statuses = em.MATCHABLE_STATUSES if _is_admin(actor) else ("active",)
    probe = _probe(title, event_type, latitude, longitude, location_summary, started_at)
    if not (probe["title"] or probe["event_type"] or probe["location_summary"]):
        return {"matches": []}
    return {"matches": em.similar_events(probe, statuses=statuses, min_score=45)}


def create_event_for(actor, title, event_type=None, location_summary=None, latitude=None, longitude=None,
                     started_at=None, severity=None, organization=None, force=0):
    title = (title or "").strip()
    if len(title) < 4:
        frappe.throw("Nama bencana wajib diisi (minimal 4 huruf).")
    event_type = (event_type or "").strip().lower() or em.norm_type(None, title) or "lainnya"
    if event_type not in em.EVENT_TYPES:
        frappe.throw("Jenis bencana tidak dikenal.")
    if not (location_summary or "").strip():
        frappe.throw("Lokasi wajib diisi (kabupaten/kota, provinsi).")
    severity = (severity or "medium").strip().lower()
    if severity not in SEVERITIES:
        frappe.throw("Tingkat keparahan tidak dikenal.")
    lat, lng = em._num(latitude), em._num(longitude)
    if (lat is None) != (lng is None) or (lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180)):
        frappe.throw("Koordinat tidak valid.")
    try:
        started = get_datetime(started_at) if started_at else now_datetime()
    except Exception:
        frappe.throw("Tanggal mulai tidak valid.")

    member_orgs = _member_orgs(actor)
    if organization and organization not in member_orgs and not is_system_manager():
        frappe.throw("Anda bukan anggota organisasi itu.", frappe.PermissionError)
    verified = _verified_orgs(actor)
    org = organization or (verified[0] if verified else (member_orgs[0] if member_orgs else None))
    live = _is_admin(actor) or (org in verified)

    probe = _probe(title, event_type, lat, lng, location_summary, started)
    if not cint(force):
        statuses = em.MATCHABLE_STATUSES if _is_admin(actor) else ("active",)
        twins = [m for m in em.similar_events(probe, statuses=statuses, min_score=70)]
        if twins:
            return {"created": False, "duplicates": twins,
                    "message": "Sepertinya bencana ini sudah ada. Gabung ke bencana yang ada, atau kirim tetap sebagai bencana baru."}

    doc = frappe.get_doc({"doctype": EVENT, "legacy_id": "event-" + frappe.generate_hash(length=12),
                          "legacy_source": "kelola-bencana", "migration_status": "Validated",
                          "title": title, "event_type": event_type, "severity": severity,
                          "location_summary": location_summary.strip(), "latitude": lat, "longitude": lng,
                          "started_at": started, "event_status": "active" if live else "proposed",
                          "reporting_organization": org, "created_by_user": frappe.session.user})
    doc.insert(ignore_permissions=True)

    org_title = frappe.db.get_value("RN Organization", org, "title") if org else None
    who = org_title or frappe.session.user
    if live:
        em.notify_admins(f"Bencana baru AKTIF: {title} — oleh {who}. Periksa di Kelola Bencana.")
    else:
        em.notify_admins(f"Usulan bencana menunggu verifikasi: {title} — dari {who}.")
    suggestions = em.suggest_for(doc.name)
    return {"created": True, "name": doc.name, "event_status": doc.event_status, "title": doc.title,
            "merge_suggestions": len(suggestions),
            "message": ("Bencana aktif dan tampil di daftar publik." if live else
                        "Usulan terkirim. Super admin akan memverifikasi; sampai itu bencana belum tampil di publik.")}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def create_event(title=None, event_type=None, location_summary=None, latitude=None, longitude=None,
                 started_at=None, severity=None, organization=None, force=0):
    actor = rn_actor(required=True)
    return create_event_for(actor, title, event_type, location_summary, latitude, longitude, started_at,
                            severity, organization, force)


@frappe.whitelist()
def my_events():
    rows = frappe.get_all(EVENT, filters={"created_by_user": frappe.session.user},
                          fields=["name", "title", "event_status", "event_type", "location_summary", "started_at",
                                  "merged_into", "review_note", "creation"],
                          order_by="creation desc", limit_page_length=50)
    for r in rows:
        if r.merged_into:
            r["merged_into_title"] = frappe.db.get_value(EVENT, r.merged_into, "title")
    return rows


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def resolve_event(event):
    """Old link of a merged event -> the event now in use (public pages redirect).
    Only public outcomes are revealed."""
    from rescue_net.reference_resolver import resolve_reference
    name = resolve_reference(EVENT, event, "disaster_events:")
    if not name or not frappe.db.exists(EVENT, name):
        return {"found": False}
    final = em.final_event(name)
    status = frappe.db.get_value(EVENT, final, "event_status")
    if status in em.HIDDEN_STATUSES and not _is_admin():
        return {"found": False}
    return {"found": True, "name": final, "merged": final != name,
            "title": frappe.db.get_value(EVENT, final, "title")}


# --------------------------------------------------------------------------- #
# super admin                                                                 #
# --------------------------------------------------------------------------- #
def _event_row(name):
    r = frappe.db.get_value(EVENT, name, ["name", "title", "event_status", "event_type", "location_summary",
                                          "started_at", "latitude", "longitude", "reporting_organization",
                                          "created_by_user", "aliases", "reviewed_by", "creation", "severity"],
                            as_dict=True)
    if not r:
        return None
    r = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.items()}
    if r.get("reporting_organization"):
        r["organization_title"] = frappe.db.get_value("RN Organization", r["reporting_organization"], "title")
    return r


def _warning_row(w):
    import json

    try:
        near = json.loads(w.nearby_poskos or "[]")
    except ValueError:
        near = []
    return {"warning": w.name, "title": w.title, "magnitude": w.magnitude, "depth_km": w.depth_km, "area": w.area_desc,
            "potential": w.potential, "issued_at": str(w.issued_at or ""), "status": w.status,
            "nearby_count": len(near), "nearby": near[:8]}


_W_FIELDS = ["name", "title", "magnitude", "depth_km", "area_desc", "potential", "issued_at", "status",
             "nearby_poskos", "latitude", "longitude", "draft_event"]


def _bmkg_drafts():
    """Older BMKG-created draft events (before 2026-11-02 drafts were automatic) — still decidable here."""
    out = []
    for n in frappe.get_all(EVENT, filters={"event_status": "draft"}, order_by="creation desc", pluck="name",
                            limit_page_length=50):
        row = _event_row(n)
        w = frappe.db.get_value("RN Early Warning", {"draft_event": n}, _W_FIELDS, as_dict=True)
        if w:
            row["quake"] = _warning_row(w)
        out.append(row)
    return out


def _bmkg_notices():
    """S13 / owner 2026-11-02: big BMKG quakes are ANNOUNCEMENTS. Listed for the super admin, who may turn
    one into a disaster once it is declared one."""
    rows = frappe.get_all("RN Early Warning", filters={"meets_threshold": 1, "status": ["in", ["new", "acknowledged"]],
                                                       "draft_event": ["in", ["", None]]},
                          fields=_W_FIELDS, order_by="issued_at desc", limit_page_length=20)
    return [_warning_row(w) for w in rows]


@frappe.whitelist(methods=["POST"])
def promote_warning(warning, title=None):
    """Super admin: this BMKG announcement has been declared a disaster → create an active RN Disaster Event."""
    _require_super_admin()
    w = frappe.db.get_value("RN Early Warning", warning, _W_FIELDS + ["identifier", "severity"], as_dict=True)
    if not w:
        frappe.throw("Pengumuman tidak ditemukan.")
    if w.draft_event:
        frappe.throw("Pengumuman ini sudah dijadikan bencana.")
    values = {"doctype": EVENT, "legacy_id": w.identifier, "title": (title or w.title or "").strip()[:140],
              "event_status": "active", "severity": w.severity, "location_summary": w.area_desc,
              "started_at": w.issued_at, "reviewed_by": frappe.session.user, "reviewed_at": now_datetime(),
              "review_note": "Dari pengumuman BMKG " + w.name}
    meta = frappe.get_meta(EVENT)
    for f, v in (("latitude", w.latitude), ("longitude", w.longitude), ("event_type", "gempa")):
        if meta.has_field(f):
            values[f] = v
    if frappe.db.exists(EVENT, w.identifier):
        values.pop("legacy_id")
    ev = frappe.get_doc(values).insert(ignore_permissions=True)
    frappe.db.set_value("RN Early Warning", w.name, {"draft_event": ev.name, "status": "acknowledged"})
    em.suggest_for(ev.name)
    return {"event": ev.name, "title": ev.title}


@frappe.whitelist(methods=["POST"])
def dismiss_warning(warning):
    _require_super_admin()
    if not frappe.db.exists("RN Early Warning", warning):
        frappe.throw("Pengumuman tidak ditemukan.")
    frappe.db.set_value("RN Early Warning", warning, "status", "dismissed")
    return {"warning": warning, "status": "dismissed"}


@frappe.whitelist()
def admin_queue():
    _require_super_admin()
    proposed = [_event_row(n) for n in frappe.get_all(EVENT, filters={"event_status": "proposed"},
                                                         order_by="creation desc", pluck="name")]
    bmkg_drafts = _bmkg_drafts()
    bmkg_notices = _bmkg_notices()
    recent_live = [_event_row(n) for n in frappe.get_all(
        EVENT, filters={"event_status": "active", "legacy_source": "kelola-bencana",
                        "reviewed_by": ["in", ["", None]]}, order_by="creation desc", pluck="name")]
    sugs = []
    for s in frappe.get_all("RN AI Suggestion", filters={"feature": em.FEATURE, "status": "draft"},
                            fields=["name", "payload", "creation"], order_by="creation desc", limit_page_length=50):
        p = json.loads(s.payload or "{}")
        src, tgt = _event_row(p.get("source")), _event_row(p.get("target"))
        if not src or not tgt or src["event_status"] == "merged" or tgt["event_status"] == "merged":
            continue
        sugs.append({"name": s.name, "score": p.get("score"), "reasons": p.get("reasons") or [],
                     "source": src, "target": tgt,
                     "source_counts": em.linked_counts(src["name"]), "target_counts": em.linked_counts(tgt["name"])})
    logs = frappe.get_all("RN Event Merge Log", fields=["name", "source_event", "target_event", "status", "merged_by",
                                                        "merged_at", "moved_count", "undone_at", "undo_note"],
                          order_by="creation desc", limit_page_length=30)
    for lg in logs:
        lg["source_title"] = frappe.db.get_value(EVENT, lg.source_event, "title")
        lg["target_title"] = frappe.db.get_value(EVENT, lg.target_event, "title")
    events = frappe.get_all(EVENT, filters={"event_status": ["in", ["active", "proposed", "draft"]]},
                            fields=["name", "title", "event_status", "is_drill"], order_by="modified desc",
                            limit_page_length=500)
    return {"proposed": proposed, "bmkg_drafts": bmkg_drafts, "bmkg_notices": bmkg_notices, "recent_live": recent_live, "suggestions": sugs, "logs": logs,
            "events": events}


@frappe.whitelist()
def event_counts(event):
    _require_super_admin()
    return {"event": _event_row(event), "counts": em.linked_counts(event)}


@frappe.whitelist(methods=["POST"])
def review_event(event, decision, note=None):
    """approve (proposed -> active), reject (proposed -> rejected), demote (active -> proposed),
    ok (active, mark reviewed)."""
    _require_super_admin()
    row = frappe.db.get_value(EVENT, event, ["event_status", "title", "created_by_user"], as_dict=True)
    if not row:
        frappe.throw("Bencana tidak ditemukan.")
    allowed = {"approve": ("proposed", "draft"), "reject": ("proposed", "draft"), "demote": ("active",),
               "ok": ("active",)}
    if decision not in allowed:
        frappe.throw("Keputusan tidak dikenal.")
    if row.event_status not in allowed[decision]:
        frappe.throw(f"Status bencana sekarang '{row.event_status}', tidak bisa '{decision}'.")
    new_status = {"approve": "active", "reject": "rejected", "demote": "proposed", "ok": "active"}[decision]
    frappe.db.set_value(EVENT, event, {"event_status": new_status, "reviewed_by": frappe.session.user,
                                       "reviewed_at": now_datetime(), "review_note": (note or "")[:500]})
    label = {"approve": "disetujui dan kini aktif", "reject": "ditolak", "demote": "diturunkan ke usulan",
             "ok": "diperiksa"}[decision]
    if decision != "ok":
        em.notify_user(row.created_by_user, f"Bencana '{row.title}' {label}." + (f" Catatan: {note}" if note else ""))
    if row.event_status == "draft":
        w = frappe.db.get_value("RN Early Warning", {"draft_event": event}, "name")
        if decision == "approve" and (row.title or "").startswith("[DRAF BMKG] "):
            frappe.db.set_value(EVENT, event, "title", row.title[len("[DRAF BMKG] "):])
        if w:
            frappe.db.set_value("RN Early Warning", w, "status", "acknowledged" if decision == "approve" else "dismissed")
    if decision == "approve":
        em.suggest_for(event)
    return {"event": event, "event_status": new_status}


@frappe.whitelist(methods=["POST"])
def merge_events(source, target, note=None, suggestion=None):
    _require_super_admin()
    res = em.merge(source, target, frappe.session.user, suggestion=suggestion, note=note)
    if suggestion and frappe.db.exists("RN AI Suggestion", suggestion):
        frappe.db.set_value("RN AI Suggestion", suggestion, {"status": "accepted", "decided_by": frappe.session.user,
                                                             "decided_at": now_datetime()})
    for user in {frappe.db.get_value(EVENT, source, "created_by_user")} - {None, frappe.session.user}:
        em.notify_user(user, "Bencana '%s' digabung ke '%s'." % (frappe.db.get_value(EVENT, source, "title"),
                                                                  frappe.db.get_value(EVENT, target, "title")))
    return res


@frappe.whitelist(methods=["POST"])
def decide_merge_suggestion(suggestion, decision, swap=0):
    """accept -> merge (swap=1 keeps the other event as the main one), reject -> dismissed."""
    _require_super_admin()
    sug = frappe.get_doc("RN AI Suggestion", suggestion)
    if sug.feature != em.FEATURE:
        frappe.throw("Bukan usulan gabung bencana.")
    if sug.status != "draft":
        frappe.throw("Usulan ini sudah diputuskan.")
    if decision == "reject":
        sug.status, sug.decided_by, sug.decided_at = "rejected", frappe.session.user, now_datetime()
        sug.save(ignore_permissions=True)
        return {"suggestion": sug.name, "status": "rejected"}
    if decision != "accept":
        frappe.throw("Keputusan harus 'accept' atau 'reject'.")
    p = json.loads(sug.payload or "{}")
    source, target = (p["target"], p["source"]) if cint(swap) else (p["source"], p["target"])
    return merge_events(source, target, note="Dari usulan gabung otomatis (skor %s)" % p.get("score"),
                        suggestion=sug.name)


@frappe.whitelist(methods=["POST"])
def undo_merge(log):
    _require_super_admin()
    return em.undo(log, frappe.session.user)


@frappe.whitelist(methods=["POST"])
def scan_now():
    _require_super_admin()
    return {"created": len(em.daily_scan())}
