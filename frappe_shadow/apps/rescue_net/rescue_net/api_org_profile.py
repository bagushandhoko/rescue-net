"""Profil Kerja Organisasi — halaman publik (owner 2026-11-08): ringkasan kerja satu organisasi beserta
organisasi anak/ortomnya: posko di peta, peran per bidang, alur bantuan & mitra, program & donasi,
kebutuhan terbuka, kredibilitas.

Privasi: tidak ada kontak pribadi, nama pasien, atau daftar anggota. Organisasi TERTUTUP hanya memberi
identitas, titik posko, dan angka gabungan; rincian per posko, alur, dan garis waktu dari posko organisasi
tertutup tidak dikirim.
"""
from collections import Counter, defaultdict

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt

from rescue_net.services.drill import real_rows

ORG = "RN Organization"
POSKO = "RN Posko"
CLOSED_NEED = {"fulfilled", "closed", "cancelled", "met", "resolved", "done", "rejected"}
RECEIVED = {"received", "partially_received"}
TYPE_LABEL = {
    "logistics": "Logistik", "medical": "Medis", "kitchen": "Dapur Umum", "shelter": "Shelter",
    "transport": "Transportasi", "collection_hub": "Gudang / Collection Hub", "field_assessment": "Asesmen Lapangan",
    "communication": "Komunikasi", "equipment": "Alat Kerja", "volunteer": "Relawan", "sar": "SAR", "command": "Komando",
}
POSKO_PAGE = {
    "medical": "posko-medis-detail.html", "shelter": "shelter-detail.html", "kitchen": "dapur-umum.html",
    "transport": "posko-distribusi.html", "equipment": "posko-alat.html", "communication": "alat-komunikasi.html",
    "volunteer": "management-relawan.html", "sar": "search-found.html",
}


def _is_open(org_row):
    return str(org_row.get("privacy_mode") or "").lower() == "open"


def _org_rows(names):
    return {o.name: o for o in frappe.get_all(
        ORG, filters={"name": ["in", list(names)]},
        fields=["name", "title", "organization_type", "verification_status", "trust_level", "privacy_mode",
                "parent_organization", "status", "contact_person", "trusted_verifier_count",
                "identity_verification_status", "brand_color"])}


def _posko_events(posko_names):
    out = defaultdict(set)
    if not posko_names:
        return out
    for r in frappe.get_all("RN Posko Served Event", filters={"parent": ["in", posko_names], "parenttype": POSKO},
                            fields=["parent", "disaster_event"], limit_page_length=0):
        if r.disaster_event:
            out[r.parent].add(r.disaster_event)
    return out


