import math

import frappe
from frappe.utils import cint, flt


# ============================================================
# Perkiraan Kebutuhan Alat/Logistik dari Laporan Masyarakat — owner ask:
# "jalan rusak 200 m butuh buldoser/excavator", "100 kehilangan rumah
# butuh makanan/pakaian/shelter", optional fields, feeds a heuristic
# estimate so posko can adjust prep. Deliberately the SAME kind of
# simple, honestly-labeled divisor heuristic as
# api_resource_tools._EQUIP_PREDICTION_RULES/_predict_equipment (Alat
# Kerja's "Prediksi Kebutuhan Alat") — a real math estimate, not a
# fabricated "AI" black box, and not a real LLM call for something
# this deterministic.
# ============================================================

# report_type -> [(item, label, divisor, basis)]; qty = ceil(scale/divisor).
_ACCESS_DAMAGE_TYPES = {"blocked_access", "new_hazard"}
_ACCESS_EQUIPMENT_RULES = [
    ("excavator", "Ekskavator", 150, "1 ekskavator per ~150 m jalan/akses rusak atau tertutup"),
    ("buldoser", "Buldoser", 200, "1 buldoser per ~200 m jalan/akses rusak atau tertutup"),
]

# report_type -> per-affected-person logistics; "per_day": consumable
# (rate, not a total — duration is unknown), else one-time durable item.
_DISPLACEMENT_TYPES = {"shelter_need", "affected_need_help", "location_needs_help"}
_DISPLACEMENT_LOGISTICS_RULES = [
    ("beras", "Beras", 0.4, "kg", True, "~0.4 kg beras per orang per hari (standar bantuan pangan darurat)"),
    ("air_bersih", "Air Bersih", 3.0, "liter", True, "~3 liter air bersih per orang per hari"),
    ("selimut", "Selimut", 1.0, "pcs", False, "1 selimut per orang terdampak"),
    ("pakaian_layak", "Pakaian Layak Pakai", 1.0, "set", False, "1 set pakaian per orang terdampak"),
    ("tenda_keluarga", "Tenda Keluarga", 0.2, "unit", False, "1 tenda keluarga per ~5 orang terdampak"),
]


def predict_report_needs(report_type, damage_scale_value=None, affected_people_count=0):
    """Heuristic equipment/logistics estimate from a citizen report — same
    honest-heuristic spirit as api_resource_tools._predict_equipment.
    Returns [] when there's nothing to predict from (no scale/people given,
    or a report_type this doesn't apply to) — never fabricates a number."""
    report_type = (report_type or "").strip()
    scale = flt(damage_scale_value)
    people = cint(affected_people_count)

    out = []

    if report_type in _ACCESS_DAMAGE_TYPES and scale > 0:
        for key, label, divisor, basis in _ACCESS_EQUIPMENT_RULES:
            qty = max(1, math.ceil(scale / divisor))
            out.append({
                "category": key, "label": label, "predicted_qty": qty,
                "unit": "unit", "basis": basis,
            })

    if report_type in _DISPLACEMENT_TYPES and people > 0:
        for key, label, rate, unit, per_day, basis in _DISPLACEMENT_LOGISTICS_RULES:
            qty = math.ceil(rate * people)
            if qty <= 0:
                continue
            out.append({
                "category": key, "label": label, "predicted_qty": qty,
                "unit": unit, "basis": basis, "per_day": bool(per_day),
            })

    return out


def _area(code):
    if not code:
        return None
    return frappe.db.get_value(
        "RN Admin Area",
        {"code": code, "enabled": 1},
        ["code", "area_name", "level", "parent_code"],
        as_dict=True,
    )


