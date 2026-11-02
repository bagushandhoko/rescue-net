"""Asisten AI di setiap halaman (owner 2026-11-02).

"buat semacam link untuk user bisa komunikasi dengan AI-nya di setiap halaman; ingat kalau dia belum setting
AI key dan/atau tokennya habis; dia bisa gunakan AI untuk atur posko dan cari data di Rescue-Net."

- status(): is AI usable for this user right now (own key / shared organisation key / platform key), and why not.
- chat(): one question (+ short history). Context = public data of the disaster, a keyword search over
  Rescue-Net (poskos, organisations, disasters, open needs), and — only for poskos the user MANAGES — that
  posko's pending work, stock, expiry and warnings. Full operational context only for System Manager /
  Control Centre. The AI never writes by itself (ADR-0002): it answers, points to the page/tool, and may PROPOSE
  an action that the user runs with the "Jalankan" button under the user's own permissions.
- Owner 2026-11-02 sore: "pastikan AI benar-benar berfungsi untuk semua user atau organisasi ... bisa jalankan
  pengaturan posko dan setting lainnya, atau menjelaskan bagaimana penggunaan rescue-net" → more actions
  (posko contact, needs, stock, volunteer requests, own volunteer profile) and the user manual
  (ai/manual_pengguna.txt, from pages/manual.html via scripts/rn-manual-to-ai.py) for how-to questions.
- Missing key, spent quota, rejected key, rate limit → a friendly `status` instead of an error.
"""

import json
import re

import frappe

from rescue_net.access_policy import can_manage_posko, is_system_manager, rn_actor
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko

MAX_Q = 1500
MAX_HISTORY = 6

# where to do what — the AI points users here instead of changing data itself
PAGE_MAP = {
    "Kelola posko (yang perlu ditindak, kontak, alat kerja, stok kedaluwarsa)": "pages/kelola-posko.html?id=<posko>",
    "Ubah data/kontak/lokasi posko": "tombol ⚙ Pengaturan di halaman posko",
    "Daftarkan posko baru": "pages/registrasi-posko.html",
    "Daftarkan / usulkan bencana baru": "pages/kelola-bencana.html#kbCreatePanel",
    "Stok, kebutuhan, kirim barang (posko logistik)": "pages/posko-logistik.html?id=<posko>",
    "Distribusi & armada": "pages/management-distribusi.html",
    "Relawan: tawaran, penugasan, jemputan": "pages/management-relawan.html",
    "Profil & tawaran relawan pribadi": "pages/relawan-saya.html",
    "Alat komunikasi & radio": "pages/alat-komunikasi.html",
    "Laporan warga": "pages/laporan-masyarakat.html",
    "Donasi & program khusus": "pages/program-khusus.html",
    "Kunci AI pribadi / organisasi": "pages/ai-settings.html",
    "Notifikasi WhatsApp": "pages/notifikasi-settings.html",
    "Registrasi akun / login / peran": "pages/auth.html",
    "Bencana aktif & peta": "pages/bencana-aktif.html",
    "Cari & pesan armada (transport)": "pages/management-distribusi.html (panel Cari Armada)",
    "Daftarkan armada posko distribusi": "pages/posko-distribusi.html?id=<posko>#armadaForm",
    "Organisasi & anggota": "pages/koordinasi-organisasi.html",
    "Kebutuhan publik (yang bisa dibantu)": "pages/kebutuhan-publik.html",
    "Kirim bantuan": "pages/kirim-bantuan.html",
    "Lacak kiriman logistik": "pages/lacak-logistik.html",
    "Pencarian orang hilang": "pages/search-found.html",
    "Shelter / pengungsian": "pages/shelter-detail.html?id=<shelter>",
    "Dapur umum": "pages/dapur-umum.html",
    "Manual pengguna lengkap": "pages/manual.html",
    "Pasang aplikasi / mode offline": "pages/install.html",
    "Kebijakan privasi": "pages/kebijakan-privasi.html",
}

