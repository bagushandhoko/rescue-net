"""Riwayat kegiatan yang bisa ditelusuri (owner 2026-11-09: "ekosistem berisi gambaran apa yang sedang dilakukan sampai
apa yang dilakukan oleh organisasi, posko atau orang tersebut — bisa di-trace dari siapa / dari posko apa, kegiatannya,
sampai detail, mirip performance atau history").

One collector for every activity of a disaster event, normalised to
{waktu, jenis, teks, posko, posko_title, organisasi, href}. Privacy:
- a CLOSED organisation's posko activities are counted but not itemised for outsiders;
- donors and reporters are never named ("warga" / "donatur"); posko officers act in the posko's name.
"""

from collections import Counter, defaultdict
from datetime import timedelta

import frappe
from frappe.utils import cint, flt, getdate, nowdate

KIND_LABEL = {
    "kirim": "Kiriman logistik dikirim", "terima": "Kiriman logistik diterima", "dapur": "Produksi dapur",
    "medis": "Pasien dilayani", "shelter": "Catatan okupansi shelter", "stok": "Catatan stok", "bukti": "Foto bukti lapangan",
    "relawan": "Penugasan relawan", "laporan": "Laporan warga", "sar": "Laporan orang hilang", "donasi": "Donasi dikonfirmasi",
    "realisasi": "Realisasi dana program",
}
_RECEIVED = ("received", "delivered", "diterima", "completed", "selesai")


def _rows(dt, filters, fields, limit=3000):
    if not frappe.db.exists("DocType", dt):
        return []
    meta = frappe.get_meta(dt)
    cols = [f for f in fields if f in ("name", "creation", "modified") or meta.has_field(f)]
    f = {k: v for k, v in filters.items() if k == "name" or meta.has_field(k)}
    return frappe.get_all(dt, filters=f, fields=cols, order_by="creation desc", limit_page_length=limit)


def _org_tree(org):
    out, todo = {org}, [org]
    while todo:
        kids = frappe.get_all("RN Organization", filters={"parent_organization": ["in", todo]}, pluck="name")
        todo = [k for k in kids if k not in out]
        out.update(todo)
    return out


def _can_see_details(org):
    """Open organisation, or the caller is a system manager / approved member of it."""
    if not org:
        return True
    mode = (frappe.db.get_value("RN Organization", org, "privacy_mode") or "closed").lower()
    if mode == "open":
        return True
    from rescue_net.access_policy import is_system_manager, rn_actor
    if is_system_manager():
        return True
    try:
        actor = rn_actor(required=False)
    except Exception:
        actor = None
    return bool(actor and actor.get("name") and frappe.db.exists(
        "RN Organization Membership", {"user_account": actor.name, "organization": org, "status": "approved"}))