def _count_by_posko(doctype, poskos, extra=None):
    if not poskos:
        return Counter()
    flt_ = {"posko": ["in", poskos]}
    flt_.update(extra or {})
    return Counter(r.posko for r in frappe.get_all(doctype, filters=flt_, fields=["posko"], limit_page_length=0))


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def org_profile(organization, disaster_event=None):
    if not organization or not frappe.db.exists(ORG, organization):
        frappe.throw("Organisasi tidak ditemukan.")
    root = _org_rows([organization])[organization]
    if str(root.status or "").lower() in ("rejected", "suspended"):
        frappe.throw("Organisasi ini tidak ditampilkan.")

    child_names = frappe.get_all(ORG, filters={"parent_organization": organization}, pluck="name")
    child_names = [c for c in child_names if c != organization]
    orgs = _org_rows([organization] + child_names)
    for c in list(child_names):
        if str(orgs[c].status or "").lower() in ("rejected", "suspended"):
            orgs.pop(c, None)
            child_names.remove(c)
    open_orgs = {n for n, o in orgs.items() if _is_open(o)}

    # ---- posko ------------------------------------------------------------------------------------------------
    poskos = real_rows(frappe.get_all(
        POSKO, filters={"organization": ["in", list(orgs)]},
        fields=["name", "title", "posko_type", "organization", "latitude", "longitude", "operational_status",
                "disaster_event", "address"], limit_page_length=500))
    served = _posko_events([p.name for p in poskos])
    for p in poskos:
        p.events = set(served.get(p.name, set()))
        if p.disaster_event:
            p.events.add(p.disaster_event)
    all_events = set().union(*[p.events for p in poskos]) if poskos else set()
    ev_rows = {e.name: e for e in frappe.get_all("RN Disaster Event", filters={"name": ["in", list(all_events) or [""]]},
                                                 fields=["name", "title", "event_status", "event_type"])}
    if disaster_event:
        poskos = [p for p in poskos if disaster_event in p.events]

    names = [p.name for p in poskos]
    open_names = [p.name for p in poskos if p.organization in open_orgs]
    by_name = {p.name: p for p in poskos}

    # ---- angka kerja ------------------------------------------------------------------------------------------
    cases = _count_by_posko("RN Medical Case", names)
    missing = _count_by_posko("RN Missing Person Report", names)
    found = _count_by_posko("RN Found Person Report", names)
    vols = _count_by_posko("RN Volunteer Assignment", names)
    portions = Counter()
    for r in frappe.get_all("RN Kitchen Production", filters={"posko": ["in", names or [""]]},
                            fields=["posko", "portions"], limit_page_length=0):
        portions[r.posko] += cint(r.portions)
    occupancy = {}
    for r in frappe.get_all("RN Shelter Occupancy", filters={"posko": ["in", names or [""]]},
                            fields=["posko", "current_occupancy", "capacity_total", "creation"],
                            order_by="creation asc", limit_page_length=0):
        occupancy[r.posko] = (cint(r.current_occupancy), cint(r.capacity_total))
    flows = frappe.get_all(
        "RN Distribution Flow",
        filters=[["flow_status", "!=", "cancelled"]],
        or_filters=[["source_posko", "in", names or [""]], ["destination_posko", "in", names or [""]]],
        fields=["name", "source_posko", "destination_posko", "item_name", "quantity", "unit", "flow_status",
                "transport_space", "transport_provider", "transport_type", "modified"],
        order_by="modified desc", limit_page_length=500)
    received_in = [f for f in flows if f.destination_posko in by_name and f.flow_status in RECEIVED]
    sent_out = [f for f in flows if f.source_posko in by_name]
    needs = frappe.get_all("RN Logistic Need", filters={"posko": ["in", names or [""]]},
                           fields=["posko", "item_name", "quantity", "unit", "urgency", "need_status"],
                           order_by="modified desc", limit_page_length=200)
    needs = [n for n in needs if str(n.need_status or "").lower() not in CLOSED_NEED]

    totals = {
        "posko": len(poskos),
        "posko_aktif": sum(1 for p in poskos if str(p.operational_status or "active").lower() in ("active", "aktif", "open")),
        "bencana": len({e for p in poskos for e in p.events}),
        "organisasi": len(orgs),
        "anggota": sum(_member_count(o) for o in orgs),
        "kiriman_diterima": len(received_in),
        "kiriman_keluar": len(sent_out),
        "pasien": sum(cases.values()),
        "porsi": sum(portions.values()),
        "dicari": sum(missing.values()),
        "ditemukan": sum(found.values()),
        "penugasan_relawan": sum(vols.values()),
        "pengungsi": sum(o[0] for o in occupancy.values()),
        "kebutuhan_terbuka": len(needs),
    }

    def metrics(pn):
        m = {}
        if cases[pn]: m["pasien"] = cases[pn]
        if portions[pn]: m["porsi"] = portions[pn]
        if pn in occupancy: m["pengungsi"], m["kapasitas"] = occupancy[pn]
        if missing[pn]: m["dicari"] = missing[pn]
        if found[pn]: m["ditemukan"] = found[pn]
        if vols[pn]: m["penugasan_relawan"] = vols[pn]
        rin = sum(1 for f in received_in if f.destination_posko == pn)
        if rin: m["kiriman_diterima"] = rin
        out = sum(1 for f in sent_out if f.source_posko == pn)
        if out: m["kiriman_keluar"] = out
        return m

    posko_out = []
    for p in poskos:
        is_open = p.organization in open_orgs
        row = {"id": p.name, "title": p.title, "type": p.posko_type, "type_label": TYPE_LABEL.get(p.posko_type, p.posko_type),
               "organization": p.organization, "organization_title": orgs[p.organization].title,
               "lat": flt(p.latitude) if p.latitude not in (None, "") else None,
               "lng": flt(p.longitude) if p.longitude not in (None, "") else None,
               "status": p.operational_status, "open": is_open,
               "events": sorted(e for e in p.events if e in ev_rows),
               "href": POSKO_PAGE.get(p.posko_type, "posko-detail.html")}
        if is_open:
            row["metrics"] = metrics(p.name)
        posko_out.append(row)

    # peran per bidang (gabungan, aman untuk organisasi tertutup)
    roles = {}
    for p in poskos:
        r = roles.setdefault(p.posko_type, {"type": p.posko_type, "label": TYPE_LABEL.get(p.posko_type, p.posko_type),
                                            "posko": 0, "metrics": Counter()})
        r["posko"] += 1
        for k, v in metrics(p.name).items():
            if k != "kapasitas":
                r["metrics"][k] += v
    roles = [dict(r, metrics=dict(r["metrics"])) for r in sorted(roles.values(), key=lambda x: -x["posko"])]

    # ---- alur & mitra (hanya dari posko organisasi terbuka) ---------------------------------------------------
    def ptitle(n):
        return frappe.db.get_value(POSKO, n, "title") if n else None

    def porg(n):
        o = frappe.db.get_value(POSKO, n, "organization") if n else None
        return (o, frappe.db.get_value(ORG, o, "title")) if o else (None, None)

    partners = {}
    alur = []
    for f in [x for x in flows if (x.source_posko in open_names or x.destination_posko in open_names)][:60]:
        src_org, src_title = porg(f.source_posko)
        dst_org, dst_title = porg(f.destination_posko)
        carrier_title = None
        if f.transport_space and frappe.db.exists("RN Transport Space", f.transport_space):
            cp = frappe.db.get_value("RN Transport Space", f.transport_space, "coordination_posko")
            c_org, c_title = porg(cp)
            if c_org and c_org not in orgs:
                partners.setdefault(c_org, {"organization": c_org, "title": c_title, "peran": set()})["peran"].add("angkutan")
            carrier_title = frappe.db.get_value("RN Transport Space", f.transport_space, "provider_name")
        if src_org and src_org not in orgs:
            partners.setdefault(src_org, {"organization": src_org, "title": src_title, "peran": set()})["peran"].add("pengirim bantuan")
        if dst_org and dst_org not in orgs:
            partners.setdefault(dst_org, {"organization": dst_org, "title": dst_title, "peran": set()})["peran"].add("penerima")
        alur.append({"dari": ptitle(f.source_posko) or "Donatur / umum", "ke": ptitle(f.destination_posko), "barang": f.item_name,
                     "jumlah": flt(f.quantity), "satuan": f.unit, "status": f.flow_status,
                     "angkutan": carrier_title or f.transport_provider, "waktu": str(f.modified)})
    partners = [dict(v, peran=sorted(v["peran"])) for v in partners.values()]

    # ---- program & donasi ---------------------------------------------------------------------------------------
    progs = frappe.get_all("RN Donor Program", filters={"owner_type": "organization", "owner_id": ["in", list(orgs)]},
                           fields=["name", "program_name", "status", "budget_target", "budget_received", "disaster_event",
                                   "owner_id", "public_visibility", "target_location"], limit_page_length=100)
    programs = []
    for pr in progs:
        if str(pr.public_visibility or "public").lower() in ("private", "internal", "hidden"):
            continue
        if disaster_event and pr.disaster_event != disaster_event:
            continue
        dons = frappe.get_all("RN Cash Donation", filters={"donor_program": pr.name, "status": ["in", ["received", "confirmed"]]},
                              fields=["amount"], limit_page_length=0)
        upd = frappe.get_all("RN Donor Program Update", filters={"program": pr.name},
                             fields=["update_title", "progress_percent", "observed_at", "creation", "public_visibility"],
                             order_by="creation desc", limit_page_length=5)
        upd = [u for u in upd if str(u.public_visibility or "public").lower() not in ("private", "internal", "hidden")]
        programs.append({"id": pr.name, "event": pr.disaster_event, "title": pr.program_name, "status": pr.status, "lokasi": pr.target_location,
                         "target": flt(pr.budget_target), "terkumpul": flt(pr.budget_received),
                         "donatur": len(dons), "dana_terkonfirmasi": sum(flt(d.amount) for d in dons),
                         "organisasi": orgs[pr.owner_id].title,
                         "progres": cint(upd[0].progress_percent) if upd else 0,
                         "update_terakhir": upd[0].update_title if upd else None})

    # ---- garis waktu (posko organisasi terbuka) -----------------------------------------------------------------
    timeline = []
    for f in received_in:
        if f.destination_posko in open_names:
            timeline.append({"waktu": str(f.modified), "jenis": "logistik",
                             "teks": f"{ptitle(f.destination_posko)} menerima {flt(f.quantity):g} {f.unit or ''} {f.item_name or ''}".strip()})
    for r in frappe.get_all("RN Kitchen Production", filters={"posko": ["in", open_names or [""]]},
                            fields=["posko", "portions", "meal_name", "creation"], order_by="creation desc", limit_page_length=10):
        timeline.append({"waktu": str(r.creation), "jenis": "dapur", "teks": f"{ptitle(r.posko)} memasak {cint(r.portions)} porsi"})
    for r in frappe.get_all("RN Medical Case", filters={"posko": ["in", open_names or [""]]},
                            fields=["posko", "triage_status", "creation"], order_by="creation desc", limit_page_length=10):
        timeline.append({"waktu": str(r.creation), "jenis": "medis",
                         "teks": f"{ptitle(r.posko)} melayani 1 pasien" + (f" (triase {r.triage_status})" if r.triage_status else "")})
    for r in frappe.get_all("RN Missing Person Report", filters={"posko": ["in", open_names or [""]]},
                            fields=["posko", "creation"], order_by="creation desc", limit_page_length=5):
        timeline.append({"waktu": str(r.creation), "jenis": "sar", "teks": f"{ptitle(r.posko)} menerima laporan orang hilang"})
    for p in programs:
        if p["update_terakhir"]:
            timeline.append({"waktu": "", "jenis": "program", "teks": f"{p['title']}: {p['update_terakhir']}"})
    timeline.sort(key=lambda t: t["waktu"], reverse=True)

    checklist = {
        "identitas_organisasi": str(root.verification_status or "").lower() not in ("", "pending", "unverified", "self_reported"),
        "kontak_person": bool(root.contact_person),
        "trusted_verifier": cint(root.trusted_verifier_count) > 0,
    }
    org_list = [{"id": n, "title": o.title, "type": o.organization_type, "verification_status": o.verification_status,
                 "open": n in open_orgs, "is_root": n == organization} for n, o in orgs.items()]

    return {
        "organization": {"id": organization, "title": root.title, "type": root.organization_type,
                         "verification_status": root.verification_status, "trust_level": root.trust_level,
                         "open": organization in open_orgs, "brand_color": root.brand_color,
                         "parent": ({"id": root.parent_organization, "title": frappe.db.get_value(ORG, root.parent_organization, "title")}
                                    if root.parent_organization else None)},
        "organizations": org_list,
        "events": [{"id": e.name, "title": e.title, "status": e.event_status, "type": e.event_type} for e in ev_rows.values()],
        "disaster_event": disaster_event,
        "totals": totals,
        "poskos": posko_out,
        "roles": roles,
        "partners": partners,
        "alur": alur[:25],
        "programs": programs,
        "needs": [{"posko": ptitle(n.posko), "item": n.item_name, "jumlah": flt(n.quantity), "satuan": n.unit,
                   "urgensi": n.urgency} for n in needs if n.posko in open_names][:30],
        "timeline": timeline[:20],
        "checklist": checklist,
    }


def _member_count(org):
    return frappe.db.count("RN Organization Membership", {"organization": org, "status": "approved"})


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def org_list():
    """Organisasi induk yang punya posko — untuk memilih profil (tanpa kontak)."""
    counts = Counter(r.organization for r in real_rows(frappe.get_all(
        POSKO, filters={"organization": ["is", "set"]}, fields=["organization", "disaster_event"], limit_page_length=0)))
    rows = frappe.get_all(ORG, filters={"name": ["in", list(counts) or [""]]},
                          fields=["name", "title", "organization_type", "verification_status", "privacy_mode",
                                  "parent_organization", "status"], limit_page_length=0)
    parents = Counter(r.parent_organization for r in frappe.get_all(ORG, filters={"parent_organization": ["is", "set"]},
                                                                   fields=["parent_organization"], limit_page_length=0))
    out = []
    for r in rows:
        if r.parent_organization or str(r.status or "").lower() in ("rejected", "suspended"):
            continue
        out.append({"id": r.name, "title": r.title, "type": r.organization_type, "verification_status": r.verification_status,
                    "open": _is_open(r), "posko": counts[r.name], "organisasi_anak": parents[r.name]})
    return sorted(out, key=lambda x: (-x["posko"], x["title"] or ""))
