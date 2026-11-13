"""Mode latihan (Fase 10g): event dengan ``is_drill=1`` adalah latihan/simulasi. + Mode Operasional Riil (2026-11-09):
bila saklar aktif, bencana simulasi (judul [SIMULASI] dsb.) diperlakukan sama seperti latihan.

Satu tempat untuk aturannya (pelajaran BUG-1..6: aturan yang tersebar di tiap endpoint akan terlewat):
publik/agregat nasional tidak pernah memuat event latihan; notifikasi untuk posko/event latihan selalu
disimulasikan; hanya System Manager yang boleh melihat latihan di panel internal (``include_drill``).
Tidak ada yang dihapus di sini — pembersihan latihan ada di ``scripts/rn-drill.py`` (pratinjau dulu).
"""

import json

import frappe

EVENT = "RN Disaster Event"

# ---- Mode Operasional Riil (owner 2026-11-09) ---------------------------------------------------------------------
# "cukup menekan 1 tombol di pengaturan super admin, semua data simulasi tidak tampil". Satu saklar global di
# tabDefaultValue (frappe.db.set_default; TANPA migrate). Saat aktif, bencana simulasi diperlakukan persis seperti
# event latihan (is_drill): semua jalur yang sudah memakai drill_event_names()/real_rows()/guard ikut menyembunyikannya.
# TIDAK ADA data yang dihapus; mematikan saklar mengembalikan semuanya.
MODE_KEY = "rn_operational_mode"
EXTRA_KEY = "rn_sim_events_extra"        # JSON: event yang ditandai simulasi secara manual oleh super admin
EXCLUDE_KEY = "rn_sim_events_exclude"    # JSON: event yang terdeteksi otomatis tapi ternyata NYATA
LOG_KEY = "rn_operational_mode_log"      # JSON: riwayat perubahan (siapa, kapan, apa)

# Penanda simulasi pada judul baris non-event (posko, organisasi, program, armada, ...): cocok huruf besar/kecil.
SIM_MARKERS = ("[simulasi]", "(simulasi)", "[uji-e2e]")
# Kolom judul yang diperiksa untuk penanda di atas (baris tanpa kolom ini tidak terpengaruh).
LABEL_FIELDS = ("title", "program_name", "organization_name", "posko_title", "provider_name", "resource_name",
                "tool_name", "volunteer_name", "full_name")


def _get_default(key):
    """Baca langsung dari DB (bukan cache defaults) agar saklar langsung berlaku & tidak basi setelah rollback tes."""
    try:
        return frappe.db.get_value("DefaultValue", {"parent": "__default", "defkey": key}, "defvalue")
    except Exception:
        return None


