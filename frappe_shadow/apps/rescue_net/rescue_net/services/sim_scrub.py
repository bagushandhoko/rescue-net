"""Penyaring umum respons API untuk tampilan "Riil Data Bencana" (owner 2026-11-13).

Banyak papan publik (komunikasi, relawan, SAR, kebutuhan, verifikator, tender, laporan masyarakat, ...) tidak
memakai penyaring simulasi. Daripada menambal satu per satu, hook ``after_request`` ini membersihkan respons JSON
``/api/method/rescue_net.*`` saat data simulasi disembunyikan (cookie rn_tampilan=riil atau Mode Operasional):
baris (dict di dalam list) dibuang bila merujuk bencana/posko simulasi (kolom id, atau tautan ?id=/?posko=/?event=)
atau salah satu teksnya berlabel [SIMULASI]/(SIMULASI)/[UJI-E2E]. Angka ringkasan dihitung oleh papan masing-masing.
System Manager tanpa pilihan riil, dan halaman admin (Mode Operasional, sistem), tidak disaring."""

import json
import re
from urllib.parse import parse_qsl, urlsplit

import frappe

from rescue_net.services import drill

SKIP_PREFIXES = ("rescue_net.api_operational_mode.", "rescue_net.api_system_admin.", "rescue_net.api_auth.")
_TOKEN = re.compile(r"[A-Za-z0-9_]+:[A-Za-z0-9_.\-]+|[A-Za-z0-9_.\-]+")


def _hidden_ids():
    events = set(drill.drill_event_names()) | set(drill.simulation_event_names())
    poskos = set(drill.hidden_posko_names())
    ids = set()
    for n in events | poskos:
        ids.add(n)
        if ":" in n:
            ids.add(n.split(":", 1)[1])  # legacy id tanpa awalan (event-..., posko-...)
    for row in frappe.get_all("RN Disaster Event", filters={"name": ["in", list(events)]}, fields=["legacy_id"],
                              limit_page_length=0) if events else []:
        if row.legacy_id:
            ids.add(row.legacy_id)
            ids.add(row.legacy_id.split(":", 1)[-1])
    ids.discard("")
    return ids


def _str_refers(value, ids):
    if value in ids:
        return True
    if "?" in value or "=" in value:
        try:
            for _k, v in parse_qsl(urlsplit(value).query):
                if v in ids:
                    return True
        except Exception:
            return False
    return False


def _row_hidden(row, ids):
    for v in row.values():
        if isinstance(v, str) and v:
            if drill.has_sim_label(v) or _str_refers(v, ids):
                return True
    return False


def scrub(obj, ids):
    """Kembalikan salinan obj tanpa baris simulasi (rekursif)."""
    if isinstance(obj, list):
        out = []
        for x in obj:
            if isinstance(x, dict) and _row_hidden(x, ids):
                continue
            if isinstance(x, str) and (drill.has_sim_label(x) or x in ids):
                continue
            out.append(scrub(x, ids))
        return out
    if isinstance(obj, dict):
        return {k: scrub(v, ids) for k, v in obj.items() if not (isinstance(k, str) and k in ids)}
    return obj


def after_request(response=None, request=None):
    try:
        if response is None or request is None or response.status_code != 200:
            return
        path = request.path or ""
        if not path.startswith("/api/method/rescue_net."):
            return
        method = path[len("/api/method/"):]
        if method.startswith(SKIP_PREFIXES):
            return
        if not drill.simulation_hidden():
            return
        if not drill.viewer_wants_real() and "System Manager" in frappe.get_roles():
            return  # Mode Operasional: super admin tetap melihat semua (seperti penjaga id eksplisit)
        if "json" not in (response.content_type or ""):
            return
        data = json.loads(response.get_data(as_text=True))
        if not isinstance(data, dict) or "message" not in data:
            return
        ids = _hidden_ids()
        data["message"] = scrub(data["message"], ids)
        response.set_data(json.dumps(data, default=str, separators=(",", ":")))
    except Exception:
        frappe.log_error(title="sim_scrub after_request", message=frappe.get_traceback())