SYSTEM_PROMPT = """Anda adalah Asisten AI Rescue-Net (platform koordinasi bencana di Indonesia).
Jawab dalam bahasa Indonesia sederhana, singkat dan praktis.
Tugas: (1) membantu pengelola mengatur posko — beri langkah konkret dan sebut halaman/alat yang dipakai dari PAGE_MAP;
(2) mencari dan merangkum data Rescue-Net dari konteks yang diberikan (posko, organisasi, bencana, kebutuhan, stok);
(3) menjelaskan cara memakai Rescue-Net (registrasi, peran, posko, relawan, laporan, bantuan, armada, kunci AI, offline)
berdasarkan MANUAL_PENGGUNA dan PAGE_MAP bila ada di konteks — jangan mengarang menu yang tidak disebut di sana;
(4) mengusulkan aksi pengaturan yang bisa langsung dijalankan pengguna (lihat AKSI di bawah).
Aturan:
- Gunakan HANYA data di konteks. Kalau tidak ada, katakan tidak ditemukan — jangan mengarang angka, nama, atau nomor.
- Anda sendiri TIDAK mengubah data. Perubahan hanya lewat usulan AKSI yang dijalankan pengguna, atau arahkan ke
  halaman/tombol yang tepat bila tidak ada aksi yang cocok.
- Jangan menampilkan data pribadi yang tidak ada di konteks; jangan menebak identitas pasien/orang hilang.
- Sebut nama posko/bencana persis seperti di konteks, dan sertakan tautan relatif bila ada (field href).
- Bila pertanyaan di luar Rescue-Net/kebencanaan, jawab singkat dan arahkan kembali.
AKSI (owner 2026-11-02): Anda BOLEH mengusulkan aksi perubahan untuk posko yang dikelola pengguna, atau untuk profil
relawan pengguna sendiri — pengguna sendiri yang menekan tombol "Jalankan". Usulkan hanya aksi dari AKSI_TERSEDIA,
hanya untuk ID yang ada di konteks (posko_yang_anda_kelola / posko_aktif / armada / permintaan_relawan /
profil_relawan_anda), dan hanya bila pengguna memintanya atau jelas membantu. Isi params hanya dengan nilai yang
disebut pengguna atau ada di konteks; bila data wajib belum ada (mis. jumlah, satuan), tanyakan dulu.
Tulis tiap usulan di baris tersendiri PALING AKHIR jawaban, persis:
[[AKSI {"action": "<nama>", "params": {...}, "label": "<kalimat singkat untuk tombol>"}]]
Jangan pernah mengklaim aksi sudah dijalankan."""

# actions the AI may PROPOSE; the user presses "Jalankan" and it runs with the user's own permissions
ACTIONS = {
    "armada_position": {"params": ["transport_space"], "desc": "kirim posisi GPS HP sekarang untuk armada (transport_space)"},
    "armada_status": {"params": ["transport_space", "transport_status"],
                      "desc": "ubah status armada: available / reserved / assigned / in_transit / arrived / completed"},
    "posko_status": {"params": ["posko", "operational_status"],
                     "desc": "ubah status operasional posko: active / standby / reducing / closing / offline"},
    "comms_support": {"params": ["posko", "offered", "needed"], "desc": "isi dukungan komunikasi yang ditawarkan / dibutuhkan posko"},
    "stock_expiry": {"params": ["posko", "item_name", "unit", "quantity", "expiry_date"],
                     "desc": "beri tanggal kedaluwarsa (YYYY-MM-DD) pada stok posko"},
    "posko_contact": {"params": ["posko", "officer_in_charge_name", "officer_in_charge_role", "officer_in_charge_phone",
                                 "officer_in_charge_whatsapp", "emergency_contact"],
                      "desc": "ubah kontak posko (PIC, jabatan, HP, WhatsApp, kontak darurat) — isi hanya yang diubah"},
    "need_create": {"params": ["posko", "item_text", "quantity", "unit", "urgency", "jiwa_terdampak", "needed_before"],
                    "desc": "tambah kebutuhan posko; urgency normal / urgent / critical (urgent/critical wajib jiwa_terdampak)"},
    "stock_record": {"params": ["posko", "item_text", "quantity", "unit"], "desc": "catat stok terkini satu barang di posko"},
    "volunteer_decide": {"params": ["booking", "decision"],
                         "desc": "putuskan permintaan relawan ke posko: decision confirm (terima) / reject (tolak)"},
    "volunteer_profile": {"params": ["main_skill", "equipment_owned", "available_from", "available_until",
                                     "duration_available", "current_location"],
                          "desc": "ubah profil relawan pengguna sendiri (keahlian, peralatan, tersedia dari/sampai YYYY-MM-DD, "
                                  "lama bisa membantu, lokasi) — isi hanya yang diubah"},
}
POSKO_ACTIONS = {"posko_status", "comms_support", "stock_expiry", "posko_contact", "need_create", "stock_record"}
NEED_URGENCY = {"normal", "urgent", "critical"}
HOWTO_RE = re.compile(r"cara|bagaimana|gimana|gmn|apa itu|fungsi|menu|fitur|daftar|registrasi|regis|pakai|gunakan|guna|"
                      r"jelaskan|langkah|panduan|tutorial|bantuan|help|mulai|install|pasang|offline|login|akun|peran|"
                      r"organisasi|kunci|token|bisa apa|kenapa|mengapa", re.I)