def collect(event, scope="all", scope_id=None, kind=None, limit=200):
    """scope: all | organisasi (scope_id=org, incl. child orgs) | posko (scope_id=posko) | masyarakat."""
    poskos = {p.name: p for p in frappe.get_all("RN Posko", filters={"disaster_event": event},
                                                fields=["name", "title", "organization"], limit_page_length=3000)}
    org_title = {o.name: o.title for o in frappe.get_all("RN Organization", fields=["name", "title"], limit_page_length=5000)}
    see = {}

    def visible(posko):
        org = poskos[posko].organization if posko in poskos else None
        if org not in see:
            see[org] = _can_see_details(org)
        return see[org]

    if scope == "organisasi":
        orgs = _org_tree(scope_id)
        in_scope = {n for n, p in poskos.items() if p.organization in orgs}
    elif scope == "posko":
        in_scope = {scope_id} if scope_id in poskos else set()
    elif scope == "masyarakat":
        in_scope = {n for n, p in poskos.items() if not p.organization}
    else:
        in_scope = set(poskos)

    items, counts, detail_hidden = [], Counter(), 0
    sums = defaultdict(float)

    def add(kind_, when, posko, text, href=None, count_only=False):
        nonlocal detail_hidden
        if kind and kind_ != kind:
            return
        counts[kind_] += 1
        if count_only or (posko and not visible(posko)):
            detail_hidden += 0 if count_only else 1
            return
        p = poskos.get(posko) if posko else None
        items.append({"waktu": str(when or "")[:16], "jenis": kind_, "label": KIND_LABEL.get(kind_, kind_), "teks": text,
                      "posko": posko, "posko_title": p.title if p else None,
                      "organisasi": org_title.get(p.organization) if p and p.organization else None,
                      "href": href or (("posko-detail.html?id=" + posko) if posko else None)})

    pt = lambda n: (poskos[n].title if n in poskos else n) or "posko"
    ev = {"disaster_event": event}

    for f in _rows("RN Distribution Flow", ev, ["name", "source_posko", "destination_posko", "item_name", "quantity", "unit",
                                                  "flow_status", "observed_at", "creation", "modified"]):
        qty = "%g %s %s" % (flt(f.quantity), f.unit or "", f.item_name or "barang")
        if f.source_posko in in_scope:
            add("kirim", f.observed_at or f.creation, f.source_posko, "%s mengirim %s ke %s" % (pt(f.source_posko), qty.strip(), pt(f.destination_posko)))
        if f.destination_posko in in_scope and str(f.flow_status or "").lower() in _RECEIVED:
            add("terima", f.modified, f.destination_posko, "%s menerima %s dari %s" % (pt(f.destination_posko), qty.strip(), pt(f.source_posko)))
    for r in _rows("RN Kitchen Production", ev, ["posko", "meal_name", "portions", "observed_at", "creation"]):
        if r.posko in in_scope:
            sums["porsi"] += cint(r.portions)
            add("dapur", r.observed_at or r.creation, r.posko, "%s memasak %s porsi %s" % (pt(r.posko), cint(r.portions), r.meal_name or ""))
    for r in _rows("RN Medical Case", ev, ["posko", "triage_status", "observed_at", "creation"]):
        if r.posko in in_scope:
            sums["pasien"] += 1
            add("medis", r.observed_at or r.creation, r.posko, "%s melayani 1 pasien%s" % (pt(r.posko), (" (triase %s)" % r.triage_status) if r.triage_status else ""))
    for r in _rows("RN Shelter Occupancy", ev, ["posko", "current_occupancy", "families_count", "observed_at", "creation"]):
        if r.posko in in_scope:
            add("shelter", r.observed_at or r.creation, r.posko, "%s mencatat %s penghuni (%s KK)" % (pt(r.posko), cint(r.current_occupancy), cint(r.families_count)))
    for r in _rows("RN Stock Observation", ev, ["posko", "item_name", "quantity", "unit", "observed_at", "creation"]):
        if r.posko in in_scope:
            add("stok", r.observed_at or r.creation, r.posko, "%s mencatat stok %s: %g %s" % (pt(r.posko), r.item_name or "barang", flt(r.quantity), r.unit or ""))
    for r in _rows("RN Evidence File", ev, ["posko", "title", "creation"]):
        if r.posko in in_scope:
            add("bukti", r.creation, r.posko, "%s mengunggah foto bukti: %s" % (pt(r.posko), (r.title or "").replace("[SIMULASI] ", "")[:90]))
    for r in _rows("RN Volunteer Assignment", ev, ["posko", "assignment_status", "creation"]):
        if r.posko in in_scope:
            add("relawan", r.creation, r.posko, "Relawan ditugaskan di %s" % pt(r.posko))
    for r in _rows("RN Community Report", ev, ["posko", "report_type", "observed_at", "creation"]):
        if (r.posko in in_scope) or (scope in ("all", "masyarakat") and not r.posko):
            add("laporan", r.observed_at or r.creation, r.posko if r.posko in poskos else None,
                "Warga melaporkan %s%s" % (r.report_type or "kondisi", (" ke " + pt(r.posko)) if r.posko in poskos else ""))
    for r in _rows("RN Missing Person Report", ev, ["posko", "creation"]):
        if (r.posko in in_scope) or (scope in ("all", "masyarakat") and not r.posko):
            add("sar", r.creation, r.posko if r.posko in poskos else None, "Laporan orang hilang diterima" + ((" " + pt(r.posko)) if r.posko in poskos else ""))

    # program donasi: milik organisasi dalam lingkup, atau semua (all/masyarakat)
    pf = {"disaster_event": event, "status": ["!=", "cancelled"]}
    progs = {p.name: p for p in frappe.get_all("RN Donor Program", filters=pf,
                                               fields=["name", "program_name", "owner_type", "owner_id", "public_visibility"],
                                               limit_page_length=500)}
    if scope == "organisasi":
        progs = {k: v for k, v in progs.items() if v.owner_type == "organization" and v.owner_id in orgs}
    elif scope == "posko":
        progs = {k: v for k, v in progs.items() if v.owner_type == "posko" and v.owner_id == scope_id}
    progs = {k: v for k, v in progs.items() if v.public_visibility == "summary_public"}
    if progs:
        for d in _rows("RN Cash Donation", {"donor_program": ["in", list(progs)], "status": "received"},
                       ["donor_program", "amount", "confirmed_at", "creation"]):
            sums["dana"] += flt(d.amount)
            add("donasi", d.confirmed_at or d.creation, None, "Donatur menyumbang Rp %s ke %s" % (
                "{:,.0f}".format(flt(d.amount)).replace(",", "."), progs[d.donor_program].program_name),
                href="program-khusus.html?program=" + d.donor_program)
        for u in _rows("RN Donor Program Update", {"program": ["in", list(progs)]}, ["program", "update_title", "amount_spent", "observed_at", "creation"]):
            if flt(u.amount_spent) > 0:
                sums["realisasi"] += flt(u.amount_spent)
                add("realisasi", u.observed_at or u.creation, None, "%s: %s (Rp %s)" % (
                    progs[u.program].program_name, (u.update_title or "").replace("[SIMULASI] ", ""),
                    "{:,.0f}".format(flt(u.amount_spent)).replace(",", ".")), href="program-khusus.html?program=" + u.program)

    items.sort(key=lambda x: x["waktu"], reverse=True)
    # kinerja 7 hari terakhir
    today = getdate(nowdate())
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    per_day = Counter(i["waktu"][:10] for i in items)
    return {
        "counts": [{"jenis": k, "label": KIND_LABEL.get(k, k), "n": n} for k, n in counts.most_common()],
        "total": sum(counts.values()),
        "sums": {k: round(v, 2) for k, v in sums.items()},
        "per_hari": [{"tanggal": d, "n": per_day.get(d, 0)} for d in days],
        "items": items[:max(1, min(cint(limit) or 200, 500))],
        "detail_hidden": detail_hidden,
        "poskos": sorted([{"id": n, "title": poskos[n].title} for n in in_scope if n in poskos and visible(n)], key=lambda x: x["title"] or ""),
    }


