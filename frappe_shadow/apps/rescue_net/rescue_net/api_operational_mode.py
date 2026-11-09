"""Mode Operasional Riil (owner 2026-11-09): "cukup dengan menekan 1 button di pengaturan super admin, semua
simulasi data ini tidak tampil di halaman rescue net".

Saklar global di tabDefaultValue (frappe.db.set_default) — TANPA DocType/field baru, TANPA migrate. Aturan
penyaringan ada di satu tempat: ``services/drill.py`` (bencana simulasi diperlakukan seperti event latihan).
Data simulasi TIDAK dihapus; mematikan saklar menampilkan semuanya lagi.

- ``status``            tamu boleh: hanya {"operational": bool} (dipakai halaman login untuk menyembunyikan akun demo)
- ``admin_status``      System Manager: status + siapa/kapan + riwayat + daftar bencana dan statusnya
- ``set_operational_mode``   System Manager, POST: nyalakan (konfirmasi "AKTIFKAN") / matikan
- ``set_event_simulation``   System Manager, POST: tandai bencana simulasi/nyata secara manual atau kembali otomatis
"""

import json

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, now_datetime

from rescue_net.services import drill

CONFIRM_WORD = "AKTIFKAN"
LOG_LIMIT = 100


def _require_system_manager():
    if frappe.session.user in (None, "", "Guest") or "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Hanya super admin (System Manager) yang boleh mengubah Mode Operasional Riil.",
                     frappe.PermissionError)


def _log():
    try:
        v = json.loads(drill._get_default(drill.LOG_KEY) or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _append_log(action, detail=None):
    user = frappe.session.user
    entry = {"at": str(now_datetime())[:19], "by": user,
             "by_name": frappe.db.get_value("User", user, "full_name") or user,
             "action": action, "detail": detail or ""}
    frappe.db.set_default(drill.LOG_KEY, json.dumps(([entry] + _log())[:LOG_LIMIT]))
    return entry


def _clear_public_caches():
    """Papan tamu disimpan 30 dtk di cache (guest_cache / public_dashboard): hapus agar saklar langsung terasa."""
    for prefix in ("rn_guest:", "rn_public_dashboard:"):
        try:
            frappe.cache().delete_keys(prefix)
        except Exception:
            pass


def _set_list(key, values):
    frappe.db.set_default(key, json.dumps(sorted(set(values))))


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def status():
    """Publik: apakah Mode Operasional Riil aktif (tanpa data lain)."""
    return {"operational": drill.operational_mode()}


@frappe.whitelist()
def admin_status():
    _require_system_manager()
    detected = drill.detected_simulation_events()
    extra = drill._resolve_names(drill._json_list(drill.EXTRA_KEY))
    exclude = drill._resolve_names(drill._json_list(drill.EXCLUDE_KEY))
    sim = drill.simulation_event_names()
    flagged = drill.flagged_drill_event_names()
    rows = frappe.get_all("RN Disaster Event", fields=["name", "legacy_id", "title", "event_status"],
                          order_by="modified desc", limit_page_length=0)
    posko_count = {r.disaster_event: cint(r.n) for r in frappe.get_all(
        "RN Posko", fields=["disaster_event", "count(name) as n"], group_by="disaster_event", limit_page_length=0)}
    events = []
    for r in rows:
        if r.event_status in ("merged",):
            continue
        events.append({
            "name": r.name, "id": r.legacy_id or r.name, "title": r.title or r.name, "status": r.event_status,
            "simulation": r.name in sim, "drill": r.name in flagged,
            "source": ("manual" if r.name in extra else "exclude" if r.name in exclude
                       else "auto" if r.name in detected else ""),
            "posko_count": posko_count.get(r.name, 0),
        })
    log = _log()
    last = log[0] if log else {}
    return {
        "operational": drill.operational_mode(),
        "changed_by": last.get("by_name") or last.get("by"),
        "changed_at": last.get("at"),
        "log": log[:20],
        "events": events,
        "simulation_count": sum(1 for e in events if e["simulation"]),
        "markers": list(drill.SIM_MARKERS),
    }


@frappe.whitelist(methods=["POST"])
def set_operational_mode(active, confirm=None):
    """Nyalakan / matikan Mode Operasional Riil. Menyalakan wajib ``confirm="AKTIFKAN"``."""
    _require_system_manager()
    on = str(active).strip().lower() in ("1", "true", "yes", "on")
    if on and str(confirm or "").strip().upper() != CONFIRM_WORD:
        frappe.throw(f'Ketik "{CONFIRM_WORD}" untuk mengonfirmasi Mode Operasional Riil.')
    was = drill.operational_mode()
    frappe.db.set_default(drill.MODE_KEY, "1" if on else "0")
    if was != on:
        n = len(drill.simulation_event_names())
        _append_log("aktif" if on else "nonaktif",
                    (f"{n} bencana simulasi disembunyikan" if on else f"{n} bencana simulasi ditampilkan lagi"))
    _clear_public_caches()
    return admin_status()


@frappe.whitelist(methods=["POST"])
def set_event_simulation(event, simulation):
    """Tandai satu bencana: ``simulation`` = "1" (simulasi), "0" (nyata), "auto" (ikut deteksi otomatis)."""
    _require_system_manager()
    names = drill._resolve_names([event])
    if not names:
        frappe.throw("Bencana tidak ditemukan.", frappe.DoesNotExistError)
    name = names.pop()
    mode = str(simulation).strip().lower()
    if mode not in ("1", "0", "auto"):
        frappe.throw("Pilihan tidak dikenal (1 / 0 / auto).")
    extra = drill._resolve_names(drill._json_list(drill.EXTRA_KEY)) - {name}
    exclude = drill._resolve_names(drill._json_list(drill.EXCLUDE_KEY)) - {name}
    detected = name in drill.detected_simulation_events()
    if mode == "1" and not detected:
        extra.add(name)
    elif mode == "0" and detected:
        exclude.add(name)
    _set_list(drill.EXTRA_KEY, extra)
    _set_list(drill.EXCLUDE_KEY, exclude)
    title = frappe.db.get_value("RN Disaster Event", name, "title") or name
    _append_log({"1": "tandai simulasi", "0": "tandai nyata", "auto": "ikut deteksi otomatis"}[mode], title)
    _clear_public_caches()
    return admin_status()