ARMADA_STATUS = {"available", "reserved", "assigned", "in_transit", "arrived", "completed"}
POSKO_STATUS = {"active", "standby", "reducing", "closing", "offline"}
_AKSI_RE = re.compile(r"\[\[AKSI\s*(\{.*?\})\s*\]\]", re.S)


def _user():
    if frappe.session.user in (None, "", "Guest"):
        return None
    return frappe.session.user


def _resolve(user, organization_id=None):
    """(resolved dict | None, status, message)."""
    from rescue_net.ai.keys import resolve_ai

    try:
        r = resolve_ai(user, "auto", organization_id or None)
    except frappe.PermissionError:
        return None, "forbidden", "Anda bukan anggota organisasi ini."
    except frappe.ValidationError as e:
        return None, "disabled", str(e) or "AI dinonaktifkan untuk konteks ini."
    if not r:
        return None, "no_key", ("Anda belum memasang kunci AI, dan tidak ada kunci organisasi/platform yang bisa dipakai. "
                                "Pasang kunci AI Anda (mis. OpenAI/Gemini/DeepSeek/GLM) di AI Settings.")
    from rescue_net.ai import budget

    try:
        budget.check_allowed(r["owner_type"], r["owner_id"], user)
    except budget.AIUnavailable as e:
        return r, ("quota" if e.kind == "budget" else e.kind), e.message
    return r, "ok", ""


SOURCE_LABEL = {"user": "kunci AI pribadi Anda", "organization": "kunci AI organisasi", "platform": "kunci AI bersama Rescue-Net"}


@frappe.whitelist(allow_guest=True)
def status(organization_id=None):
    user = _user()
    if not user:
        return {"status": "login", "message": "Login dulu untuk memakai Asisten AI.", "settings": "pages/ai-settings.html"}
    r, st, msg = _resolve(user, organization_id)
    orgs = []
    try:
        from rescue_net.ai.keys import ai_contexts

        orgs = ai_contexts().get("organizations", [])
    except Exception:
        pass
    return {"status": st, "message": msg, "source": SOURCE_LABEL.get((r or {}).get("owner_type")),
            "own_key": bool(r and r.get("owner_type") == "user"), "organizations": orgs,
            "settings": "pages/ai-settings.html"}


# --- context -----------------------------------------------------------------

def _words(q):
    stop = {"yang", "dan", "di", "ke", "dari", "untuk", "ada", "apa", "berapa", "mana", "dengan", "saya", "kami",
            "posko", "bencana", "data", "cari", "tolong", "bagaimana", "apakah", "ini", "itu", "atau", "the"}
    return [w for w in re.findall(r"[a-zA-Z0-9]{3,}", (q or "").lower()) if w not in stop][:6]


