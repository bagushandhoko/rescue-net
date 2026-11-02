"""Asisten AI di setiap halaman (owner 2026-11-02).

"buat semacam link untuk user bisa komunikasi dengan AI-nya di setiap halaman; ingat kalau dia belum setting
AI key dan/atau tokennya habis; dia bisa gunakan AI untuk atur posko dan cari data di Rescue-Net."

- status(): is AI usable for this user right now (own key / shared organisation key / platform key), and why not.
- chat(): one question (+ short history). Context = public data of the disaster, a keyword search over
  Rescue-Net (poskos, organisations, disasters, open needs), and — only for poskos the user MANAGES — that
  posko's pending work, stock, expiry and warnings. Full operational context only for System Manager /
  Control Centre. The AI never changes data (ADR-0002): it answers and points to the page/tool to use.
- Missing key, spent quota, rejected key, rate limit → a friendly `status` instead of an error.
"""

import json
import re

import frappe
from frappe.rate_limiter import rate_limit

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
}

SYSTEM_PROMPT = """Anda adalah Asisten AI Rescue-Net (platform koordinasi bencana di Indonesia).
Jawab dalam bahasa Indonesia sederhana, singkat dan praktis.
Tugas: (1) membantu pengelola mengatur posko — beri langkah konkret dan sebut halaman/alat yang dipakai dari PAGE_MAP;
(2) mencari dan merangkum data Rescue-Net dari konteks yang diberikan (posko, organisasi, bencana, kebutuhan, stok).
Aturan:
- Gunakan HANYA data di konteks. Kalau tidak ada, katakan tidak ditemukan — jangan mengarang angka, nama, atau nomor.
- Anda TIDAK bisa mengubah data. Untuk mengubah, arahkan ke halaman/tombol yang tepat.
- Jangan menampilkan data pribadi yang tidak ada di konteks; jangan menebak identitas pasien/orang hilang.
- Sebut nama posko/bencana persis seperti di konteks, dan sertakan tautan relatif bila ada (field href).
- Bila pertanyaan di luar Rescue-Net/kebencanaan, jawab singkat dan arahkan kembali.
AKSI (owner 2026-11-02): Anda BOLEH mengusulkan aksi perubahan untuk posko yang dikelola pengguna — pengguna sendiri
yang menekan tombol "Jalankan". Usulkan hanya aksi dari AKSI_TERSEDIA, hanya untuk ID yang ada di konteks
(posko_yang_anda_kelola / posko_aktif / armada), dan hanya bila pengguna memintanya atau jelas membantu.
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
}
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


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=600)
def chat(question, page=None, disaster_event=None, posko=None, organization_id=None, history=None):
    user = _user()
    if not user:
        return {"status": "login", "message": "Login dulu untuk memakai Asisten AI."}
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
        if params.get("posko"):
            return bool(actor and can_manage_posko(actor, resolve_posko(params["posko"])))
    except Exception:
        return False
    return False


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=600)
def run_action(action, params=None, latitude=None, longitude=None, accuracy_m=None):
    """The user pressed "Jalankan" on an action the AI proposed. Runs through the normal, permission-checked
    endpoints AS THE USER — the AI itself never writes (ADR-0002: a human decides)."""
    user = _user()
    if not user:
        frappe.throw("Login dulu.", frappe.PermissionError)
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
    frappe.throw("Aksi tidak dikenal.")
