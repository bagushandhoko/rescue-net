from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import cint, flt, getdate, now_datetime

from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    rn_actor,
)


CONTROL_ROLES = {
    "command_center",
    "posko_operator",
    "shelter_operator",
}


HOUSEHOLD_TRANSITIONS = {
    "checked_in": {
        "moved",
        "checked_out",
    },
    "moved": set(),
    "checked_out": set(),
}


NEED_TRANSITIONS = {
    "open": {
        "partially_met",
        "met",
        "cancelled",
    },
    "partially_met": {
        "met",
        "cancelled",
    },
    "met": set(),
    "cancelled": set(),
}


def _member_orgs(actor):
    if not actor or not actor.name:
        return []

    rows = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="organization",
        limit_page_length=500,
    )

    organization = getattr(
        actor,
        "organization",
        None,
    )

    if organization:
        rows.append(organization)

    return list(
        set(x for x in rows if x)
    )


def _candidate_poskos(actor):
    if is_system_manager():
        return frappe.get_all(
            "RN Posko",
            pluck="name",
            limit_page_length=5000,
        )

    result = set()

    for organization in _member_orgs(actor):
        result.update(
            frappe.get_all(
                "RN Posko",
                filters={
                    "organization": organization,
                },
                pluck="name",
                limit_page_length=1000,
            )
        )

    if actor and actor.name:
        result.update(
            frappe.get_all(
                "RN Posko Assignment",
                filters={
                    "user_account": actor.name,
                    "status": "approved",
                },
                pluck="posko",
                limit_page_length=500,
            )
        )

    actor_posko = getattr(
        actor,
        "posko",
        None,
    )

    if actor_posko:
        result.add(actor_posko)

    return sorted(result)


def _can_operate(actor, posko):
    if is_system_manager():
        return True

    if not actor:
        return False

    if can_manage_posko(
        actor,
        posko,
    ):
        return True

    organization = frappe.db.get_value(
        "RN Posko",
        posko,
        "organization",
    )

    return bool(
        organization
        and can_manage_organization(
            actor,
            organization,
        )
    )


def _assert_shelter_access(actor, posko):
    if not _can_operate(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses Shelter ditolak",
            frappe.PermissionError,
        )

    posko_type = frappe.db.get_value(
        "RN Posko",
        posko,
        "posko_type",
    )

    if posko_type != "shelter":
        frappe.throw(
            "Posko ini bukan Shelter",
            frappe.ValidationError,
        )


def _accessible_shelters(actor):
    result = []

    for posko in _candidate_poskos(actor):
        if not _can_operate(
            actor,
            posko,
        ):
            continue

        if frappe.db.get_value(
            "RN Posko",
            posko,
            "posko_type",
        ) != "shelter":
            continue

        result.append(posko)

    return result


def _all_shelters():
    return frappe.get_all(
        "RN Posko",
        filters={
            "posko_type": "shelter",
        },
        pluck="name",
        limit_page_length=5000,
    )


