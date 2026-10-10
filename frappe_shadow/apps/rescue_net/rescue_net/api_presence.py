"""Check-in / check-out relawan di posko (Fase 10h).

Kehadiran dicatat append-only di RN Volunteer Presence (hanya check-out/tinjauan yang boleh mengisi).
Check-in lewat QR posko (token berputar harian, diturunkan dari rahasia situs — tidak disimpan) atau tombol di
aplikasi (koordinat opsional, hanya penanda jarak, tidak pernah menolak). Relawan tanpa penugasan aktif di posko itu
tercatat sebagai walk-in dan menunggu tinjauan pengelola. Lupa check-out ditutup otomatis setelah 12 jam.
Kehadiran tidak pernah publik: hanya untuk relawan sendiri dan pengelola posko.
"""

import hashlib
import hmac
from datetime import timedelta

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, get_datetime, now_datetime

from rescue_net.access_policy import rn_actor
from rescue_net.api_volunteer import _actor_profile, _assert_manager_posko
from rescue_net.services.early_warning import _km

AUTO_CLOSE_HOURS = 12
_ACTIVE_ASSIGNMENT = ("accepted", "checked_in", "in_progress")
_MAX_LATE = timedelta(days=3)


def _token_for(posko, day):
    from frappe.utils.password import get_encryption_key

    msg = "{}:{}".format(posko, day).encode()
    return "RNH-" + hmac.new(get_encryption_key().encode(), msg, hashlib.sha256).hexdigest()[:16]


def _valid_tokens(posko):
    today = now_datetime().date()
    return {_token_for(posko, today), _token_for(posko, today - timedelta(days=1))}  # kemarin = masa tenggang


def _event_time(at):
    """Waktu kejadian dari antrean offline: tidak di masa depan, tidak lebih tua dari 3 hari; selain itu pakai sekarang."""
    now = now_datetime()
    if not at:
        return now
    try:
        t = get_datetime(at)
    except Exception:
        return now
    if t > now + timedelta(minutes=5) or now - t > _MAX_LATE:
        return now
    return min(t, now)


def _row(d):
    return {"name": d.name, "posko": d.posko, "in_at": str(d.in_at), "out_at": str(d.out_at or ""),
            "walk_in": int(d.walk_in or 0), "method": d.method, "auto_closed": int(d.auto_closed or 0)}


def _open_presence(volunteer):
    name = frappe.db.get_value("RN Volunteer Presence", {"volunteer": volunteer, "out_at": ["is", "not set"]}, "name",
                               order_by="in_at desc")
    return frappe.get_doc("RN Volunteer Presence", name) if name else None


def _close(doc, when, auto=False):
    doc.out_at = max(when, get_datetime(doc.in_at))
    doc.auto_closed = 1 if auto else 0
    doc.save(ignore_permissions=True)


@frappe.whitelist()
def posko_qr(posko):
    """Pengelola posko: token kehadiran hari ini + tautan untuk dicetak sebagai QR."""
    actor = rn_actor()
    if not frappe.db.exists("RN Posko", posko):
        frappe.throw("Posko tidak ditemukan.", frappe.DoesNotExistError)
    _assert_manager_posko(actor, posko)
    token = _token_for(posko, now_datetime().date())
    return {"posko": posko, "token": token,
            "path": "/rescue-net/pages/kehadiran-relawan.html?posko={}&t={}".format(posko, token),
            "berlaku": "hari ini (+ masa tenggang 1 hari)"}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60)