def performance_by_party(event):
    """Owner 2026-11-09: Ekosistem = siapa yang terlibat + kinerjanya. Counts only (safe for public, incl. closed orgs):
    per ROOT organisation (children rolled in) and 'masyarakat' (poskos without organisation + public at large)."""
    poskos = {p.name: p for p in frappe.get_all("RN Posko", filters={"disaster_event": event},
                                                fields=["name", "title", "organization", "operational_status"], limit_page_length=3000)}
    parent = {o.name: o for o in frappe.get_all("RN Organization", fields=["name", "title", "parent_organization",
                                                                            "organization_type", "privacy_mode", "verification_status"],
                                                limit_page_length=5000)}

    def root(org):
        seen = set()
        while org and parent.get(org) and parent[org].parent_organization and parent[org].parent_organization in parent and org not in seen:
            seen.add(org)
            org = parent[org].parent_organization
        return org

    party = {}

    def P(key):
        if key not in party:
            o = parent.get(key)
            party[key] = {"id": key, "title": (o.title if o else "Masyarakat Umum"), "organization_type": o.organization_type if o else None,
                          "open": bool(o and (o.privacy_mode or "") == "open"), "verified": bool(o and str(o.verification_status or "") in ("verified", "official_verified", "community_verified")),
                          "anak": set(), "posko": set(), "counts": Counter(), "porsi": 0, "pasien": 0, "dana": 0.0, "realisasi": 0.0, "terakhir": ""}
        return party[key]

    def key_of_posko(n):
        p = poskos.get(n)
        if not p:
            return None
        if not p.organization:
            return "masyarakat"
        r = root(p.organization)
        if r != p.organization:
            P(r)["anak"].add(parent[p.organization].title if p.organization in parent else p.organization)
        return r

    for n, p in poskos.items():
        P(key_of_posko(n))["posko"].add(n)

    def hit(n, kind, when, add=None):
        k = key_of_posko(n) if n else "masyarakat"
        if not k:
            return
        row = P(k)
        row["counts"][kind] += 1
        if add:
            for f, v in add.items():
                row[f] += v
        w = str(when or "")[:16]
        if w > row["terakhir"]:
            row["terakhir"] = w

    ev = {"disaster_event": event}
    for f in _rows("RN Distribution Flow", ev, ["source_posko", "destination_posko", "flow_status", "observed_at", "creation", "modified"]):
        if f.source_posko in poskos:
            hit(f.source_posko, "kirim", f.observed_at or f.creation)
        if f.destination_posko in poskos and str(f.flow_status or "").lower() in _RECEIVED:
            hit(f.destination_posko, "terima", f.modified)
    for r in _rows("RN Kitchen Production", ev, ["posko", "portions", "observed_at", "creation"]):
        hit(r.posko, "dapur", r.observed_at or r.creation, {"porsi": cint(r.portions)})
    for r in _rows("RN Medical Case", ev, ["posko", "observed_at", "creation"]):
        hit(r.posko, "medis", r.observed_at or r.creation, {"pasien": 1})
    for dt, kind in (("RN Shelter Occupancy", "shelter"), ("RN Stock Observation", "stok"), ("RN Evidence File", "bukti"),
                     ("RN Volunteer Assignment", "relawan"), ("RN Missing Person Report", "sar"), ("RN Community Report", "laporan")):
        for r in _rows(dt, ev, ["posko", "observed_at", "creation"]):
            if r.posko in poskos or kind in ("laporan", "sar"):
                hit(r.posko if r.posko in poskos else None, kind, r.get("observed_at") or r.creation)

    progs = frappe.get_all("RN Donor Program", filters={"disaster_event": event, "status": ["!=", "cancelled"]},
                           fields=["name", "owner_type", "owner_id"], limit_page_length=500)
    owner_key = {}
    for pr in progs:
        if pr.owner_type == "organization" and pr.owner_id in parent:
            owner_key[pr.name] = root(pr.owner_id)
        elif pr.owner_type == "posko":
            owner_key[pr.name] = key_of_posko(pr.owner_id) or "masyarakat"
        else:
            owner_key[pr.name] = "masyarakat"
    if owner_key:
        for d in _rows("RN Cash Donation", {"donor_program": ["in", list(owner_key)], "status": "received"}, ["donor_program", "amount", "confirmed_at", "creation"]):
            row = P(owner_key[d.donor_program]); row["counts"]["donasi"] += 1; row["dana"] += flt(d.amount)
            row["terakhir"] = max(row["terakhir"], str(d.confirmed_at or d.creation or "")[:16])
        for u in _rows("RN Donor Program Update", {"program": ["in", list(owner_key)]}, ["program", "amount_spent", "observed_at", "creation"]):
            if flt(u.amount_spent) > 0:
                row = P(owner_key[u.program]); row["counts"]["realisasi"] += 1; row["realisasi"] += flt(u.amount_spent)

    out = []
    for k, r in party.items():
        total = sum(r["counts"].values())
        if not total and not r["posko"]:
            continue
        out.append({"id": k, "title": r["title"], "organization_type": r["organization_type"], "open": r["open"], "verified": r["verified"],
                    "masyarakat": k == "masyarakat", "anak": sorted(r["anak"]), "posko": len(r["posko"]),
                    "kegiatan": total, "per_jenis": [{"jenis": j, "label": KIND_LABEL.get(j, j), "n": n} for j, n in r["counts"].most_common()],
                    "porsi": r["porsi"], "pasien": r["pasien"], "dana": round(r["dana"], 2), "realisasi": round(r["realisasi"], 2),
                    "terakhir": r["terakhir"]})
    out.sort(key=lambda x: (x["masyarakat"], -x["kegiatan"], -x["posko"]))
    return out
