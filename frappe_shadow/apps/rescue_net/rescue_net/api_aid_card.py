"""Kartu keluarga + penerimaan bantuan per putaran (Fase 10b langkah 3).

- Putaran distribusi ditetapkan KOORDINATOR (pengelola shelter / organisasinya / System Manager).
- Satu keluarga menerima paling banyak satu kali per putaran (indeks unik di RN Aid Receipt).
- QR kartu hanya memuat token buram `RNK-XXXXXXXX`; petugas hanya melihat "boleh / sudah menerima pada ...".
  Tidak ada nama anggota di kartu maupun di respons pemindaian. Tidak ada endpoint tamu.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_datetime, now_datetime

from rescue_net.access_policy import rn_actor
from rescue_net.api_shelter import _accessible_shelters, _assert_shelter_access, _can_operate
from rescue_net.services.trace import ALPHABET, LENGTH

import secrets

ROUND, CARD, RECEIPT, HOUSEHOLD = "RN Distribution Round", "RN Household Card", "RN Aid Receipt", "RN Shelter Household"
PREFIX = "RNK-"


def _norm_token(raw):
    t = str(raw or "").strip().upper()
    if t.startswith(PREFIX):
        t = t[len(PREFIX):]
    return t.strip()


def _new_token():
    for _ in range(20):
        t = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        if not frappe.db.exists(CARD, {"card_token": t}):
            return t
    frappe.throw("Gagal membuat token kartu unik.")


def _when(value):
    try:
        return get_datetime(value) if value else now_datetime()
    except Exception:  # noqa: BLE001
        return now_datetime()


def _round_row(r):
    return {"round": r.name, "title": r.title, "posko": r.posko, "item_note": r.item_note or "",
            "status": r.round_status, "opens_at": str(r.opens_at or ""), "closes_at": str(r.closes_at or "")}


@frappe.whitelist()
def my_shelters():
    """Shelter yang boleh dikelola pemanggil (untuk pemilih posko di halaman kartu keluarga)."""
    actor = rn_actor()
    names = _accessible_shelters(actor) if actor else []
    if not names:
        return []
    return frappe.get_all("RN Posko", filters={"name": ["in", names]}, fields=["name", "title"],
                          order_by="title asc", limit_page_length=500)


# ---------- putaran ----------

@frappe.whitelist(methods=["POST"])
def create_round(posko, title, item_note=None, opens_at=None, closes_at=None):
    actor = rn_actor()
    _assert_shelter_access(actor, posko)
    title = " ".join(str(title or "").split())
    if not title:
        frappe.throw("Judul putaran wajib diisi.")
    doc = frappe.get_doc({
        "doctype": ROUND, "title": title[:140], "posko": posko,
        "disaster_event": frappe.db.get_value("RN Posko", posko, "disaster_event"),
        "item_note": (item_note or "").strip()[:500] or None, "round_status": "open",
        "opens_at": _when(opens_at) if opens_at else None, "closes_at": _when(closes_at) if closes_at else None,
        "created_by_user": actor.name if actor else None})
    doc.insert(ignore_permissions=True)
    return _round_row(doc)


@frappe.whitelist(methods=["POST"])
def set_round_status(round, status):
    if status not in ("open", "closed"):
        frappe.throw("Status tidak dikenal.")
    r = frappe.get_doc(ROUND, round)
    _assert_shelter_access(rn_actor(), r.posko)
    r.round_status = status
    r.closed_at = now_datetime() if status == "closed" else None
    r.save(ignore_permissions=True)
    return _round_row(r)


@frappe.whitelist()
def list_rounds(posko):
    _assert_shelter_access(rn_actor(), posko)
    households = frappe.db.count(HOUSEHOLD, {"posko": posko, "household_status": "checked_in"})
    out = []
    for r in frappe.get_all(ROUND, filters={"posko": posko}, fields=["*"], order_by="creation desc", limit_page_length=100):
        row = _round_row(r)
        row["received"] = frappe.db.count(RECEIPT, {"round": r.name})
        row["households"] = households
        out.append(row)
    return out


# ---------- kartu ----------

@frappe.whitelist()
def list_households(posko):
    _assert_shelter_access(rn_actor(), posko)
    active = {c.household: c.card_token for c in frappe.get_all(
        CARD, filters={"posko": posko, "card_status": "active"}, fields=["household", "card_token"], limit_page_length=5000)}
    rows = frappe.get_all(HOUSEHOLD, filters={"posko": posko, "household_status": "checked_in"},
                          fields=["name", "household_code", "members_count"], order_by="household_code asc",
                          limit_page_length=2000)
    return [{"household": h.name, "household_code": h.household_code, "members_count": h.members_count,
             "token": active.get(h.name)} for h in rows]


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=120, seconds=3600)
def issue_card(household, reissue=0):
    """Terbitkan kartu aktif untuk keluarga. Kartu aktif lama dicabut hanya bila reissue=1 (kartu hilang)."""
    h = frappe.db.get_value(HOUSEHOLD, household, ["name", "posko", "household_code", "members_count", "household_status"],
                            as_dict=True)
    if not h:
        frappe.throw("Keluarga tidak ditemukan.", frappe.DoesNotExistError)
    actor = rn_actor()
    _assert_shelter_access(actor, h.posko)
    if h.household_status != "checked_in":
        frappe.throw("Kartu hanya untuk keluarga yang masih tercatat di shelter.")
    cur = frappe.db.get_value(CARD, {"household": household, "card_status": "active"}, ["name", "card_token"], as_dict=True)
    if cur and not cint(reissue):
        return {"token": PREFIX + cur.card_token, "household_code": h.household_code, "members_count": h.members_count,
                "posko": h.posko, "reused": True}
    if cur:
        frappe.db.set_value(CARD, cur.name, {"card_status": "revoked", "revoked_at": now_datetime()})
    doc = frappe.get_doc({"doctype": CARD, "household": household, "posko": h.posko, "card_token": _new_token(),
                          "card_status": "active", "issued_at": now_datetime(), "issued_by": actor.name if actor else None})
    doc.insert(ignore_permissions=True)
    return {"token": PREFIX + doc.card_token, "household_code": h.household_code, "members_count": h.members_count,
            "posko": h.posko, "reused": False}


# ---------- pemindaian & penerimaan ----------

def _eval(token, round_name):
    """-> (state, ctx). state: eligible | already | invalid | revoked | closed | wrong_posko | not_present."""
    tok = _norm_token(token)
    card = frappe.db.get_value(CARD, {"card_token": tok}, ["name", "household", "posko", "card_status"], as_dict=True) if tok else None
    if not card:
        return "invalid", {}
    r = frappe.db.get_value(ROUND, round_name, ["name", "posko", "round_status", "opens_at", "closes_at"], as_dict=True)
    if not r:
        frappe.throw("Putaran tidak ditemukan.", frappe.DoesNotExistError)
    ctx = {"card": card, "round": r}
    if card.card_status != "active":
        return "revoked", ctx
    if card.posko != r.posko:
        return "wrong_posko", ctx
    now = now_datetime()
    if r.round_status != "open" or (r.opens_at and now < get_datetime(r.opens_at)) or (r.closes_at and now > get_datetime(r.closes_at)):
        return "closed", ctx
    if frappe.db.get_value(HOUSEHOLD, card.household, "household_status") != "checked_in":
        return "not_present", ctx
    prev = frappe.db.get_value(RECEIPT, {"round_household": "%s:%s" % (r.name, card.household)}, "received_at")
    if prev:
        ctx["received_at"] = prev
        return "already", ctx
    return "eligible", ctx


def _result(state, ctx):
    out = {"state": state, "ok": state == "eligible"}
    if ctx.get("received_at"):
        out["received_at"] = str(ctx["received_at"])
    if ctx.get("card"):
        out["household_code"] = frappe.db.get_value(HOUSEHOLD, ctx["card"].household, "household_code")
    return out


@frappe.whitelist()
@rate_limit(limit=240, seconds=60)
def check_card(token, round):
    """Petugas: boleh menerima / sudah menerima pada ... (tanpa data pribadi)."""
    r = frappe.db.get_value(ROUND, round, "posko")
    if not r:
        frappe.throw("Putaran tidak ditemukan.", frappe.DoesNotExistError)
    actor = rn_actor()
    if not _can_operate(actor, r):
        frappe.throw("Anda tidak dapat memindai kartu di posko ini", frappe.PermissionError)
    return _result(*_eval(token, round))


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=240, seconds=60)
def record_receipt(token, round, items_note=None, offline_id=None, received_at=None):
    r = frappe.db.get_value(ROUND, round, "posko")
    if not r:
        frappe.throw("Putaran tidak ditemukan.", frappe.DoesNotExistError)
    actor = rn_actor()
    if not _can_operate(actor, r):
        frappe.throw("Anda tidak dapat mencatat penerimaan di posko ini", frappe.PermissionError)
    offline_id = (str(offline_id).strip()[:140] or None) if offline_id else None
    if offline_id:
        prev = frappe.db.get_value(RECEIPT, {"offline_id": offline_id}, ["name", "received_at"], as_dict=True)
        if prev:  # ulangan antrean offline
            return {"state": "recorded", "ok": True, "duplicate": True, "received_at": str(prev.received_at)}
    state, ctx = _eval(token, round)
    if state != "eligible":
        return _result(state, ctx)
    card = ctx["card"]
    doc = frappe.get_doc({
        "doctype": RECEIPT, "round": round, "household": card.household, "card": card.name, "posko": r,
        "round_household": "%s:%s" % (round, card.household), "received_at": _when(received_at),
        "received_at_server": now_datetime(), "received_by": actor.name if actor else None,
        "items_note": (items_note or "").strip()[:500] or None, "offline_id": offline_id})
    try:
        doc.insert(ignore_permissions=True)
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):  # balapan: petugas lain mencatat lebih dulu
        state2, ctx2 = _eval(token, round)
        return _result(state2, ctx2)
    out = _result("eligible", ctx)
    out.update({"state": "recorded", "ok": True, "duplicate": False, "received_at": str(doc.received_at)})
    return out


@frappe.whitelist()
def list_receipts(round):
    r = frappe.db.get_value(ROUND, round, "posko")
    if not r:
        frappe.throw("Putaran tidak ditemukan.", frappe.DoesNotExistError)
    _assert_shelter_access(rn_actor(), r)
    rows = frappe.get_all(RECEIPT, filters={"round": round}, fields=["household", "received_at", "received_by", "items_note"],
                          order_by="received_at desc", limit_page_length=2000)
    codes = {h.name: h.household_code for h in frappe.get_all(
        HOUSEHOLD, filters={"name": ["in", [x.household for x in rows] or [""]]}, fields=["name", "household_code"],
        limit_page_length=2000)}
    return [{"household_code": codes.get(x.household, ""), "received_at": str(x.received_at or ""),
             "items_note": x.items_note or ""} for x in rows]
