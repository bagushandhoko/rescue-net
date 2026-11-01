"""Disaster events: duplicate scoring, merge and undo (owner SOP 2026-11-01).

- `similar_events()` scores how alike two events are (type, distance, time, name) with a
  plain formula — no AI key needed. The same score feeds the "is this the same
  disaster?" check on the create form and the automatic merge suggestions.
- `merge()` moves every record that points at the source event to the target event,
  keeps the source as a `merged` row (its title becomes an alias of the target, old
  links keep resolving through `merged_into`) and writes an RN Event Merge Log with
  every moved row, so `undo()` can put them back.
- Merge suggestions are RN AI Suggestion drafts (ADR-0002): nothing is merged until a
  System Manager accepts.
"""

import difflib
import json
import math
import re

import frappe
from frappe.utils import get_datetime, now_datetime

EVENT = "RN Disaster Event"

# Hidden from every public list.
HIDDEN_STATUSES = ("draft", "proposed", "rejected", "merged")
# Candidates for "the same disaster" (a BMKG draft can be the same quake).
MATCHABLE_STATUSES = ("active", "proposed", "draft")

EVENT_TYPES = {
    "banjir": ("banjir", "flood", "banjir bandang", "rob"),
    "gempa": ("gempa", "earthquake", "lindu"),
    "tsunami": ("tsunami",),
    "longsor": ("longsor", "tanah longsor", "landslide"),
    "erupsi": ("erupsi", "meletus", "letusan", "gunung api", "volcano", "awan panas"),
    "karhutla": ("karhutla", "kebakaran hutan", "kebakaran lahan", "kabut asap", "wildfire"),
    "kebakaran": ("kebakaran", "fire"),
    "angin": ("puting beliung", "angin kencang", "badai", "siklon", "cyclone"),
    "kekeringan": ("kekeringan", "drought", "krisis air"),
    "abrasi": ("abrasi", "gelombang pasang"),
    "wabah": ("wabah", "epidemi", "outbreak", "klb"),
    "lainnya": (),
}

# Data fields (not Link) that store an event reference. Logs (AI usage, sync) stay as written.
DATA_FIELDS = (
    ("RN Consolidated Need Snapshot", "disaster_event"),
    ("RN Consolidation Group Override", "disaster_event"),
    ("RN Verification Action", "disaster_event"),
)
SKIP_DOCTYPES = {EVENT, "RN Event Merge Log"}

_STOP = {"bencana", "di", "dan", "kab", "kabupaten", "kota", "provinsi", "prov", "simulasi", "uji", "draf", "bmkg",
         "the", "of"}


def norm_type(value, title=""):
    """Canonical event type from the stored type, else guessed from the title."""
    v = (value or "").strip().lower()
    if v in EVENT_TYPES:
        return v
    text = f"{v} {title or ''}".lower()
    # longest keyword first so "kebakaran hutan" wins over "kebakaran"
    best = None
    for key, words in EVENT_TYPES.items():
        for w in words:
            if w in text and (best is None or len(w) > len(best[1])):
                best = (key, w)
    return best[0] if best else None


def _words(text):
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOP}


def _title_core(title):
    return " ".join(sorted(_words(re.sub(r"\b(19|20)\d\d\b", " ", title or ""))))


def km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def score_pair(a, b):
    """(score 0-100, reasons[]) for two event-like dicts (title, event_type, latitude,
    longitude, location_summary, started_at)."""
    score, reasons = 0, []
    ta, tb = norm_type(a.get("event_type"), a.get("title")), norm_type(b.get("event_type"), b.get("title"))
    if ta and tb:
        if ta != tb:
            return 0, ["jenis berbeda (%s vs %s)" % (ta, tb)]
        score += 30
        reasons.append("jenis sama (%s)" % ta)
    else:
        score += 10

    la, lo, lb, lob = (_num(a.get("latitude")), _num(a.get("longitude")),
                       _num(b.get("latitude")), _num(b.get("longitude")))
    place_hit = False
    if None not in (la, lo, lb, lob) and not (la == 0 and lo == 0) and not (lb == 0 and lob == 0):
        d = km(la, lo, lb, lob)
        if d <= 25:
            score += 35
        elif d <= 75:
            score += 25
        elif d <= 150:
            score += 10
        place_hit = d <= 150
        reasons.append("jarak %.0f km" % d)
    wa, wb = _words(a.get("location_summary")), _words(b.get("location_summary"))
    if wa and wb and wa & wb:
        common = wa & wb
        score += min(20, 8 * len(common)) if not place_hit else 5
        reasons.append("lokasi sama: " + ", ".join(sorted(common)[:3]))

    sa, sb = a.get("started_at"), b.get("started_at")
    if sa and sb:
        try:
            days = abs((get_datetime(sa) - get_datetime(sb)).total_seconds()) / 86400
            if days <= 3:
                score += 20
            elif days <= 7:
                score += 10
            elif days > 60:
                score -= 15
            reasons.append("selisih waktu %.0f hari" % days)
        except Exception:
            pass

    ca, cb = _title_core(a.get("title")), _title_core(b.get("title"))
    if ca and cb:
        ratio = difflib.SequenceMatcher(None, ca, cb).ratio()
        score += int(15 * ratio)
        if ratio >= 0.6:
            reasons.append("nama mirip (%d%%)" % (ratio * 100))
    return max(0, min(100, score)), reasons