@frappe.whitelist(allow_guest=True)
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor(required=False)

    allowed = _accessible_shelters(
        actor
    )

    if posko:
        # Guests reading a specific posko get a public read-only view of
        # that one posko (same guest-read model as shelter_board); the
        # manager allow-list only gates authenticated actors.
        if actor and posko not in allowed:
            frappe.throw(
                "Akses Shelter ditolak",
                frappe.PermissionError,
            )

        allowed = [posko]

    if not allowed:
        return {
            "poskos": [],
            "occupancies": [],
            "households": [],
            "needs": [],
        }

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "name": ["in", allowed],
        },
        fields=[
            "name",
            "title",
            "posko_type",
            "verification_status",
            "officer_in_charge_phone",
        ],
        order_by="title asc",
        limit_page_length=500,
    )

    occupancies = frappe.get_all(
        "RN Shelter Occupancy",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "shelter_name",
            "capacity_total",
            "current_occupancy",
            "families_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
            "observed_at",
            "verification_status",
        ],
        order_by="observed_at desc, creation desc",
        limit_page_length=2000,
    )

    households = frappe.get_all(
        "RN Shelter Household",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "household_code",
            "members_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
            "household_status",
            "check_in_at",
            "moved_at",
            "checked_out_at",
            "destination",
            "notes",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    needs = frappe.get_all(
        "RN Shelter Need",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "item_name",
            "quantity_mode",
            "quantity_needed",
            "quantity_min",
            "quantity_max",
            "quantity_text",
            "unit",
            "priority",
            "need_status",
            "needed_before",
            "observed_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=2000,
    )

    return {
        "poskos": poskos,
        "occupancies": occupancies,
        "households": households,
        "needs": needs,
    }


@frappe.whitelist()
def create_occupancy(
    posko,
    shelter_name,
    capacity_total=0,
    current_occupancy=0,
    families_count=0,
    infants_count=0,
    children_count=0,
    elderly_count=0,
    pregnant_count=0,
    disability_count=0,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_shelter_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Shelter Occupancy"
    )

    doc.posko = posko
    doc.shelter_name = shelter_name
    doc.capacity_total = cint(
        capacity_total
    )
    doc.current_occupancy = cint(
        current_occupancy
    )
    doc.families_count = cint(
        families_count
    )
    doc.infants_count = cint(
        infants_count
    )
    doc.children_count = cint(
        children_count
    )
    doc.elderly_count = cint(
        elderly_count
    )
    doc.pregnant_count = cint(
        pregnant_count
    )
    doc.disability_count = cint(
        disability_count
    )
    doc.observed_at = now_datetime()
    doc.source_updated_at = (
        doc.observed_at
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    capacity = cint(
        doc.capacity_total
    )

    current = cint(
        doc.current_occupancy
    )

    pct = None

    if capacity > 0:
        pct = round(
            current * 100 / capacity,
            1,
        )

    return {
        "occupancy": doc.name,
        "capacity_total": capacity,
        "current_occupancy": current,
        "occupancy_percent": pct,
        "over_capacity": bool(
            capacity > 0
            and current > capacity
        ),
    }


@frappe.whitelist()
def check_in_household(
    posko,
    household_code,
    members_count,
    infants_count=0,
    children_count=0,
    elderly_count=0,
    pregnant_count=0,
    disability_count=0,
    notes=None,
):
    actor = rn_actor()

    _assert_shelter_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Shelter Household"
    )

    doc.posko = posko
    doc.household_code = household_code
    doc.members_count = cint(
        members_count
    )
    doc.infants_count = cint(
        infants_count
    )
    doc.children_count = cint(
        children_count
    )
    doc.elderly_count = cint(
        elderly_count
    )
    doc.pregnant_count = cint(
        pregnant_count
    )
    doc.disability_count = cint(
        disability_count
    )
    doc.household_status = (
        "checked_in"
    )
    doc.notes = notes
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "household": doc.name,
        "household_code": (
            doc.household_code
        ),
        "members_count": (
            doc.members_count
        ),
        "status": (
            doc.household_status
        ),
    }


@frappe.whitelist()
def update_household_status(
    household,
    new_status,
    destination=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Shelter Household",
        household,
    )

    _assert_shelter_access(
        actor,
        doc.posko,
    )

    current = doc.household_status

    if new_status not in (
        HOUSEHOLD_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi keluarga tidak valid: "
            f"{current} -> {new_status}"
        )

    if (
        new_status == "moved"
        and not destination
    ):
        frappe.throw(
            "Tujuan perpindahan wajib diisi"
        )

    now = now_datetime()

    doc.household_status = (
        new_status
    )

    if new_status == "moved":
        doc.destination = (
            destination
        )
        doc.moved_at = now

    if new_status == "checked_out":
        doc.destination = (
            destination
            or doc.destination
        )
        doc.checked_out_at = now

    doc.save(
        ignore_permissions=True
    )

    return {
        "household": doc.name,
        "previous_status": current,
        "status": (
            doc.household_status
        ),
    }


@frappe.whitelist()
def create_need(
    posko,
    item_name,
    quantity_mode="unknown",
    quantity_needed=None,
    quantity_min=None,
    quantity_max=None,
    quantity_text=None,
    unit=None,
    priority="normal",
    needed_before=None,
    notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_shelter_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Shelter Need"
    )

    doc.posko = posko
    doc.item_name = item_name
    doc.quantity_mode = (
        quantity_mode
    )

    if quantity_needed not in (
        None,
        "",
    ):
        doc.quantity_needed = flt(
            quantity_needed
        )

    if quantity_min not in (
        None,
        "",
    ):
        doc.quantity_min = flt(
            quantity_min
        )

    if quantity_max not in (
        None,
        "",
    ):
        doc.quantity_max = flt(
            quantity_max
        )

    doc.quantity_text = (
        quantity_text
    )
    doc.unit = unit
    doc.priority = priority
    doc.need_status = "open"
    doc.needed_before = (
        needed_before
    )
    doc.notes = notes
    doc.observed_at = (
        now_datetime()
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "shelter_need": doc.name,
        "item_name": doc.item_name,
        "quantity_mode": (
            doc.quantity_mode
        ),
        "status": doc.need_status,
    }