def _search(q, event):
    """Small keyword search over public-safe fields."""
    words = _words(q)
    if not words:
        return {}
    out = {}

    def like_any(fields):
        return [[f, "like", "%" + w + "%"] for w in words for f in fields]

    from rescue_net.control_centre.common import serving_posko_names

    pk_filters = {"name": ["in", serving_posko_names(event) or ["__none__"]]} if event else {}
    poskos = frappe.get_all("RN Posko", filters=pk_filters, or_filters=like_any(["title", "city_name", "district_name",
                                                                                  "village_name", "posko_type"]),
                            fields=["name", "title", "posko_type", "city_name", "operational_status"], limit_page_length=15)
    out["posko"] = [dict(p, href="pages/posko-detail.html?id=" + p.name) for p in poskos]
    out["organisasi"] = frappe.get_all("RN Organization", or_filters=like_any(["title"]),
                                       fields=["name", "title", "verification_status"], limit_page_length=10)
    out["bencana"] = [dict(e, href="pages/bencana-aktif.html?event=" + e.name) for e in frappe.get_all(
        "RN Disaster Event", filters={"event_status": "active"}, or_filters=like_any(["title", "location_summary"]),
        fields=["name", "title", "event_type", "location_summary"], limit_page_length=10)]
    if event:
        out["kebutuhan_terbuka"] = frappe.get_all(
            "RN Logistic Need", filters={"disaster_event": event, "need_status": ["in", ["open", "needs_review"]]},
            or_filters=like_any(["item_name"]), fields=["item_name", "quantity", "unit", "urgency", "posko"],
            limit_page_length=20)
    return {k: v for k, v in out.items() if v}


_MANUAL = None


def _manual():
    """User manual as plain text (ai/manual_pengguna.txt, generated from pages/manual.html)."""
    global _MANUAL
    if _MANUAL is None:
        import os

        try:
            with open(os.path.join(os.path.dirname(__file__), "ai", "manual_pengguna.txt"), encoding="utf-8") as f:
                _MANUAL = f.read()[:24000]
        except OSError:
            _MANUAL = ""
    return _MANUAL


def _my_volunteer_profiles(actor):
    from rescue_net.api_volunteer_booking import _profiles

    return _profiles(actor)


def _my_volunteer_summary(actor):
    """The asker's OWN volunteer profile (only their own data) so the AI can explain or propose changes."""
    from rescue_net.api_volunteer_booking import _my_profile_fields

    profiles = _my_volunteer_profiles(actor)
    if not profiles:
        return None
    f = _my_profile_fields(profiles)
    return {"bencana": [p.disaster_event for p in profiles], "profil": {k: str(v) for k, v in f.items() if v not in ("", None)},
            "ubah_di": "pages/relawan-saya.html"}


def _active_disasters():
    """Always in the context (owner 2026-11-02: "AI jawab tidak ada bencana aktif") — the keyword search alone
    finds nothing for "bencana aktif apa saja?" because no title contains those words. Same public list as the
    home page (drills excluded)."""
    from rescue_net.services.drill import real_rows

    rows = frappe.get_all("RN Disaster Event", filters={"event_status": "active"},
                          fields=["name", "title", "event_type", "severity", "location_summary", "started_at"],
                          order_by="started_at desc", limit_page_length=30)
    return [dict(r, href="pages/bencana-aktif.html?event=" + r.name) for r in real_rows(rows, key="name")]


def _event_context(event):
    from rescue_net.ai.context import _build_context
    from rescue_net.ai.context import _public_scrub

    full = is_system_manager() or ((rn_actor(required=False) or {}).get("role") == "command_center")
    ctx = _build_context(event, public=not full)
    if not full:
        ctx = _public_scrub(ctx)
    keep = ("summary", "alerts", "recommendations", "stock_summary", "logistic_needs", "shelter_occupancies",
            "special_programs", "resource_profiles")
    return {k: (v[:25] if isinstance(v, list) else v) for k, v in ctx.items() if k in keep}, full