def _json_list(key):
    try:
        v = json.loads(_get_default(key) or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except Exception:
        return []


def operational_mode():
    """True bila Mode Operasional Riil aktif (data simulasi disembunyikan)."""
    return str(_get_default(MODE_KEY) or "0").strip() in ("1", "true", "True")


# Akun demo/simulasi (owner 2026-11-09 malam: "hilangkan akun demo dan bencana simulasi, taruh di satu button di
# super admin"): semua akun berdomain di bawah ini dibuat untuk demo & simulasi (data 2026-11-09: 46 + 39 akun;
# akun nyata memakai domain asli). Saat Mode Operasional aktif akun ini tidak bisa masuk dan sesinya diputus.
DEMO_DOMAINS = ("@rescue-net.local", "@example.org")
DEMO_LOGIN_MSG = "Akun demo dinonaktifkan: Rescue-Net sedang dalam Mode Operasional Riil."


def is_demo_user(user):
    u = str(user or "").strip().lower()
    return bool(u) and u.endswith(DEMO_DOMAINS)


def demo_users():
    return [u for (u,) in frappe.db.sql(
        "select name from tabUser where " + " or ".join(["name like %s"] * len(DEMO_DOMAINS)),
        tuple("%" + d for d in DEMO_DOMAINS))]


def block_demo_login(login_manager=None):
    """Hook on_login: tolak akun demo saat Mode Operasional aktif (sebelum sesi dibuat)."""
    user = getattr(login_manager, "user", None) or frappe.session.user
    if is_demo_user(user) and operational_mode():
        frappe.throw(DEMO_LOGIN_MSG, frappe.AuthenticationError)
    if is_demo_user(user):
        # owner 2026-11-13: masuk dengan akun demo = ekosistem demo -> tampilan Simulasi, dan tetap Simulasi setelah
        # keluar sampai pengunjung sendiri memilih "Riil Data Bencana" di Home.
        cm = getattr(frappe.local, "cookie_manager", None)
        if cm is not None:
            try:
                cm.delete_cookie(VIEW_COOKIE)
            except Exception:
                pass


# Pilihan tampilan per pengunjung (owner 2026-11-13: tombol "Lihat Simulasi" / "Riil Data Bencana" di Home).
# Cookie rn_tampilan=riil -> data simulasi disembunyikan HANYA untuk pengunjung itu. Tanpa cookie = simulasi tampil.
# Saklar Mode Operasional (super admin) tetap saklar utama untuk semua orang + blokir akun demo.
VIEW_COOKIE = "rn_tampilan"
VIEW_REAL = "riil"


def viewer_wants_real():
    try:
        req = getattr(frappe.local, "request", None)
        return bool(req) and str(req.cookies.get(VIEW_COOKIE) or "").strip().lower() == VIEW_REAL
    except Exception:
        return False


def view_suffix():
    """Bagian kunci cache publik: salinan untuk tampilan riil terpisah dari tampilan simulasi."""
    return ":riil" if (viewer_wants_real() and not operational_mode()) else ""


def simulation_hidden():
    """Dibaca di titik penyaringan: data simulasi disembunyikan? (Mode Operasional global ATAU pengunjung memilih riil)"""
    return operational_mode() or viewer_wants_real()


def has_sim_label(text):
    t = str(text or "").lower()
    return bool(t) and any(m in t for m in SIM_MARKERS)


def row_has_sim_label(row):
    get = row.get if hasattr(row, "get") else (lambda k: getattr(row, k, None))
    return any(has_sim_label(get(f)) for f in LABEL_FIELDS)


def detected_simulation_events():
    """Event yang TERDETEKSI otomatis sebagai simulasi (tanpa pengecualian/manual): judul berisi 'simulasi' atau
    'UJI-E2E', label latihan berisi 'simulasi', atau id berawalan event-sim-/sim-."""
    or_filters = [["title", "like", "%simulasi%"], ["title", "like", "%UJI-E2E%"],
                  ["name", "like", "%event-sim-%"], ["legacy_id", "like", "%event-sim-%"],
                  ["name", "like", "sim-%"], ["legacy_id", "like", "sim-%"]]
    if frappe.get_meta(EVENT).has_field("drill_label"):
        or_filters.append(["drill_label", "like", "%simulasi%"])
    return set(frappe.get_all(EVENT, or_filters=or_filters, pluck="name", limit_page_length=0))


def _resolve_names(values):
    out = set()
    for v in values:
        v = str(v or "").strip()
        if not v:
            continue
        if frappe.db.exists(EVENT, v):
            out.add(v)
            continue
        legacy = v.split("disaster_events:", 1)[-1]
        n = frappe.db.get_value(EVENT, {"legacy_id": legacy}, "name") or frappe.db.get_value(EVENT, "disaster_events:" + legacy, "name")
        if n:
            out.add(n)
    return out


def simulation_event_names():
    """Semua event simulasi = terdeteksi otomatis + tambahan manual - pengecualian manual (TIDAK tergantung saklar)."""
    return (detected_simulation_events() | _resolve_names(_json_list(EXTRA_KEY))) - _resolve_names(_json_list(EXCLUDE_KEY))


def is_simulation_event(event):
    return bool(event) and event in simulation_event_names()


def flagged_drill_event_names():
    """Hanya event ``is_drill=1`` (latihan resmi). Dipakai pembersihan latihan — data simulasi demo TIDAK PERNAH
    ikut terhapus walau Mode Operasional aktif (owner: data demo jangan dihapus)."""
    if not frappe.get_meta(EVENT).has_field("is_drill"):
        return set()
    return set(frappe.get_all(EVENT, filters={"is_drill": 1}, pluck="name"))


def is_flagged_drill_event(event):
    return bool(event) and event in flagged_drill_event_names()


def drill_event_names():
    """Event yang disembunyikan dari publik/agregat: latihan ``is_drill=1``, ditambah bencana simulasi bila Mode
    Operasional Riil aktif (himpunan; kosong bila field belum dimigrasi dan mode mati)."""
    names = flagged_drill_event_names()
    if simulation_hidden():
        names |= simulation_event_names()
    return names


def is_drill_event(event):
    return bool(event) and event in drill_event_names()


def hidden_posko_names():
    """Posko yang ikut tersembunyi: posko di event tersembunyi, dan (mode aktif) posko berjudul [SIMULASI]."""
    events = drill_event_names()
    out = set()
    if events:
        out |= set(frappe.get_all("RN Posko", filters={"disaster_event": ["in", list(events)]}, pluck="name",
                                  limit_page_length=0))
    if simulation_hidden():
        out |= set(frappe.get_all("RN Posko", or_filters=[["title", "like", "%[SIMULASI]%"],
                                                           ["title", "like", "%(SIMULASI)%"],
                                                           ["title", "like", "%[UJI-E2E]%"]],
                                  pluck="name", limit_page_length=0))
    return out


def is_drill_posko(posko):
    if not posko:
        return False
    return is_drill_event(frappe.db.get_value("RN Posko", posko, "disaster_event"))


def can_include_drill(include_drill=None):
    """Hanya System Manager yang boleh meminta data latihan ikut (panel internal)."""
    asked = str(include_drill or "").lower() in ("1", "true", "yes")
    return asked and "System Manager" in frappe.get_roles()


def real_rows(rows, key="disaster_event", include_drill=None):
    """Buang baris yang terkait event latihan (``key`` = nama kolom event; ``name`` untuk event itu sendiri)."""
    if can_include_drill(include_drill):
        return list(rows)
    drills = drill_event_names()
    sim = simulation_hidden()  # mode operasional: baris berjudul [SIMULASI] juga dibuang walau event-nya nyata
    if not drills and not sim:
        return list(rows)
    return [r for r in rows if (r.get(key) if hasattr(r, "get") else getattr(r, key, None)) not in drills
            and not (sim and row_has_sim_label(r))]


# ---- akses tamu lewat id eksplisit ------------------------------------------------------------------------------
EVENT_PARAMS = ("disaster_event", "disaster_event_id", "event")
POSKO_PARAMS = ("posko", "source_posko", "destination_posko")
ORG_PARAMS = ("organization", "organization_id", "org")


def _event_refs(names):
    """Semua cara menyebut event: nama, legacy_id, dan 'disaster_events:<legacy>'."""
    refs = set()
    if not names:
        return refs
    for r in frappe.get_all(EVENT, filters={"name": ["in", list(names)]}, fields=["name", "legacy_id"],
                            limit_page_length=0):
        for v in (r.name, r.legacy_id):
            if v:
                refs.update({v, "disaster_events:" + v})
                if ":" in v:  # id pendek di URL/halaman: event-sim-001 = disaster_events:event-sim-001
                    refs.add(v.split(":", 1)[1])
    return refs


HIDE_EVENT_KEYS = ("disaster_event", "disaster_event_legacy_id", "disaster_event_id", "event")
HIDE_POSKO_KEYS = ("posko", "source_posko", "destination_posko", "coordination_posko", "posko_ditempatkan_id",
                   "assigned_posko", "host_posko", "shelter_posko")


def drop_hidden_rows(rows, event_keys=HIDE_EVENT_KEYS, posko_keys=HIDE_POSKO_KEYS, label=True):
    """Papan publik (angka & daftar): buang baris milik bencana/posko tersembunyi — latihan is_drill, dan data
    simulasi bila disembunyikan (Mode Operasional atau tampilan "Riil Data Bencana"). Pakai tepat setelah
    frappe.get_all supaya ringkasan dihitung dari data yang sama dengan daftarnya (owner 2026-11-13)."""
    rows = list(rows or [])
    sim = simulation_hidden()
    events = drill_event_names()
    if not rows or (not sim and not events):
        return rows
    refs = _event_refs(events)
    poskos = hidden_posko_names()
    get = lambda r, k: r.get(k) if hasattr(r, "get") else getattr(r, k, None)
    out = []
    for r in rows:
        if any(get(r, k) in refs for k in event_keys if get(r, k)):
            continue
        if any(get(r, k) in poskos for k in posko_keys if get(r, k)):
            continue
        if sim and label and row_has_sim_label(r):
            continue
        out.append(r)
    return out


def _drill_event_refs():
    """Referensi event yang tersembunyi (latihan + simulasi bila mode operasional aktif)."""
    return _event_refs(drill_event_names())


def _refers_to(params, refs, check_labels=False):
    for key in EVENT_PARAMS:
        v = str(params.get(key) or "").strip()
        if v and v in refs:
            return True
    for key in POSKO_PARAMS:
        v = str(params.get(key) or "").strip()
        if not v:
            continue
        row = frappe.db.get_value("RN Posko", v, ["disaster_event", "title"], as_dict=True)
        if row and (row.disaster_event in refs or (check_labels and has_sim_label(row.title))):
            return True
    if check_labels:
        for key in ORG_PARAMS:
            v = str(params.get(key) or "").strip()
            if v and has_sim_label(frappe.db.get_value("RN Organization", v, "title")):
                return True
    return False


def _has_ref_params(params):
    return any(str(params.get(k) or "").strip() for k in EVENT_PARAMS + POSKO_PARAMS + ORG_PARAMS)


def refers_to_drill(params):
    """True bila parameter permintaan menunjuk event tersembunyi, atau posko di event itu (mode operasional: juga
    posko/organisasi berjudul [SIMULASI])."""
    if not _has_ref_params(params):
        return False
    refs = _drill_event_refs()
    sim = simulation_hidden()
    if not refs and not sim:
        return False
    return _refers_to(params, refs, check_labels=sim)


def refers_to_simulation(params):
    """Mode operasional aktif dan parameter menunjuk bencana/posko/organisasi simulasi."""
    if not _has_ref_params(params) or not simulation_hidden():
        return False
    return _refers_to(params, _event_refs(simulation_event_names()), check_labels=True)


def guard_guest_refs(params):
    """Tamu tidak boleh membuka data latihan lewat id eksplisit (diperlakukan 'tidak ditemukan'). Mode Operasional
    Riil: pengguna login (selain System Manager) juga tidak bisa membuka data simulasi."""
    user = frappe.session.user
    if user == "Guest":
        if refers_to_drill(params):
            frappe.throw("Data tidak ditemukan.", frappe.DoesNotExistError)
        return
    # super admin tetap bisa membuka data simulasi saat Mode Operasional, KECUALI ia sendiri memilih tampilan Riil
    if ("System Manager" not in frappe.get_roles(user) or viewer_wants_real()) and refers_to_simulation(params):
        frappe.throw("Data tidak ditemukan.", frappe.DoesNotExistError)


def before_request(*args, **kwargs):
    """Hook before_request: berlaku hanya untuk panggilan /api/method/rescue_net.*; kegagalan internal tidak
    boleh mengganggu request lain (hanya penolakan yang disengaja yang diteruskan)."""
    try:
        req = getattr(frappe.local, "request", None)
        if not req or not (req.path or "").startswith("/api/method/rescue_net."):
            return
        params = frappe.local.form_dict
    except Exception:
        return
    # sesi akun demo yang masih terbuka saat Mode Operasional aktif: ditolak
    if is_demo_user(frappe.session.user) and operational_mode():
        frappe.throw(DEMO_LOGIN_MSG, frappe.AuthenticationError)
    guard_guest_refs(params)