@frappe.whitelist()
def submit_community_report(
    title,
    description,
    report_type=None,
    priority=None,
    affected_people_count=0,
    urgent_needs=None,
    location_text=None,
    latitude=None,
    longitude=None,
    province_code=None,
    city_code=None,
    district_code=None,
    village_code=None,
    consent_to_contact=0,
    location_input_method=None,
    create_need=0,
    damage_scale_value=None,
    damage_scale_unit=None,
    disaster_event=None,
):
    if frappe.session.user == "Guest":
        frappe.throw("Login diperlukan untuk mengirim laporan")

    province = _area(province_code)
    city = _area(city_code)
    district = _area(district_code)
    village = _area(village_code)

    deepest = village or district or city or province

    lat = None if latitude in (None, "") else flt(latitude)
    lng = None if longitude in (None, "") else flt(longitude)
    has_coordinates = lat is not None and lng is not None

    from rescue_net.reference_resolver import resolve_disaster_event

    doc = frappe.new_doc("RN Community Report")
    doc.title = title
    doc.description = description
    doc.disaster_event = resolve_disaster_event(disaster_event) if disaster_event else None
    doc.report_type = report_type
    doc.priority = priority
    doc.affected_people_count = cint(affected_people_count or 0)
    doc.urgent_needs = urgent_needs
    doc.location_text = location_text
    doc.damage_scale_value = flt(damage_scale_value) if damage_scale_value not in (None, "") else None
    doc.damage_scale_unit = damage_scale_unit or None

    doc.has_coordinates = 1 if has_coordinates else 0
    doc.latitude = lat
    doc.longitude = lng
    doc.location_input_method = location_input_method
    doc.location_source = "frappe-web"
    doc.location_status = "provided" if has_coordinates else "not_provided"

    if deepest:
        doc.admin_area_id = deepest.code
        doc.admin_level = deepest.level
        doc.area_level = deepest.level

    doc.province_name = province.area_name if province else None
    doc.city_name = city.area_name if city else None
    doc.district_name = district.area_name if district else None
    doc.village_name = village.area_name if village else None

    doc.consent_to_contact = cint(consent_to_contact or 0)
    doc.status = "submitted"

    doc.insert(ignore_permissions=True)

    community_need = None

    if cint(create_need):
        need_text = (urgent_needs or "").strip()

        if not need_text:
            frappe.throw(
                "Kebutuhan Mendesak wajib diisi bila dijadikan kebutuhan penanganan"
            )

        need = frappe.new_doc("RN Community Need")
        need.title = f"Kebutuhan - {doc.title}"
        need.source_report = doc.name
        need.requester_user = doc.reporter_user
        need.disaster_event = doc.disaster_event

        if doc.reporter_user:
            need.community_owner = frappe.db.get_value(
                "RN User Account",
                doc.reporter_user,
                "organization",
            )

            if not need.community_owner:
                memberships = frappe.get_all(
                    "RN Organization Membership",
                    filters={
                        "user_account": doc.reporter_user,
                        "status": "approved",
                    },
                    fields=["organization"],
                    order_by="approved_at desc, creation asc",
                    limit_page_length=1,
                )
                if memberships:
                    need.community_owner = memberships[0].organization

            if not need.community_owner:
                memberships = frappe.get_all(
                    "RN Organization Membership",
                    filters={
                        "user_account": doc.reporter_user,
                        "status": "approved",
                    },
                    fields=["organization"],
                    order_by="approved_at desc, creation asc",
                    limit_page_length=1,
                )
                if memberships:
                    need.community_owner = memberships[0].organization

        need.need_type = doc.report_type
        need.description = need_text

        if priority in ("low", "medium", "high", "critical"):
            need.urgency = priority

        need.handling_mode = "community"
        need.takeover_status = "none"
        need.status = "open"

        need.verification_status = "unverified"
        need.verification_status = "unverified"
        need.insert(ignore_permissions=True)
        community_need = need.name

        frappe.db.set_value(
            "RN Community Report",
            doc.name,
            {
                "converted_object_type": "RN Community Need",
                "converted_object_id": need.name,
            },
            update_modified=False,
        )

        frappe.db.set_value(
            "RN Community Report",
            doc.name,
            {
                "converted_object_type": "RN Community Need",
                "converted_object_id": need.name,
            },
            update_modified=False,
        )

    predicted_needs = predict_report_needs(
        doc.report_type, doc.damage_scale_value, doc.affected_people_count,
    )

    return {
        "name": doc.name,
        "status": doc.status,
        "reporter_user": doc.reporter_user,
        "admin_area_id": doc.admin_area_id,
        "has_coordinates": doc.has_coordinates,
        "community_need": community_need,
        "predicted_needs": predicted_needs,
        "predicted_needs_note": (
            "Perkiraan heuristik dari skala kerusakan/jumlah terdampak yang dilaporkan — "
            "bukan perhitungan teknis, untuk membantu posko menyesuaikan persiapan awal."
        ) if predicted_needs else None,
    }