_FIELDS = ["name", "legacy_id", "title", "event_status", "event_type", "latitude", "longitude",
           "location_summary", "started_at", "is_drill", "reporting_organization", "aliases", "creation"]


def _event_fields():
    meta = frappe.get_meta(EVENT)
    return [f for f in _FIELDS if f in ("name", "creation") or meta.has_field(f)]


def similar_events(probe, exclude=None, statuses=MATCHABLE_STATUSES, min_score=45, limit=5):
    """Events alike `probe` (dict), best first. Drills only match drills."""
    rows = frappe.get_all(EVENT, filters={"event_status": ["in", list(statuses)]}, fields=_event_fields(),
                          limit_page_length=1000)
    drill = bool(probe.get("is_drill"))
    out = []
    for r in rows:
        if exclude and r.name == exclude:
            continue
        if bool(r.get("is_drill")) != drill:
            continue
        s, why = score_pair(probe, r)
        if s >= min_score:
            out.append({"name": r.name, "title": r.title, "event_status": r.event_status,
                        "location_summary": r.get("location_summary"),
                        "started_at": str(r.started_at) if r.get("started_at") else None,
                        "score": s, "reasons": why})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


# --------------------------------------------------------------------------- #
# merge suggestions (AI Suggestion, decided by a System Manager)              #
# --------------------------------------------------------------------------- #
SUGGEST_MIN = 60
FEATURE = "event_merge"


def _pair_key(a, b):
    return "|".join(sorted([a, b]))


def _existing_pairs():
    keys = set()
    for p in frappe.get_all("RN AI Suggestion", filters={"feature": FEATURE}, pluck="payload",
                            limit_page_length=0):
        try:
            keys.add(json.loads(p or "{}").get("pair"))
        except Exception:
            pass
    return keys


def _pick_direction(a, b):
    """(source, target): the older event (by start, then creation) stays as the main one;
    an active event always wins over a proposal/draft."""
    rank = {"active": 0, "proposed": 1, "draft": 2}

    def key(e):
        return (rank.get(e.get("event_status"), 3), str(e.get("started_at") or e.get("creation") or ""),
                str(e.get("creation") or ""))
    first, second = sorted([a, b], key=key)
    return second, first


def suggest_for(event_name, existing=None):
    """Create merge suggestions for one event. Returns the suggestion names created."""
    ev = frappe.db.get_value(EVENT, event_name, _event_fields(), as_dict=True)
    if not ev or ev.event_status not in MATCHABLE_STATUSES:
        return []
    existing = _existing_pairs() if existing is None else existing
    made = []
    for c in similar_events(ev, exclude=ev.name, min_score=SUGGEST_MIN):
        pair = _pair_key(ev.name, c["name"])
        if pair in existing:
            continue
        other = frappe.db.get_value(EVENT, c["name"], _event_fields(), as_dict=True)
        source, target = _pick_direction(ev, other)
        payload = {"pair": pair, "source": source.name, "target": target.name,
                   "source_title": source.title, "target_title": target.title,
                   "score": c["score"], "reasons": c["reasons"]}
        sug = frappe.get_doc({"doctype": "RN AI Suggestion", "feature": FEATURE, "ref_doctype": EVENT,
                              "ref_name": source.name, "owner_type": "platform", "owner_id": "platform",
                              "provider": "rules", "model_name": "skor-kemiripan-v1",
                              "payload": json.dumps(payload, ensure_ascii=False), "status": "draft"})
        sug.insert(ignore_permissions=True)
        existing.add(pair)
        made.append(sug.name)
    return made