@frappe.whitelist()
def update_need_status(
    shelter_need,
    new_status,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Shelter Need",
        shelter_need,
    )

    _assert_shelter_access(
        actor,
        doc.posko,
    )

    current = doc.need_status

    if new_status not in (
        NEED_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi kebutuhan tidak valid: "
            f"{current} -> {new_status}"
        )

    doc.need_status = new_status

    doc.save(
        ignore_permissions=True
    )

    return {
        "shelter_need": doc.name,
        "previous_status": current,
        "status": doc.need_status,
    }


@frappe.whitelist()
def add_evidence(
    linked_doctype,
    linked_name,
    file_url,
    evidence_type="verification",
    caption=None,
):
    supported = {
        "RN Shelter Occupancy",
        "RN Shelter Household",
        "RN Shelter Need",
    }

    if linked_doctype not in supported:
        frappe.throw(
            "Objek evidence Shelter tidak didukung"
        )

    if not frappe.db.exists(
        linked_doctype,
        linked_name,
    ):
        frappe.throw(
            "Objek evidence tidak ditemukan"
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence Shelter wajib private"
        )

    allowed_types = {
        "photo",
        "document",
        "receipt",
        "handover",
        "transport",
        "verification",
        "other",
    }

    if evidence_type not in allowed_types:
        frappe.throw(
            "Evidence type tidak valid"
        )

    actor = rn_actor()

    posko = frappe.db.get_value(
        linked_doctype,
        linked_name,
        "posko",
    )

    _assert_shelter_access(
        actor,
        posko,
    )

    now = now_datetime()

    doc = frappe.new_doc(
        "RN Operational Evidence"
    )

    doc.linked_doctype = (
        linked_doctype
    )
    doc.linked_name = linked_name
    doc.posko = posko
    doc.file_url = file_url
    doc.evidence_type = (
        evidence_type
    )
    doc.caption = caption
    doc.observed_at = now
    doc.uploaded_at = now
    doc.uploader_user = actor.name
    doc.verification_status = (
        "pending"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "evidence": doc.name,
        "verification_status": (
            doc.verification_status
        ),
        "private": True,
    }


def _latest_occupancies(allowed):
    rows = frappe.get_all(
        "RN Shelter Occupancy",
        filters={
            "posko": ["in", allowed],
        },
        fields=[
            "name",
            "posko",
            "shelter_name",
            "capacity_total",
            "current_occupancy",
            "families_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
            "observed_at",
        ],
        order_by=(
            "observed_at desc, "
            "creation desc"
        ),
        limit_page_length=5000,
    )

    latest = {}

    for row in rows:
        key = (
            row.posko,
            row.shelter_name,
        )

        if key not in latest:
            latest[key] = row

    return list(
        latest.values()
    )