def _posko_context(posko):
    from rescue_net.api_posko_manage import _summary

    actor = rn_actor(required=False)
    s = _summary(posko, actor)
    out = {k: s.get(k) for k in ("posko", "title", "type_label", "status", "verification", "events", "pending",
                                 "warnings", "tools", "comms")}
    out["armada"] = frappe.get_all("RN Transport Space", filters={"coordination_posko": posko,
                                                                  "transport_status": ["not in", ["completed", "cancelled"]]},
                                   fields=["name", "title", "transport_status", "departure_at", "position_at",
                                           "capacity_weight_kg", "capacity_committed_kg"], limit_page_length=30)
    try:
        from rescue_net.api_posko_manage import workbench

        wb = workbench(posko)
        out["kontak"] = wb.get("contact")
        out["kebutuhan_terbuka"] = wb.get("needs")
        out["permintaan_relawan"] = [{k: v.get(k) for k in ("name", "booking_kind", "volunteer_name", "main_skill", "note", "creation")}
                                     for v in wb.get("volunteer_requests") or []]
    except Exception:
        pass
    try:
        from rescue_net.services.expiry import expiring_report

        rep = expiring_report(posko)
        out["stok_kedaluwarsa"] = [r for r in rep["rows"] if r["state"] != "ok"][:15]
    except Exception:
        pass
    try:
        from rescue_net.control_centre.posko import logistik_board

        b = logistik_board(posko)
        out["stok"] = [{k: c.get(k) for k in ("item", "unit", "stok_ada", "kebutuhan", "gap", "estimasi_habis_hari")}
                       for c in (b.get("stock_cards") or [])[:30]]
    except Exception:
        pass
    return out


def _managed_poskos(actor):
    try:
        from rescue_net.api_posko_manage import _managed

        return _managed(actor)[:10]
    except Exception:
        return []


CHAT_LIMIT, ACTION_LIMIT, WINDOW_S = 30, 60, 600


def _over_limit(user, what, limit):
    """Per-USER limit (owner 2026-11-02: frappe's @rate_limit counts per IP — an office / posko / the owner's
    network shares one public IP, so one person's questions used up everybody's quota)."""
    key = frappe.cache.make_key("rn:assistant:%s:%s" % (what, user))
    n = frappe.cache.incrby(key, 1)
    if n == 1:
        frappe.cache.expire(key, WINDOW_S)
    return n > limit


@frappe.whitelist(methods=["POST"])
def chat(question, page=None, disaster_event=None, posko=None, organization_id=None, history=None):
    user = _user()
    if not user:
        return {"status": "login", "message": "Login dulu untuk memakai Asisten AI."}
    if _over_limit(user, "chat", CHAT_LIMIT):
        return {"status": "rate", "message": "Terlalu banyak pertanyaan dalam 10 menit (maks. %d). Tunggu sebentar lalu coba lagi." % CHAT_LIMIT}
    question = (question or "").strip()[:MAX_Q]
    if not question:
        frappe.throw("Tulis pertanyaan dulu.")
    r, st, msg = _resolve(user, organization_id)
    if st != "ok":
        return {"status": st, "message": msg, "settings": "pages/ai-settings.html"}

    actor = rn_actor(required=False)
    event = resolve_disaster_event(disaster_event) if disaster_event else None
    managed = _managed_poskos(actor) if actor else []
    ctx = {"halaman_saat_ini": (page or "")[:200], "PAGE_MAP": PAGE_MAP,
           "AKSI_TERSEDIA": {k: v["desc"] + " — params: " + ", ".join(v["params"]) for k, v in ACTIONS.items()}}
    if event:
        try:
            ctx["bencana"], full = _event_context(event)
            ctx["akses"] = "lengkap (super admin / Control Centre)" if full else "data publik"
        except Exception:
            frappe.log_error(frappe.get_traceback(), "assistant event context")
    if HOWTO_RE.search(question):
        ctx["MANUAL_PENGGUNA"] = _manual()
    if actor:
        try:
            prof = _my_volunteer_summary(actor)
            if prof:
                ctx["profil_relawan_anda"] = prof
        except Exception:
            frappe.log_error(frappe.get_traceback(), "assistant volunteer profile")
    try:
        ctx["bencana_aktif"] = _active_disasters()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "assistant active disasters")
    ctx["posko_yang_anda_kelola"] = [{"id": p, "title": frappe.db.get_value("RN Posko", p, "title"),
                                      "kelola": "pages/kelola-posko.html?id=" + p} for p in managed]
    target = resolve_posko(posko) if posko else (managed[0] if len(managed) == 1 else None)
    if target and actor and can_manage_posko(actor, target):
        try:
            ctx["posko_aktif"] = _posko_context(target)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "assistant posko context")
    try:
        ctx["hasil_pencarian"] = _search(question, event)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "assistant search")

    msgs = []
    try:
        hist = json.loads(history) if isinstance(history, str) else (history or [])
        for h in hist[-MAX_HISTORY:]:
            if isinstance(h, dict) and h.get("q") and h.get("a"):
                msgs.append("Pertanyaan sebelumnya: " + str(h["q"])[:500] + "\nJawaban: " + str(h["a"])[:800])
    except (ValueError, TypeError):
        pass

    from rescue_net.ai.chat import _llm_chat

    try:
        answer = _llm_chat(r["api_key"], r["model"], SYSTEM_PROMPT,
                           ["Konteks Rescue-Net (JSON):\n" + json.dumps(ctx, default=str, ensure_ascii=False)[:60000]]
                           + msgs + [question],
                           user, r["key_source"], r["owner_type"], r["owner_id"], r["provider"],
                           disaster_event=event, q_chars=len(question), temperature=0.2, feature="assistant")
    except frappe.AuthenticationError:
        return {"status": "key_rejected", "message": "Kunci AI ditolak provider (salah atau kedaluwarsa). Perbarui di AI Settings.",
                "settings": "pages/ai-settings.html"}
    except frappe.ValidationError as e:
        m = str(e)
        st = "quota" if ("habis" in m or "Anggaran" in m) else ("rate" if "Terlalu banyak" in m else "error")
        return {"status": st, "message": m or "Permintaan AI gagal.", "settings": "pages/ai-settings.html"}
    answer, actions = _extract_actions(answer, actor)
    return {"status": "ok", "answer": answer, "actions": actions, "source": SOURCE_LABEL.get(r["owner_type"])}


