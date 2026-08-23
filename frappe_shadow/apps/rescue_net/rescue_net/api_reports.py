import frappe
from frappe.utils import cint, flt


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

    doc = frappe.new_doc("RN Community Report")
    doc.title = title
    doc.description = description
    doc.report_type = report_type
    doc.priority = priority
    doc.affected_people_count = cint(affected_people_count or 0)
    doc.urgent_needs = urgent_needs
    doc.location_text = location_text

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

    return {
        "name": doc.name,
        "status": doc.status,
        "reporter_user": doc.reporter_user,
        "admin_area_id": doc.admin_area_id,
        "has_coordinates": doc.has_coordinates,
    }