@frappe.whitelist()
def control_centre_shelter():
    actor = rn_actor()

    role = getattr(
        actor,
        "role",
        None,
    )

    if (
        not is_system_manager()
        and role not in CONTROL_ROLES
    ):
        frappe.throw(
            "Akses Control Centre Shelter ditolak",
            frappe.PermissionError,
        )

    if (
        is_system_manager()
        or role == "command_center"
    ):
        allowed = _all_shelters()
    else:
        allowed = _accessible_shelters(
            actor
        )

    if not allowed:
        return {
            "shelter_count": 0,
            "snapshot": {},
            "registered_households": {},
            "needs": {},
            "capacity_alerts": [],
            "privacy": (
                "Aggregate only."
            ),
        }

    latest = _latest_occupancies(
        allowed
    )

    snapshot_capacity = 0
    snapshot_people = 0
    snapshot_families = 0

    vulnerable = defaultdict(int)

    capacity_alerts = []

    for row in latest:
        capacity = cint(
            row.capacity_total
        )
        current = cint(
            row.current_occupancy
        )

        snapshot_capacity += capacity
        snapshot_people += current
        snapshot_families += cint(
            row.families_count
        )

        for fieldname in (
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
        ):
            vulnerable[
                fieldname
            ] += cint(
                row.get(fieldname)
            )

        if capacity > 0:
            pct = (
                current
                * 100
                / capacity
            )

            if pct >= 90:
                capacity_alerts.append({
                    "posko": row.posko,
                    "shelter_name": (
                        row.shelter_name
                    ),
                    "capacity_total": (
                        capacity
                    ),
                    "current_occupancy": (
                        current
                    ),
                    "occupancy_percent": round(
                        pct,
                        1,
                    ),
                })

    active_households = frappe.get_all(
        "RN Shelter Household",
        filters={
            "posko": ["in", allowed],
            "household_status": "checked_in",
        },
        fields=[
            "members_count",
            "infants_count",
            "children_count",
            "elderly_count",
            "pregnant_count",
            "disability_count",
        ],
        limit_page_length=5000,
    )

    registered_people = sum(
        cint(x.members_count)
        for x in active_households
    )

    open_needs = frappe.get_all(
        "RN Shelter Need",
        filters={
            "posko": ["in", allowed],
            "need_status": [
                "in",
                [
                    "open",
                    "partially_met",
                ],
            ],
        },
        fields=[
            "priority",
            "need_status",
        ],
        limit_page_length=5000,
    )

    critical_needs = sum(
        1
        for x in open_needs
        if x.priority == "critical"
    )

    return {
        "shelter_count": len(
            set(
                row.posko
                for row in latest
            )
        ),
        "snapshot": {
            "capacity_total": (
                snapshot_capacity
            ),
            "current_occupancy": (
                snapshot_people
            ),
            "families_count": (
                snapshot_families
            ),
            "vulnerable": dict(
                vulnerable
            ),
        },
        "registered_households": {
            "active_households": len(
                active_households
            ),
            "registered_people": (
                registered_people
            ),
        },
        "needs": {
            "open_or_partial": len(
                open_needs
            ),
            "critical": critical_needs,
        },
        "capacity_alerts": (
            capacity_alerts
        ),
        "privacy": (
            "Occupancy snapshot dan "
            "registrasi keluarga adalah "
            "dua sumber berbeda dan tidak "
            "dijumlahkan otomatis. "
            "Tidak ada identitas korban "
            "dalam agregat Control Centre."
        ),
    }


_BASIC_NEED_CATALOG = [
    ("Makanan", ("makan", "beras", "nasi", "sembako")),
    ("Air Bersih", ("air",)),
    ("Sanitasi", ("sanitasi", "toilet", "mck", "disinfektan", "sabun")),
    ("Selimut", ("selimut", "matras")),
    ("Perlengkapan Bayi", ("bayi", "mpasi", "susu", "popok")),
]

_VULNERABLE_LABELS = {
    "infants_count": "Bayi (0-1 th)",
    "children_count": "Anak-anak (0-17 th)",
    "elderly_count": "Lansia (60+ th)",
    "pregnant_count": "Ibu Hamil",
    "disability_count": "Disabilitas",
}

_SANITATION_KEYWORDS = ("sanitasi", "toilet", "mck", "disinfektan", "sabun")
_WATER_KEYWORDS = ("air bersih", "air minum")


def _event_shelters(event):
    filters = [["disaster_event", "=", event]]
    or_filters = [["posko_type", "=", "shelter"], ["rn_fn_shelter", "=", 1]]
    return frappe.get_all(
        "RN Posko",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "title", "posko_type", "address", "city_name"],
        limit_page_length=500,
    )


def _drill(title, sub, href):
    return {"title": title, "sub": sub, "href": href}


