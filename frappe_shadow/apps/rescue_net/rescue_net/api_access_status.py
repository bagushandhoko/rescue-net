"""Status akses & infrastruktur (Fase 10e). Tulis: pengelola posko di event itu / pelapor terverifikasi / System
Manager. Verifikasi: verifikator aktif / System Manager. Publik: hanya ringkasan per jenis + daftar tempat tertutup/
terbatas (tanpa pelapor, tanpa koordinat, tanpa catatan)."""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, get_datetime, now_datetime

from rescue_net.access_policy import is_system_manager, rn_actor
from rescue_net.api_public_needs import _can_edit_notes, _clean_note
from rescue_net.api_verifier import _my_verifier
from rescue_net.services import access_status as svc
from rescue_net.services.drill import is_drill_event
from rescue_net.services.reporter import is_verified_reporter

MAX_VALID_HOURS = 24 * 30


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=3600)
def report(disaster_event, kind, place_name, status, valid_hours=48, posko=None, latitude=None, longitude=None,
           segment=None, admin_area_id=None, note=None):
    actor = rn_actor()
    if not disaster_event or not frappe.db.exists("RN Disaster Event", disaster_event):
        frappe.throw("Bencana tidak ditemukan.", frappe.DoesNotExistError)
    if kind not in svc.KINDS or status not in svc.STATUSES:
        frappe.throw("Jenis atau status tidak valid.")
    place_name = " ".join(str(place_name or "").split())
    if not place_name or len(place_name) > 140:
        frappe.throw("Nama tempat/ruas wajib (maks 140 karakter).")
    hours = 48 if valid_hours in (None, "") else int(valid_hours)
    if not 1 <= hours <= MAX_VALID_HOURS:
        frappe.throw("Masa berlaku harus 1 jam sampai 30 hari.")

    pk = None
    if posko:
        pk = frappe.db.get_value("RN Posko", posko, ["name", "disaster_event", "admin_area_id"], as_dict=True)
        if not pk or pk.disaster_event != disaster_event:
            frappe.throw("Posko bukan bagian dari bencana ini.")
    allowed = is_system_manager() or is_verified_reporter(actor) or bool(pk and _can_edit_notes(actor, pk.name))
    if not allowed:
        frappe.throw("Hanya pengelola posko (isi posko), pelapor terverifikasi, atau System Manager.", frappe.PermissionError)

    area = admin_area_id or (pk.admin_area_id if pk else None)
    if area and not frappe.db.exists("RN Admin Area", area):
        area = None
    now = now_datetime()
    doc = frappe.get_doc({
        "doctype": "RN Access Status", "disaster_event": disaster_event, "kind": kind, "place_name": place_name,
        "status": status, "latitude": float(latitude) if latitude not in (None, "") else None,
        "longitude": float(longitude) if longitude not in (None, "") else None,
        "segment": _clean_note(segment, "Keterangan lokasi")[:140] or None, "admin_area_id": area,
        "posko": pk.name if pk else None, "reported_by": (actor.name if actor and actor.get("name") else frappe.session.user),
        "verification_status": "reported", "observed_at": now, "valid_until": add_to_date(now, hours=hours),
        "note": _clean_note(note, "Catatan") or None,
    }).insert(ignore_permissions=True)
    return {"ok": True, "name": doc.name, "valid_until": str(doc.valid_until)}


@frappe.whitelist(methods=["POST"])
def verify(name):
    actor = rn_actor()
    if not frappe.db.exists("RN Access Status", name):
        frappe.throw("Laporan tidak ditemukan.", frappe.DoesNotExistError)
    ver = _my_verifier(actor)
    if not (is_system_manager() or (ver and not ver.get("_inactive"))):
        frappe.throw("Hanya verifikator aktif atau System Manager.", frappe.PermissionError)
    doc = frappe.get_doc("RN Access Status", name)
    doc.verification_status = "verified"
    doc.verified_by = frappe.session.user
    doc.save(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist()
def list_status(disaster_event):
    """Pengguna login: status saat ini lengkap (koordinat, wilayah, catatan) untuk peta/perencana rute."""
    rn_actor()
    return {"rows": svc.current_statuses(disaster_event)}


@frappe.whitelist()
def history(disaster_event, kind, place_name):
    """Pengguna login: riwayat satu tempat (kapan putus, kapan pulih)."""
    rn_actor()
    rows = frappe.get_all("RN Access Status",
                          filters={"disaster_event": disaster_event, "kind": kind, "place_name": place_name},
                          fields=["status", "observed_at", "valid_until", "verification_status", "note"],
                          order_by="observed_at desc, creation desc", limit_page_length=200)
    return {"rows": [dict(r, observed_at=str(r.observed_at), valid_until=str(r.valid_until)) for r in rows]}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def board(disaster_event):
    """Publik: ringkasan per jenis dan daftar tempat tertutup/terbatas. Tanpa pelapor, koordinat, atau catatan."""
    if not disaster_event or not frappe.db.exists("RN Disaster Event", disaster_event) or is_drill_event(disaster_event):
        return {"event": disaster_event, "summary": [], "items": []}
    cur = svc.current_statuses(disaster_event)
    summary = []
    for kind in svc.KINDS:
        rows = [r for r in cur if r["kind"] == kind]
        if rows:
            summary.append({"kind": kind, "label": svc.KIND_LABEL[kind],
                            **{s: sum(1 for r in rows if r["effective_status"] == s) for s in svc.STATUSES}})
    items = [{"kind": r["kind"], "label": svc.KIND_LABEL[r["kind"]], "place_name": r["place_name"],
              "status": r["effective_status"], "segment": r["segment"], "age_hours": r["age_hours"],
              "stale": r["stale"], "verified": int(r["verification_status"] == "verified")}
             for r in cur if r["effective_status"] in ("closed", "limited")]
    items.sort(key=lambda r: (r["status"] != "closed", r["age_hours"]))
    return {"event": disaster_event, "summary": summary, "items": items[:300]}
