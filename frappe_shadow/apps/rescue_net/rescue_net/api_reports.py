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
    create_need=0,
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

    return {
        "name": doc.name,
        "status": doc.status,
        "reporter_user": doc.reporter_user,
        "admin_area_id": doc.admin_area_id,
        "has_coordinates": doc.has_coordinates,
        "community_need": community_need,
    }