@frappe.whitelist(allow_guest=True)
def shelter_board(disaster_event=None):
    """Shelter & Akomodasi overview (matches the DMS mock-up), guest read-only.

    Cross-shelter dashboard for one disaster event: KPI totals + drill
    items, Daftar Shelter, Kapasitas & Okupansi donut, Kebutuhan Dasar
    (keyword-matched against open RN Shelter Need, not a fixed catalog with
    invented thresholds), Kelompok Rentan, Check-in/Check-out hari ini
    (real RN Shelter Household rows), Peringatan Keselamatan (overcapacity +
    critical needs — no safety/sanitation status field exists on RN Shelter
    Occupancy yet, so nothing is fabricated there) and the evidence strip.
    "Akomodasi Relawan/Petugas" and literal toilet/water-point counts from
    the mock-up have no backing doctype — honestly omitted rather than
    invented (see HANDOVER.md).
    """
    event = resolve_disaster_event(disaster_event) or disaster_event

    shelters = _event_shelters(event)
    posko_names = [s.name for s in shelters]
    posko_by_name = {s.name: s for s in shelters}

    if not posko_names:
        return {
            "disaster_event": event,
            "generated_at": now_datetime(),
            "totals": {}, "kpi_items": {}, "daftar_shelter": [],
            "kapasitas_okupansi": {}, "kebutuhan_dasar": [],
            "kelompok_rentan": [], "checkin_checkout": {},
            "peringatan": [], "bukti": [], "bukti_total": 0,
        }

    latest = _latest_occupancies(posko_names)
    latest_by_posko = {}
    for row in latest:
        # one row per posko (first shelter_name encountered, i.e. most
        # recently observed thanks to _latest_occupancies' ordering)
        latest_by_posko.setdefault(row.posko, row)

    total_penghuni = 0
    kapasitas_maksimal = 0
    overcapacity_rows = []
    vulnerable_totals = defaultdict(int)
    vulnerable_by_shelter = defaultdict(lambda: defaultdict(int))
    daftar_shelter = []

    for posko in posko_names:
        row = latest_by_posko.get(posko)
        p = posko_by_name[posko]
        cap = cint(row.capacity_total) if row else 0
        cur = cint(row.current_occupancy) if row else 0
        total_penghuni += cur
        kapasitas_maksimal += cap
        pct = round(cur * 100 / cap, 1) if cap else None
        over = bool(cap and cur > cap)
        if over:
            overcapacity_rows.append({
                "posko": posko, "title": p.title, "capacity_total": cap,
                "current_occupancy": cur, "occupancy_percent": pct,
            })

        for field, label in _VULNERABLE_LABELS.items():
            v = cint(row.get(field)) if row else 0
            vulnerable_totals[field] += v
            vulnerable_by_shelter[field][posko] = v

        daftar_shelter.append({
            "posko": posko,
            "title": p.title,
            "lokasi": p.city_name or p.address or "-",
            "penghuni": cur,
            "kapasitas": cap,
            "okupansi_pct": pct,
            "status": "overcapacity" if over else "aman",
            "href": "shelter-detail.html?id=" + posko + "&event=" + (event or ""),
        })

    daftar_shelter.sort(key=lambda r: -(r["okupansi_pct"] or 0))

    kelompok_rentan_total = sum(vulnerable_totals.values())

    # Open shelter needs, keyword-matched to the basic-need catalog.
    open_needs = frappe.get_all(
        "RN Shelter Need",
        filters={"posko": ["in", posko_names], "need_status": ["in", ["open", "partially_met"]]},
        fields=["name", "posko", "item_name", "priority", "quantity_needed", "unit"],
        limit_page_length=1000,
    )
    urgent_terms = {"critical", "urgent"}

    kebutuhan_dasar = []
    for label, keywords in _BASIC_NEED_CATALOG:
        matches = [n for n in open_needs if any(k in (n.item_name or "").lower() for k in keywords)]
        kritis = any(str(n.priority).lower() in urgent_terms for n in matches)
        kebutuhan_dasar.append({
            "label": label,
            "status": "kritis" if kritis else ("perlu" if matches else "cukup"),
            "open_count": len(matches),
        })

    air_bersih_kritis = sum(
        1 for posko in posko_names
        if any(
            n.posko == posko and str(n.priority).lower() in urgent_terms
            and any(k in (n.item_name or "").lower() for k in _WATER_KEYWORDS)
            for n in open_needs
        )
    )
    sanitasi_kritis = sum(
        1 for posko in posko_names
        if any(
            n.posko == posko and str(n.priority).lower() in urgent_terms
            and any(k in (n.item_name or "").lower() for k in _SANITATION_KEYWORDS)
            for n in open_needs
        )
    )

    # Kelompok Rentan table: category -> total, %, shelter with the most.
    kelompok_rentan = []
    for field, label in _VULNERABLE_LABELS.items():
        total = vulnerable_totals[field]
        top_posko = max(vulnerable_by_shelter[field], key=lambda k: vulnerable_by_shelter[field][k], default=None)
        kelompok_rentan.append({
            "label": label,
            "jumlah": total,
            "pct": round(100.0 * total / total_penghuni, 1) if total_penghuni else 0,
            "lokasi_terbanyak": posko_by_name[top_posko].title if top_posko and vulnerable_by_shelter[field][top_posko] else "-",
        })
    kelompok_rentan.sort(key=lambda r: -r["jumlah"])

    # Check-in / check-out hari ini (real RN Shelter Household rows).
    today = getdate()
    households = frappe.get_all(
        "RN Shelter Household",
        filters={"posko": ["in", posko_names]},
        fields=["name", "posko", "household_code", "members_count", "household_status",
                "check_in_at", "moved_at", "checked_out_at"],
        limit_page_length=2000,
    )
    checkin_today = [h for h in households if h.check_in_at and getdate(h.check_in_at) == today]
    checkout_today = [h for h in households if h.checked_out_at and getdate(h.checked_out_at) == today]
    moved_today = [h for h in households if h.moved_at and getdate(h.moved_at) == today]

    checkin_checkout = {
        "checkin_people": sum(cint(h.members_count) for h in checkin_today),
        "checkin_households": len(checkin_today),
        "checkout_people": sum(cint(h.members_count) for h in checkout_today),
        "checkout_households": len(checkout_today),
        "moved_people": sum(cint(h.members_count) for h in moved_today),
        "moved_households": len(moved_today),
    }

    # Peringatan Keselamatan: overcapacity + critical open needs (only real,
    # derivable signals — no fabricated safety/sanitation status).
    peringatan = []
    for r in overcapacity_rows:
        peringatan.append({
            "title": r["title"],
            "sub": f"Kapasitas melebihi 100% (+{r['current_occupancy'] - r['capacity_total']} orang)",
            "href": "shelter-detail.html?id=" + r["posko"] + "&event=" + (event or ""),
            "level": "critical",
        })
    for n in open_needs:
        if str(n.priority).lower() == "critical":
            p = posko_by_name.get(n.posko)
            peringatan.append({
                "title": (p.title if p else n.posko) + " — " + n.item_name,
                "sub": "Kebutuhan kritis terbuka",
                "href": "shelter-detail.html?id=" + n.posko + "&event=" + (event or ""),
                "level": "critical",
            })
    peringatan.sort(key=lambda r: 0 if r.get("level") == "critical" else 1)

    # Evidence strip, same unified feed as other posko pages.
    from rescue_net.api_control_centre import event_evidence
    bukti = []
    try:
        for row in event_evidence(event, limit=80):
            if row.get("posko") in posko_names or row.get("linked_object_id") in posko_names:
                bukti.append(row)
        bukti.sort(key=lambda r: str(r.get("created_at") or r.get("creation") or ""), reverse=True)
        bukti = bukti[:8]
    except Exception:
        bukti = []

    return {
        "disaster_event": event,
        "generated_at": now_datetime(),
        "totals": {
            "total_penghuni": total_penghuni,
            "kapasitas_maksimal": kapasitas_maksimal,
            "overcapacity": len(overcapacity_rows),
            "kelompok_rentan": kelompok_rentan_total,
            "air_bersih_kritis": air_bersih_kritis,
            "sanitasi_kritis": sanitasi_kritis,
        },
        "kpi_items": {
            "shelter_items": [
                _drill(s["title"], f"{s['penghuni']}/{s['kapasitas']} · {s['status']}", s["href"])
                for s in daftar_shelter
            ],
            "overcapacity_items": [
                _drill(r["title"], f"{r['current_occupancy']}/{r['capacity_total']} ({r['occupancy_percent']}%)",
                       "shelter-detail.html?id=" + r["posko"] + "&event=" + (event or ""))
                for r in overcapacity_rows
            ],
            "air_bersih_items": [
                _drill(posko_by_name[n.posko].title, n.item_name + " · kritis",
                       "shelter-detail.html?id=" + n.posko + "&event=" + (event or ""))
                for n in open_needs
                if str(n.priority).lower() in urgent_terms
                and any(k in (n.item_name or "").lower() for k in _WATER_KEYWORDS)
            ],
            "sanitasi_items": [
                _drill(posko_by_name[n.posko].title, n.item_name + " · kritis",
                       "shelter-detail.html?id=" + n.posko + "&event=" + (event or ""))
                for n in open_needs
                if str(n.priority).lower() in urgent_terms
                and any(k in (n.item_name or "").lower() for k in _SANITATION_KEYWORDS)
            ],
        },
        "daftar_shelter": daftar_shelter,
        "kapasitas_okupansi": {
            "terisi": total_penghuni,
            "tersedia": max(0, kapasitas_maksimal - total_penghuni),
            "kapasitas_max": kapasitas_maksimal,
            "pct": round(100.0 * total_penghuni / kapasitas_maksimal, 1) if kapasitas_maksimal else 0,
        },
        "kebutuhan_dasar": kebutuhan_dasar,
        "kelompok_rentan": kelompok_rentan,
        "checkin_checkout": checkin_checkout,
        "peringatan": peringatan,
        "bukti": bukti,
        "bukti_total": len(bukti),
    }