def daily_scan():
    """Scheduler: look for duplicate pairs among all matchable events (catches events
    created before this feature, BMKG drafts, desk entries)."""
    existing = _existing_pairs()
    made = []
    for name in frappe.get_all(EVENT, filters={"event_status": ["in", ["active", "proposed"]]}, pluck="name",
                               limit_page_length=1000):
        made += suggest_for(name, existing)
    if made:
        notify_admins("Usulan gabung bencana baru: %d pasang" % len(made))
    return made


def notify_admins(subject):
    """Bell notice to every System Manager (deduplicated per subject per day)."""
    try:
        from frappe.utils import nowdate
        users = set(frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"},
                                   pluck="parent")) - {"Guest", "Administrator"}
        for u in users:
            if not frappe.db.get_value("User", u, "enabled"):
                continue
            if frappe.db.exists("Notification Log", {"for_user": u, "subject": subject, "creation": [">=", nowdate()]}):
                continue
            frappe.get_doc({"doctype": "Notification Log", "for_user": u, "type": "Alert",
                            "subject": subject[:140]}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="rn event notify_admins failed")


def notify_user(user, subject):
    try:
        if user and user not in ("Guest",) and frappe.db.exists("User", user):
            frappe.get_doc({"doctype": "Notification Log", "for_user": user, "type": "Alert",
                            "subject": subject[:140]}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="rn event notify_user failed")


# --------------------------------------------------------------------------- #
# merge / undo                                                                #
# --------------------------------------------------------------------------- #
def reference_fields():
    """[(doctype, fieldname, is_child)] for every field that stores an event name."""
    out = set()
    for df in frappe.get_all("DocField", filters={"fieldtype": "Link", "options": EVENT},
                             fields=["parent", "fieldname"], limit_page_length=0):
        out.add((df.parent, df.fieldname))
    for df in frappe.get_all("Custom Field", filters={"fieldtype": "Link", "options": EVENT},
                             fields=["dt", "fieldname"], limit_page_length=0):
        out.add((df.dt, df.fieldname))
    out |= set(DATA_FIELDS)
    res = []
    for dt, fn in sorted(out):
        if dt in SKIP_DOCTYPES or not frappe.db.exists("DocType", dt) or not frappe.db.table_exists(dt):
            continue
        if not frappe.db.has_column(dt, fn):
            continue
        res.append((dt, fn, bool(frappe.db.get_value("DocType", dt, "istable"))))
    return res


def _source_keys(ev):
    keys = {ev.name}
    if ev.get("legacy_id"):
        keys.add(ev.legacy_id)
        if not ev.legacy_id.startswith("disaster_events:"):
            keys.add("disaster_events:" + ev.legacy_id)
    return list(keys)


def linked_counts(event_name):
    ev = frappe.db.get_value(EVENT, event_name, ["name", "legacy_id"], as_dict=True)
    if not ev:
        return {}
    keys = _source_keys(ev)
    out = {}
    for dt, fn, _child in reference_fields():
        n = frappe.db.count(dt, {fn: ["in", keys]})
        if n:
            out[dt] = out.get(dt, 0) + n
    return out