def _extract_actions(answer, actor):
    """Pull [[AKSI {...}]] lines out of the answer; keep only known actions the user is allowed to run."""
    actions = []
    for raw in _AKSI_RE.findall(answer or ""):
        try:
            a = json.loads(raw)
        except ValueError:
            continue
        name, params = a.get("action"), a.get("params") or {}
        spec = ACTIONS.get(name)
        if not spec or not isinstance(params, dict):
            continue
        params = {k: params[k] for k in spec["params"] if k in params}
        if _allowed(name, params, actor):
            actions.append({"action": name, "params": params, "label": str(a.get("label") or spec["desc"])[:120]})
    cleaned = _AKSI_RE.sub("", answer or "").strip()
    return cleaned, actions[:4]


def _allowed(name, params, actor):
    try:
        if name in ("armada_position", "armada_status"):
            from rescue_net.api_armada import _can_update

            space = frappe.db.get_value("RN Transport Space", params.get("transport_space"),
                                        ["name", "coordination_posko", "created_by_user"], as_dict=True)
            return bool(space and _can_update(space))
        if name == "volunteer_decide":
            posko = frappe.db.get_value("RN Volunteer Booking", params.get("booking"), "posko")
            return bool(posko and (is_system_manager() or (actor and can_manage_posko(actor, posko))))
        if name == "volunteer_profile":
            return bool(actor and _my_volunteer_profiles(actor))
        if name in POSKO_ACTIONS and params.get("posko"):
            return bool(actor and can_manage_posko(actor, resolve_posko(params["posko"])))
    except Exception:
        return False
    return False