def check_in(posko, token=None, latitude=None, longitude=None, offline_id=None, at=None):
    actor = rn_actor()
    volunteer = _actor_profile(actor)
    if not volunteer:
        frappe.throw("Daftar sebagai relawan dulu sebelum check-in.", frappe.PermissionError)
    info = frappe.db.get_value("RN Posko", posko, ["name", "disaster_event", "latitude", "longitude"], as_dict=True)
    if not info:
        frappe.throw("Posko tidak ditemukan.", frappe.DoesNotExistError)

    offline_id = (str(offline_id).strip()[:140] or None) if offline_id else None
    if offline_id:
        prev = frappe.db.get_value("RN Volunteer Presence", {"offline_id": offline_id}, "name")
        if prev:
            return {"ok": True, "duplicate": True, "presence": _row(frappe.get_doc("RN Volunteer Presence", prev))}

    method = "app"
    if token:
        if str(token).strip() not in _valid_tokens(posko):
            frappe.throw("Kode QR kehadiran tidak valid atau kedaluwarsa.", frappe.PermissionError)
        method = "qr"

    when = _event_time(at)
    cur = _open_presence(volunteer)
    if cur and cur.posko == posko:
        return {"ok": True, "duplicate": True, "presence": _row(cur)}      # sudah check-in di sini
    if cur:                                                                # pindah posko: tutup yang lama
        _close(cur, when, auto=True)

    assignment = frappe.db.get_value("RN Volunteer Assignment",
                                     {"volunteer": volunteer, "posko": posko, "assignment_status": ["in", list(_ACTIVE_ASSIGNMENT)]},
                                     ["name", "assignment_status"], as_dict=True)
    lat, lng = (flt(latitude) if latitude not in (None, "") else None), (flt(longitude) if longitude not in (None, "") else None)
    dist = None
    if None not in (lat, lng) and info.latitude and info.longitude:
        dist = round(_km(lat, lng, flt(info.latitude), flt(info.longitude)) * 1000)
    doc = frappe.get_doc({
        "doctype": "RN Volunteer Presence", "volunteer": volunteer, "posko": posko, "disaster_event": info.disaster_event,
        "assignment": assignment.name if assignment else None, "in_at": when, "method": method,
        "walk_in": 0 if assignment else 1, "review_status": "" if assignment else "pending",
        "latitude": lat, "longitude": lng, "distance_m": dist, "offline_id": offline_id,
        "briefing_missing": 0 if frappe.db.exists("RN Safety Briefing", {"posko": posko}) else 1,
    }).insert(ignore_permissions=True)
    if assignment and assignment.assignment_status == "accepted":
        try:  # selaraskan penugasan lewat graf status yang sama
            from rescue_net.api_volunteer import update_assignment_status
            update_assignment_status(assignment.name, "checked_in")
        except Exception:
            frappe.clear_last_message()
    return {"ok": True, "duplicate": False, "presence": _row(doc), "walk_in": int(doc.walk_in),
            "briefing_missing": int(doc.briefing_missing), "distance_m": dist}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60)
def check_out(posko=None, offline_id=None, at=None):
    actor = rn_actor()
    volunteer = _actor_profile(actor)
    if not volunteer:
        frappe.throw("Anda bukan relawan terdaftar.", frappe.PermissionError)
    cur = _open_presence(volunteer)
    if not cur or (posko and cur.posko != posko):
        if offline_id:  # pemutaran ulang antrean offline: sudah ter-check-out -> aman diabaikan
            return {"ok": True, "duplicate": True}
        frappe.throw("Tidak ada check-in aktif untuk di-check-out.")
    _close(cur, _event_time(at))
    return {"ok": True, "duplicate": False, "presence": _row(cur)}


@frappe.whitelist()
def on_site(posko):
    """Pengelola posko: siapa yang sedang ada di lokasi + hitungan (privat, tidak publik)."""
    actor = rn_actor()
    _assert_manager_posko(actor, posko)
    rows = frappe.get_all("RN Volunteer Presence", filters={"posko": posko, "out_at": ["is", "not set"]},
                          fields=["name", "volunteer", "in_at", "walk_in", "review_status", "method", "distance_m", "briefing_missing"],
                          order_by="in_at asc", limit_page_length=500)
    for r in rows:
        v = frappe.db.get_value("RN Volunteer Profile", r.volunteer, ["volunteer_name", "main_skill"], as_dict=True) or {}
        r["volunteer_name"], r["main_skill"] = v.get("volunteer_name"), v.get("main_skill")
        r["in_at"] = str(r["in_at"])
    return {"posko": posko, "count": len(rows), "walk_in_pending": sum(1 for r in rows if r.review_status == "pending"),
            "rows": rows}


@frappe.whitelist(methods=["POST"])
def review_walk_in(presence):
    """Pengelola posko menandai walk-in sudah ditinjau (diterima)."""
    actor = rn_actor()
    doc = frappe.get_doc("RN Volunteer Presence", presence)
    _assert_manager_posko(actor, doc.posko)
    if not doc.walk_in:
        frappe.throw("Ini bukan catatan walk-in.")
    doc.review_status = "reviewed"
    doc.reviewed_by = frappe.session.user
    doc.save(ignore_permissions=True)
    return {"ok": True, "presence": doc.name}


def close_stale_presence(hours=AUTO_CLOSE_HOURS):
    """Terjadwal (tiap jam): check-in yang tak di-check-out > N jam ditutup otomatis pada in_at + N jam."""
    cutoff = now_datetime() - timedelta(hours=hours)
    for name in frappe.get_all("RN Volunteer Presence", filters={"out_at": ["is", "not set"], "in_at": ["<", cutoff]},
                               pluck="name", limit_page_length=1000):
        doc = frappe.get_doc("RN Volunteer Presence", name)
        _close(doc, get_datetime(doc.in_at) + timedelta(hours=hours), auto=True)