def merge(source, target, user=None, suggestion=None, note=None):
    user = user or frappe.session.user
    if not source or not target or source == target:
        frappe.throw("Pilih dua bencana yang berbeda.")
    src = frappe.db.get_value(EVENT, source, ["name", "legacy_id", "title", "event_status", "aliases", "is_drill"],
                              as_dict=True)
    tgt = frappe.db.get_value(EVENT, target, ["name", "title", "event_status", "aliases", "is_drill"], as_dict=True)
    if not src or not tgt:
        frappe.throw("Bencana tidak ditemukan.")
    if src.event_status == "merged" or tgt.event_status in ("merged", "rejected"):
        frappe.throw("Bencana yang sudah digabung/ditolak tidak bisa dipakai.")
    if bool(src.is_drill) != bool(tgt.is_drill):
        frappe.throw("Bencana latihan tidak bisa digabung dengan bencana nyata.")

    keys = _source_keys(src)
    moved, removed = [], []
    for dt, fn, is_child in reference_fields():
        cols = ["name", fn] + (["parent", "parenttype", "parentfield"] if is_child else [])
        for r in frappe.get_all(dt, filters={fn: ["in", keys]}, fields=cols, limit_page_length=0):
            if is_child and frappe.db.exists(dt, {"parent": r.parent, "parenttype": r.parenttype,
                                                  "parentfield": r.parentfield, fn: target}):
                row = frappe.db.get_value(dt, r.name, "*", as_dict=True)
                removed.append({"doctype": dt, "row": {k: (str(v) if hasattr(v, "isoformat") else v)
                                                       for k, v in row.items()}})
                frappe.db.delete(dt, {"name": r.name})
                continue
            frappe.db.set_value(dt, r.name, fn, target, update_modified=False)
            moved.append([dt, r.name, fn, r.get(fn)])
    # events already merged into the source now point at the target
    for child_ev in frappe.get_all(EVENT, filters={"merged_into": src.name}, pluck="name"):
        frappe.db.set_value(EVENT, child_ev, "merged_into", target, update_modified=False)
        moved.append([EVENT, child_ev, "merged_into", src.name])

    aliases = [a for a in (tgt.aliases or "").splitlines() if a.strip()]
    for a in [src.title] + [x for x in (src.aliases or "").splitlines() if x.strip()]:
        if a and a not in aliases and a != tgt.title:
            aliases.append(a)
    frappe.db.set_value(EVENT, target, "aliases", "\n".join(aliases))
    frappe.db.set_value(EVENT, source, {"event_status": "merged", "merged_into": target})

    log = frappe.get_doc({"doctype": "RN Event Merge Log", "source_event": source, "target_event": target,
                          "status": "done", "merged_by": user, "merged_at": now_datetime(),
                          "suggestion": suggestion, "note": note, "source_prev_status": src.event_status,
                          "moved_count": len(moved), "moved_json": json.dumps(moved),
                          "removed_rows_json": json.dumps(removed)})
    log.insert(ignore_permissions=True)
    return {"log": log.name, "moved": len(moved), "removed_duplicates": len(removed), "source": source,
            "target": target}


def undo(log_name, user=None):
    user = user or frappe.session.user
    log = frappe.get_doc("RN Event Merge Log", log_name)
    if log.status != "done":
        frappe.throw("Penggabungan ini sudah dibatalkan.")
    if frappe.db.get_value(EVENT, log.target_event, "event_status") == "merged":
        frappe.throw("Bencana utama sudah digabung lagi ke bencana lain. Batalkan penggabungan itu dulu.")
    restored = skipped = 0
    for dt, name, fn, old in json.loads(log.moved_json or "[]"):
        cur = frappe.db.get_value(dt, name, fn) if frappe.db.exists(dt, name) else None
        if cur == log.target_event:
            frappe.db.set_value(dt, name, fn, old, update_modified=False)
            restored += 1
        else:
            skipped += 1
    reinserted = 0
    for item in json.loads(log.removed_rows_json or "[]"):
        row = item["row"]
        if frappe.db.exists(item["doctype"], row.get("name")):
            continue
        if not frappe.db.exists(row.get("parenttype"), row.get("parent")):
            continue
        frappe.get_doc(dict(row, doctype=item["doctype"])).db_insert()
        reinserted += 1
    src_title = frappe.db.get_value(EVENT, log.source_event, "title")
    tgt_aliases = [a for a in (frappe.db.get_value(EVENT, log.target_event, "aliases") or "").splitlines()
                   if a.strip() and a != src_title]
    frappe.db.set_value(EVENT, log.target_event, "aliases", "\n".join(tgt_aliases))
    frappe.db.set_value(EVENT, log.source_event, {"event_status": log.source_prev_status or "active",
                                                  "merged_into": None})
    note = f"{restored} data dikembalikan, {reinserted} baris dipulihkan, {skipped} dilewati (sudah berubah)"
    log.status, log.undone_by, log.undone_at, log.undo_note = "undone", user, now_datetime(), note
    log.save(ignore_permissions=True)
    return {"log": log.name, "restored": restored, "reinserted": reinserted, "skipped": skipped}


def final_event(name, max_hops=10):
    """Follow merged_into to the event that is still in use."""
    seen = set()
    while name and max_hops > 0 and name not in seen:
        seen.add(name)
        nxt = frappe.db.get_value(EVENT, name, "merged_into")
        if not nxt:
            return name
        name, max_hops = nxt, max_hops - 1
    return name