@frappe.whitelist(methods=["POST"])
def run_action(action, params=None, latitude=None, longitude=None, accuracy_m=None):
    """The user pressed "Jalankan" on an action the AI proposed. Runs through the normal, permission-checked
    endpoints AS THE USER — the AI itself never writes (ADR-0002: a human decides)."""
    user = _user()
    if not user:
        frappe.throw("Login dulu.", frappe.PermissionError)
    if _over_limit(user, "action", ACTION_LIMIT):
        frappe.throw("Terlalu banyak aksi dalam 10 menit. Tunggu sebentar lalu coba lagi.")
    p = json.loads(params) if isinstance(params, str) else (params or {})
    if action not in ACTIONS:
        frappe.throw("Aksi tidak dikenal.")
    actor = rn_actor(required=False)
    if not _allowed(action, p, actor):
        frappe.throw("Anda tidak berhak menjalankan aksi ini.", frappe.PermissionError)
    if action == "armada_position":
        from rescue_net.api_armada import update_armada_position

        r = update_armada_position(p["transport_space"], latitude, longitude, accuracy_m)
        return {"ok": True, "message": "Posisi armada diperbarui." if not r.get("skipped") else "Posisi belum berubah."}
    if action == "armada_status":
        if p.get("transport_status") not in ARMADA_STATUS:
            frappe.throw("Status armada tidak valid.")
        from rescue_net.logistics.transport import update_transport_space

        update_transport_space(p["transport_space"], transport_status=p["transport_status"])
        return {"ok": True, "message": "Status armada diubah ke " + p["transport_status"] + "."}
    if action == "posko_status":
        if p.get("operational_status") not in POSKO_STATUS:
            frappe.throw("Status posko tidak valid.")
        from rescue_net.api_community_cluster import update_posko

        r = update_posko(resolve_posko(p["posko"]), operational_status=p["operational_status"])
        return {"ok": True, "message": "Status posko diubah." + (" Menunggu persetujuan pusat." if isinstance(r, dict) and r.get("pending") else "")}
    if action == "comms_support":
        from rescue_net.api_comms import set_posko_comms_support

        set_posko_comms_support(p["posko"], offered=p.get("offered"), needed=p.get("needed"))
        return {"ok": True, "message": "Dukungan komunikasi posko disimpan."}
    if action == "stock_expiry":
        from rescue_net.api_stock_expiry import add_lot

        add_lot(resolve_posko(p["posko"]), p.get("item_name"), p.get("unit"), p.get("quantity"), p.get("expiry_date"))
        return {"ok": True, "message": "Tanggal kedaluwarsa dicatat."}
    if action == "posko_contact":
        from rescue_net.api_community_cluster import update_posko

        fields = {k: str(p[k]).strip()[:140] for k in ACTIONS["posko_contact"]["params"][1:] if p.get(k) not in (None, "")}
        if not fields:
            frappe.throw("Tidak ada kontak yang diubah.")
        r = update_posko(resolve_posko(p["posko"]), **fields)
        return {"ok": True, "message": "Kontak posko disimpan." + (" Sebagian menunggu persetujuan pusat." if isinstance(r, dict) and r.get("pending") else "")}
    if action == "need_create":
        urgency = p.get("urgency") or "normal"
        if urgency not in NEED_URGENCY:
            frappe.throw("Urgensi tidak valid.")
        if urgency in ("urgent", "critical") and not (frappe.utils.cint(p.get("jiwa_terdampak")) > 0):
            frappe.throw("Isi jumlah jiwa untuk kebutuhan urgent/critical.")
        from rescue_net.api_logistics import create_need

        create_need(posko=resolve_posko(p["posko"]), item_text=p.get("item_text"), quantity=p.get("quantity"),
                    unit=p.get("unit"), quantity_mode="exact" if p.get("quantity") not in (None, "") else "unknown",
                    urgency=urgency, needed_before=p.get("needed_before") or None,
                    jiwa_terdampak=p.get("jiwa_terdampak") or None)
        return {"ok": True, "message": "Kebutuhan posko ditambahkan."}
    if action == "stock_record":
        from rescue_net.api_logistics import create_stock_observation

        create_stock_observation(posko=resolve_posko(p["posko"]), item_text=p.get("item_text"), quantity=p.get("quantity"),
                                 unit=p.get("unit"), quantity_mode="exact" if p.get("quantity") not in (None, "") else "unknown")
        return {"ok": True, "message": "Stok dicatat."}
    if action == "volunteer_decide":
        if p.get("decision") not in ("confirm", "reject"):
            frappe.throw("Keputusan harus confirm atau reject.")
        from rescue_net.api_volunteer_booking import decide_booking

        decide_booking(p["booking"], p["decision"])
        return {"ok": True, "message": "Permintaan relawan " + ("diterima." if p["decision"] == "confirm" else "ditolak.")}
    if action == "volunteer_profile":
        from rescue_net.api_volunteer_booking import update_my_profile

        fields = {k: p[k] for k in ACTIONS["volunteer_profile"]["params"] if p.get(k) not in (None, "")}
        if not fields:
            frappe.throw("Tidak ada data profil yang diubah.")
        update_my_profile(**fields)
        return {"ok": True, "message": "Profil relawan Anda diperbarui."}
    frappe.throw("Aksi tidak dikenal.")
