from collections import defaultdict

import frappe
from rescue_net.reference_resolver import resolve_disaster_event, resolve_posko
from frappe.utils import flt, now_datetime
from frappe.rate_limiter import rate_limit

from rescue_net.access_policy import (
    can_manage_organization,
    can_manage_posko,
    is_system_manager,
    public_posko_allowed,
    rn_actor,
)


OPERATOR_ROLES = {
    "posko_operator",
    "medical_operator",
}


# status graphs + the case/evacuation cascade live in the controllers (phase 2)
from rescue_net.rn_medical.doctype.rn_medical_case.rn_medical_case import CASE_TRANSITIONS  # noqa: E402,F401
from rescue_net.rn_medical.doctype.rn_medical_evacuation.rn_medical_evacuation import EVAC_TRANSITIONS  # noqa: E402,F401


def _member_orgs(actor):
    if not actor or not actor.name:
        return []

    result = frappe.get_all(
        "RN Organization Membership",
        filters={
            "user_account": actor.name,
            "status": "approved",
        },
        pluck="organization",
        limit_page_length=500,
    )

    if getattr(
        actor,
        "organization",
        None,
    ):
        result.append(actor.organization)

    return list(
        set(x for x in result if x)
    )


def _accessible_poskos(actor):
    if is_system_manager():
        return frappe.get_all(
            "RN Posko",
            pluck="name",
            limit_page_length=5000,
        )

    result = set()

    for org in _member_orgs(actor):
        result.update(
            frappe.get_all(
                "RN Posko",
                filters={
                    "organization": org
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

    if actor and getattr(
        actor,
        "posko",
        None,
    ):
        result.add(actor.posko)

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


def _assert_medical_access(actor, posko):
    if not _can_operate(
        actor,
        posko,
    ):
        frappe.throw(
            "Akses medis Posko ditolak",
            frappe.PermissionError,
        )

    posko_type = frappe.db.get_value(
        "RN Posko",
        posko,
        "posko_type",
    )

    if posko_type != "medical":
        frappe.throw(
            "Posko ini bukan Posko Medis",
            frappe.ValidationError,
        )


@frappe.whitelist()
def dashboard(posko=None):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()
    allowed = _accessible_poskos(actor)

    allowed = [
        p
        for p in allowed
        if _can_operate(actor, p)
        and frappe.db.get_value(
            "RN Posko",
            p,
            "posko_type",
        ) == "medical"
    ]

    if posko:
        if posko not in allowed:
            frappe.throw(
                "Akses Posko Medis ditolak",
                frappe.PermissionError,
            )

        allowed = [posko]

    if not allowed:
        return {
            "poskos": [],
            "cases": [],
            "supply_uses": [],
            "evacuations": [],
        }

    poskos = frappe.get_all(
        "RN Posko",
        filters={
            "name": ["in", allowed]
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

    cases = frappe.get_all(
        "RN Medical Case",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "name",
            "posko",
            "patient_code",
            "patient_name",
            "age_group",
            "gender",
            "complaint",
            "severity",
            "triage_status",
            "case_status",
            "treatment_notes",
            "verification_status",
            "observed_at",
            "source_updated_at",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    supply_uses = frappe.get_all(
        "RN Medical Supply Use",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "name",
            "posko",
            "medical_case",
            "item_name",
            "quantity",
            "unit",
            "notes",
            "used_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    evacuations = frappe.get_all(
        "RN Medical Evacuation",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "name",
            "posko",
            "medical_case",
            "provider_name",
            "transport_reference",
            "vehicle_contact",
            "destination_facility",
            "evacuation_status",
            "requested_at",
            "departed_at",
            "arrived_at",
            "handover_at",
            "verification_status",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    return {
        "poskos": poskos,
        "cases": cases,
        "supply_uses": supply_uses,
        "evacuations": evacuations,
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_patients(posko=None):
    """Guest-safe patient roster for a PUBLIC medical posko.

    Purpose is family reunification: so relatives can look for a victim and
    see what happened to them. It exposes identity + outcome only — patient
    code, name, age group, gender, triage colour, case status and the latest
    evacuation destination. It NEVER exposes the complaint, treatment notes,
    supply use or officer contact (those stay behind api_medical.dashboard,
    which is actor-gated). Returns {allowed, posko, patients}; allowed is
    False when the posko is not a public medical posko, and the frontend then
    shows the petugas-only notice instead.
    """
    posko = resolve_posko(posko)
    if not posko:
        return {"allowed": False, "posko": None, "patients": []}

    if frappe.db.get_value("RN Posko", posko, "posko_type") != "medical":
        return {"allowed": False, "posko": posko, "patients": []}

    if not public_posko_allowed(posko):
        return {"allowed": False, "posko": posko, "patients": []}

    info = frappe.db.get_value(
        "RN Posko", posko, ["name", "title"], as_dict=True
    )

    cases = frappe.get_all(
        "RN Medical Case",
        filters={"posko": posko},
        fields=[
            "name",
            "patient_code",
            "patient_name",
            "patient_kind",
            "age_group",
            "gender",
            "triage_status",
            "case_status",
            "observed_at",
            "source_updated_at",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    latest_evac = {}
    for e in frappe.get_all(
        "RN Medical Evacuation",
        filters={"posko": posko},
        fields=[
            "medical_case",
            "evacuation_status",
            "destination_facility",
            "requested_at",
            "departed_at",
            "arrived_at",
            "handover_at",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    ):
        k = e.get("medical_case")
        if not k:
            continue
        t = str(
            e.get("handover_at")
            or e.get("arrived_at")
            or e.get("departed_at")
            or e.get("requested_at")
            or ""
        )
        if k not in latest_evac or t > latest_evac[k]["_t"]:
            latest_evac[k] = {
                "_t": t,
                "evacuation_status": e.get("evacuation_status"),
                "destination_facility": e.get("destination_facility"),
            }

    patients = []
    for c in cases:
        ev = latest_evac.get(c["name"])
        patients.append(
            {
                "patient_code": c.get("patient_code"),
                "patient_name": c.get("patient_name"),
                "patient_kind": c.get("patient_kind"),
                "age_group": c.get("age_group"),
                "gender": c.get("gender"),
                "triage_status": c.get("triage_status"),
                "case_status": c.get("case_status"),
                "updated_at": c.get("source_updated_at") or c.get("observed_at"),
                "evacuation_status": ev["evacuation_status"] if ev else None,
                "destination_facility": ev["destination_facility"] if ev else None,
            }
        )

    return {"allowed": True, "posko": info, "patients": patients}


@frappe.whitelist()
def create_case(
    posko,
    patient_code,
    complaint,
    age_group="unknown",
    gender="unknown",
    severity="mild",
    triage_status="green",
    treatment_notes=None,
    patient_kind="manusia",
    patient_name=None,
    has_disability=0,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_medical_access(
        actor,
        posko,
    )

    if not patient_code:
        frappe.throw(
            "Kode pasien wajib diisi"
        )

    if not complaint:
        frappe.throw(
            "Keluhan / kondisi wajib diisi"
        )

    doc = frappe.new_doc(
        "RN Medical Case"
    )

    doc.posko = posko
    doc.patient_code = patient_code
    doc.patient_name = (str(patient_name).strip() or None) if patient_name else None
    doc.complaint = complaint
    doc.age_group = age_group
    doc.gender = gender
    if doc.meta.has_field("has_disability"):
        doc.has_disability = 1 if str(has_disability).lower() in ("1", "true", "yes", "ya") else 0
    doc.severity = severity
    doc.triage_status = triage_status
    doc.patient_kind = "satwa" if str(patient_kind or "").strip().lower() == "satwa" else "manusia"
    doc.case_status = "active"
    doc.treatment_notes = (
        treatment_notes
    )
    doc.verification_status = (
        "self_reported"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "medical_case": doc.name,
        "patient_code": doc.patient_code,
        "triage_status": doc.triage_status,
        "case_status": doc.case_status,
    }


@frappe.whitelist()
def update_case_status(
    medical_case,
    new_status,
    treatment_notes=None,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Medical Case",
        medical_case,
    )

    _assert_medical_access(
        actor,
        doc.posko,
    )

    current = doc.case_status

    if new_status not in (
        CASE_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi kasus tidak valid: "
            f"{current} -> {new_status}"
        )

    doc.case_status = new_status

    if treatment_notes:
        doc.treatment_notes = (
            treatment_notes
        )

    doc.source_updated_at = (
        now_datetime()
    )

    doc.save(
        ignore_permissions=True
    )

    _log_case_update(
        doc,
        "status",
        note=treatment_notes,
        previous_status=current,
        new_status=doc.case_status,
    )

    return {
        "medical_case": doc.name,
        "previous_status": current,
        "case_status": doc.case_status,
    }


@frappe.whitelist()
def record_supply_use(
    posko,
    item_name,
    quantity,
    unit,
    medical_case=None,
    notes=None,
):
    # RN_CANONICAL_REF posko = resolve_posko(posko)
    posko = resolve_posko(posko)
    actor = rn_actor()

    _assert_medical_access(
        actor,
        posko,
    )

    qty = flt(quantity)

    if qty <= 0:
        frappe.throw(
            "Jumlah pemakaian harus lebih dari 0"
        )

    if medical_case:
        case_posko = frappe.db.get_value(
            "RN Medical Case",
            medical_case,
            "posko",
        )

        if case_posko != posko:
            frappe.throw(
                "Medical Case berasal dari "
                "Posko yang berbeda"
            )

    doc = frappe.new_doc(
        "RN Medical Supply Use"
    )

    doc.posko = posko
    doc.medical_case = (
        medical_case
    )
    doc.item_name = item_name
    doc.quantity = qty
    doc.unit = unit
    doc.notes = notes

    doc.insert(
        ignore_permissions=True
    )

    return {
        "medical_supply_use": doc.name,
        "quantity": doc.quantity,
        "unit": doc.unit,
        "stock_updated": False,
        "note": (
            "Pemakaian medis tidak otomatis "
            "mengubah Stock Observation."
        ),
    }


@frappe.whitelist()
def create_evacuation(
    posko,
    medical_case,
    destination_facility,
    provider_name=None,
    transport_reference=None,
    vehicle_contact=None,
    notes=None,
):
    actor = rn_actor()

    _assert_medical_access(
        actor,
        posko,
    )

    case = frappe.get_doc(
        "RN Medical Case",
        medical_case,
    )

    if case.posko != posko:
        frappe.throw(
            "Medical Case berasal dari "
            "Posko yang berbeda"
        )

    doc = frappe.new_doc(
        "RN Medical Evacuation"
    )

    doc.posko = posko
    doc.medical_case = (
        medical_case
    )
    doc.provider_name = (
        provider_name
    )
    doc.transport_reference = (
        transport_reference
    )
    doc.vehicle_contact = (
        vehicle_contact
    )
    doc.destination_facility = (
        destination_facility
    )
    doc.evacuation_status = (
        "requested"
    )
    doc.notes = notes

    doc.insert(
        ignore_permissions=True
    )

    return {
        "medical_evacuation": doc.name,
        "evacuation_status": (
            doc.evacuation_status
        ),
    }


@frappe.whitelist()
def update_evacuation_status(
    evacuation,
    new_status,
):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Medical Evacuation",
        evacuation,
    )

    _assert_medical_access(
        actor,
        doc.posko,
    )

    current = doc.evacuation_status

    if new_status not in (
        EVAC_TRANSITIONS.get(
            current,
            set(),
        )
    ):
        frappe.throw(
            f"Transisi evakuasi tidak valid: "
            f"{current} -> {new_status}"
        )

    now = now_datetime()

    doc.evacuation_status = (
        new_status
    )

    if new_status == "patient_on_board":
        doc.departed_at = now


    if new_status == "arrived_hospital":
        doc.arrived_at = now

    if new_status == "handover_complete":
        doc.handover_at = now


    doc.save(
        ignore_permissions=True
    )

    return {
        "medical_evacuation": doc.name,
        "previous_status": current,
        "evacuation_status": (
            doc.evacuation_status
        ),
    }


@frappe.whitelist()
def add_evidence(
    reference_doctype,
    reference_name,
    file_url,
    evidence_type="other",
    caption=None,
):
    allowed = {
        "RN Medical Case",
        "RN Medical Evacuation",
    }

    if reference_doctype not in allowed:
        frappe.throw(
            "Jenis referensi evidence tidak valid"
        )

    if not (
        file_url or ""
    ).startswith(
        "/private/files/"
    ):
        frappe.throw(
            "Evidence medis wajib disimpan private"
        )

    actor = rn_actor()

    posko = frappe.db.get_value(
        reference_doctype,
        reference_name,
        "posko",
    )

    if not posko:
        frappe.throw(
            "Referensi medis tidak ditemukan"
        )

    _assert_medical_access(
        actor,
        posko,
    )

    doc = frappe.new_doc(
        "RN Medical Evidence"
    )

    doc.reference_doctype = (
        reference_doctype
    )
    doc.reference_name = (
        reference_name
    )
    doc.posko = posko
    doc.file_url = file_url
    doc.evidence_type = (
        evidence_type
    )
    doc.caption = caption
    doc.verification_status = "pending"

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


@frappe.whitelist()
def control_centre_medical():
    actor = rn_actor()

    role = getattr(
        actor,
        "role",
        None,
    )

    if (
        not is_system_manager()
        and role not in OPERATOR_ROLES
    ):
        frappe.throw(
            "Akses Control Centre medis ditolak",
            frappe.PermissionError,
        )

    allowed = _accessible_poskos(
        actor
    )

    cases = frappe.get_all(
        "RN Medical Case",
        filters={
            "posko": ["in", allowed]
        },
        fields=[
            "posko",
            "triage_status",
            "case_status",
            "severity",
        ],
        limit_page_length=5000,
    )

    triage = defaultdict(int)
    status = defaultdict(int)
    posko_counts = defaultdict(int)

    for row in cases:
        triage[
            row.triage_status
        ] += 1

        status[
            row.case_status
        ] += 1

        posko_counts[
            row.posko
        ] += 1

    return {
        "case_count": len(cases),
        "triage": dict(triage),
        "case_status": dict(status),
        "posko_case_count": (
            dict(posko_counts)
        ),
        "privacy": (
            "Aggregate only; patient code "
            "and complaint are not exposed."
        ),
    }


# --- Patient card: history timeline (status changes + notes) ---------------

def _case_author():
    user = frappe.session.user
    return (
        frappe.db.get_value("User", user, "full_name")
        or user
    )


def _log_case_update(
    case_doc,
    update_type,
    note=None,
    previous_status=None,
    new_status=None,
):
    """Append one row to a patient's history timeline. Best-effort: a logging
    failure must never break the clinical action it records."""
    try:
        actor = rn_actor()
    except Exception:
        actor = None

    try:
        frappe.get_doc({
            "doctype": "RN Medical Case Update",
            "medical_case": case_doc.name,
            "posko": case_doc.posko,
            "update_type": update_type,
            "previous_status": previous_status,
            "new_status": new_status,
            "note": note,
            "author_name": _case_author(),
            "created_by_user": getattr(actor, "name", None),
            "observed_at": now_datetime(),
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "RN medical case update log failed",
        )


@frappe.whitelist()
def add_case_note(medical_case, note):
    note = (note or "").strip()

    if not note:
        frappe.throw("Catatan kosong")

    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Medical Case",
        medical_case,
    )

    _assert_medical_access(actor, doc.posko)
    _log_case_update(doc, "note", note=note)

    return {"medical_case": doc.name}


@frappe.whitelist()
def case_card(medical_case):
    actor = rn_actor()

    doc = frappe.get_doc(
        "RN Medical Case",
        medical_case,
    )

    _assert_medical_access(actor, doc.posko)

    history = frappe.get_all(
        "RN Medical Case Update",
        filters={"medical_case": doc.name},
        fields=[
            "update_type",
            "previous_status",
            "new_status",
            "note",
            "author_name",
            "observed_at",
        ],
        order_by="observed_at desc",
        limit_page_length=200,
    )

    return {
        "case": {
            "name": doc.name,
            "patient_code": doc.patient_code,
            "patient_name": doc.patient_name,
            "complaint": doc.complaint,
            "severity": doc.severity,
            "triage_status": doc.triage_status,
            "case_status": doc.case_status,
            "treatment_notes": doc.treatment_notes,
            "age_group": doc.age_group,
            "gender": doc.gender,
            "observed_at": (
                str(doc.observed_at)
                if doc.observed_at
                else None
            ),
        },
        "history": history,
    }


# --- Posko medical needs: kategori kebutuhan logistik bencana ----------------

# Keep in sync with RN Logistic Need.need_kind Select options and the label map
# in assets/js/posko-medis-detail.js (NEED_KIND_LABEL).
NEED_KINDS = {
    "obat": "Obat & Bahan Medis",
    "alat": "Alat & Peralatan Medis",
    "logistik": "Logistik Umum",
    "makanan_air": "Makanan & Air",
    "sanitasi": "Sanitasi & Higiene",
    "lainnya": "Lainnya",
}


@frappe.whitelist()
def posko_needs(posko=None):
    posko = resolve_posko(posko)
    actor = rn_actor()
    _assert_medical_access(actor, posko)

    rows = frappe.get_all(
        "RN Logistic Need",
        filters={"posko": posko},
        fields=[
            "name",
            "item_name",
            "quantity",
            "unit",
            "urgency",
            "need_status",
            "need_kind",
        ],
        order_by="observed_at desc",
        limit_page_length=500,
    )

    for r in rows:
        if r.get("need_kind") not in NEED_KINDS:
            r["need_kind"] = "obat"

    # Flat list + the category order/labels so the UI can group generically.
    return {
        "needs": rows,
        "kinds": [
            {"key": k, "label": v} for k, v in NEED_KINDS.items()
        ],
    }


@frappe.whitelist()
def add_posko_need(
    posko,
    item_name,
    quantity,
    unit,
    need_kind="obat",
    urgency="normal",
):
    posko = resolve_posko(posko)
    actor = rn_actor()
    _assert_medical_access(actor, posko)

    item_name = (item_name or "").strip()
    if not item_name:
        frappe.throw("Nama item kosong")

    kind = need_kind if need_kind in NEED_KINDS else "obat"
    event = frappe.db.get_value("RN Posko", posko, "disaster_event")

    doc = frappe.get_doc({
        "doctype": "RN Logistic Need",
        "posko": posko,
        "disaster_event": event,
        "title": item_name,
        "item_name": item_name,
        "quantity": flt(quantity),
        "unit": (unit or "").strip(),
        "urgency": urgency,
        "need_kind": kind,
        "need_status": "open",
        "observed_at": now_datetime(),
        "created_by_user": getattr(actor, "name", None),
        "verification_status": "self_reported",
    }).insert(ignore_permissions=True)

    return {"name": doc.name, "need_kind": kind}


# --- Penerimaan bantuan: masuk ke stok medis (RN Stock Observation) ----------

@frappe.whitelist()
def record_aid_received(
    posko,
    item_name,
    quantity,
    unit,
    donor=None,
    notes=None,
):
    """Catat bantuan yang diterima posko medis. Bantuan langsung menambah
    RN Stock Observation sehingga tampil di Medical Stock. Pemberi/donor dan
    catatan disimpan di field notes (tidak ada doctype terpisah)."""
    posko = resolve_posko(posko)
    actor = rn_actor()
    _assert_medical_access(actor, posko)

    item_name = (item_name or "").strip()
    if not item_name:
        frappe.throw("Nama item bantuan kosong")

    qty = flt(quantity)
    if qty <= 0:
        frappe.throw("Jumlah bantuan harus lebih dari 0")

    donor = (donor or "").strip()
    extra = (notes or "").strip()
    note_parts = ["Penerimaan bantuan"]
    if donor:
        note_parts.append(f"dari {donor}")
    full_note = " ".join(note_parts)
    if extra:
        full_note = f"{full_note}. {extra}"

    event = frappe.db.get_value("RN Posko", posko, "disaster_event")

    doc = frappe.new_doc("RN Stock Observation")
    doc.title = item_name
    doc.posko = posko
    doc.disaster_event = event
    doc.item_name = item_name
    doc.raw_item_text = item_name
    doc.quantity = qty
    doc.unit = (unit or "").strip()
    doc.quantity_mode = "exact"
    doc.stock_state = "available"
    doc.notes = full_note
    doc.observed_at = now_datetime()
    doc.source_updated_at = doc.observed_at
    doc.created_by_user = getattr(actor, "name", None)
    doc.verification_status = "self_reported"
    doc.insert(ignore_permissions=True)

    return {
        "stock_observation": doc.name,
        "item_name": doc.item_name,
        "quantity": doc.quantity,
        "unit": doc.unit,
    }
