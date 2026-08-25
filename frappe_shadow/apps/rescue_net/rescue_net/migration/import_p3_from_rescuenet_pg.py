import json
from decimal import Decimal

import frappe

from rescue_net.migration.import_from_rescuenet_pg import get_rescuenet_pg_dsn


P3_TABLES = {
    "RN Stock Observation": ["stock_movements"],
    "RN Medical Case": ["medical_cases"],
    "RN Medical Supply Use": ["medical_supply_uses"],
    "RN Shelter Occupancy": ["shelter_occupancies"],
    "RN Shelter Need": ["shelter_needs"],
    "RN Volunteer Profile": ["volunteer_profiles"],
    "RN Volunteer Assignment": ["volunteer_assignments"],
    "RN Missing Person Report": ["missing_person_reports"],
    "RN Found Person Report": ["found_person_reports"],
    "RN Search Found Match": ["search_found_matches"],
    "RN Resource Profile": ["resource_profiles"],
    "RN Resource Request": ["resource_requests"],
    "RN Work Tool Request": ["work_tool_requests"],
    "RN Kitchen Production": ["kitchen_meal_productions"],
    "RN Donor Program": ["donor_programs"],
    "RN Donor Program Update": ["donor_program_updates"],
    "RN Recovery Project": ["recovery_projects"],
    "RN Recovery Project Update": ["recovery_project_updates"],
}


SOURCE_COUNTS_SQL_P3 = {
    table: f"select count(*) from {table}"
    for tables in P3_TABLES.values()
    for table in tables
}


_P3_PENDING_LINKS = set()
_P3_PENDING_PREFIX = "__P3_PENDING__:"


P3_DEFERRED_TABLES = {}


def _pending_link_token(doctype, source_id):
    return (
        f"{_P3_PENDING_PREFIX}"
        f"{doctype}:{source_id}"
    )


def _is_pending_link(value):
    return (
        isinstance(value, str)
        and value.startswith(_P3_PENDING_PREFIX)
    )


def _value(row, key, default=None):
    value = row.get(key)
    return default if value is None else value


def _json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _legacy_link(doctype, legacy_id):
    if not legacy_id:
        return None

    source_id = str(legacy_id)

    existing = frappe.db.get_value(
        doctype,
        {"legacy_id": source_id},
        "name",
    )

    if existing:
        return existing

    if (doctype, source_id) in _P3_PENDING_LINKS:
        return _pending_link_token(
            doctype,
            source_id,
        )

    return None


def _sync_link(doctype, sync_event_id):
    if not sync_event_id:
        return None
    return frappe.db.get_value(
        doctype,
        {"sync_event_id": str(sync_event_id)},
        "name",
    )


def _common(row):
    return {
        "legacy_id": str(row["id"]) if row.get("id") is not None else None,
        "verification_status": row.get("verification_status"),
        "observed_at": row.get("created_at"),
    }


def _map_stock_movement(row):
    data = _common(row)

    source_id = str(row["id"])

    notes = row.get("notes") or ""

    context = [
        f"movement_type={row.get('movement_type')}",
        f"movement_direction={row.get('movement_direction')}",
    ]

    if row.get("source_type") or row.get("source_id"):
        context.append(
            f"source={row.get('source_type')}:{row.get('source_id')}"
        )

    if row.get("destination_type") or row.get("destination_id"):
        context.append(
            "destination="
            f"{row.get('destination_type')}:{row.get('destination_id')}"
        )

    marker = f"[legacy_stock_movement:{source_id}]"

    extra = "; ".join(context)

    notes = "\n".join(
        x for x in (notes, extra, marker)
        if x
    )

    data.update({
        "title": (
            f"[legacy:{source_id}] "
            f"{row.get('item_name') or 'Stock movement'}"
        ),
        "disaster_event": _legacy_link(
            "RN Disaster Event",
            row.get("disaster_event_id"),
        ),
        "posko": _legacy_link(
            "RN Posko",
            row.get("posko_id"),
        ),
        "item_name": row.get("item_name"),
        "raw_item_text": row.get("item_name"),
        "quantity": _decimal(row.get("quantity")),
        "quantity_mode": "exact",
        "unit": row.get("unit"),
        "stock_state": "available",
        "observed_at": row.get("created_at"),
        "source_updated_at": row.get("updated_at"),
        "verification_status": row.get("verification_status"),
        "notes": notes,
    })

    return data


def _map_medical_case(row):
    data = _common(row)
    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "posko": _legacy_link("RN Posko", row.get("posko_id")),
        "patient_code": row.get("patient_code"),
        "age_group": row.get("age_group"),
        "gender": row.get("gender"),
        "complaint": row.get("complaint"),
        "severity": {
            "minor": "mild",
        }.get(
            row.get("severity"),
            row.get("severity"),
        ),
        "triage_status": row.get("triage_status"),
        "treatment_notes": row.get("treatment_notes"),
        "referral_needed": 1 if row.get("referral_needed") else 0,
        "referral_destination": row.get("referral_destination"),
        "case_status": {
            "treated": "stabilized",
        }.get(
            row.get("status"),
            row.get("status"),
        ),
    })
    return data


def _map_medical_supply_use(row):
    data = _common(row)
    data.update({
        "posko": _legacy_link("RN Posko", row.get("posko_id")),
        "medical_case": _legacy_link(
            "RN Medical Case", row.get("medical_case_id")
        ),
        "item_name": row.get("item_name"),
        "quantity": _decimal(row.get("quantity")),
        "unit": row.get("unit"),
        "notes": row.get("notes"),
        "used_at": row.get("created_at"),
    })
    return data


def _map_shelter_occupancy(row):
    data = _common(row)
    data.update({
        "legacy_source": "shelter_occupancies",
        "migration_status": "imported",
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "posko": _legacy_link("RN Posko", row.get("posko_id")),
        "shelter_name": row.get("shelter_name"),
        "capacity_total": row.get("capacity_total"),
        "current_occupancy": row.get("current_occupancy"),
        "families_count": row.get("families_count"),
        "children_count": row.get("children_count"),
        "elderly_count": row.get("elderly_count"),
        "disability_count": row.get("disabled_count"),
        "sanitation_status": row.get("sanitation_status"),
        "water_status": row.get("water_status"),
        "electricity_status": row.get("electricity_status"),
        "safety_status": row.get("safety_status"),
        "notes": row.get("notes"),
        "occupancy_status": row.get("status"),
    })
    return data


def _map_shelter_need(row):
    data = _common(row)

    notes = row.get("notes") or ""

    legacy_needed_before = row.get("needed_before")

    if legacy_needed_before:
        marker = (
            "[legacy_needed_before:"
            f"{legacy_needed_before}]"
        )

        if marker not in notes:
            notes = (notes + "\n" + marker).strip()

    data.update({
        "posko": _legacy_link(
            "RN Posko",
            row.get("posko_id"),
        ),
        "item_name": row.get("item_name"),
        "quantity_mode": "exact",
        "quantity_needed": _decimal(
            row.get("quantity_needed")
        ),
        "unit": row.get("unit"),
        "priority": row.get("priority"),

        # Legacy source contains relative human text
        # such as "Besok pagi". Do not fabricate a
        # concrete datetime.
        "needed_before": None,

        "need_status": row.get("status"),
        "notes": notes,
    })

    return data


def _map_volunteer_profile(row):
    data = _common(row)
    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "volunteer_name": row.get("volunteer_name"),
        "contact": row.get("contact"),
        "main_skill": row.get("skill_tags") or "unspecified",
        "skill_tags": row.get("skill_tags"),
        "availability_status": row.get("availability_status"),
        "current_location": row.get("current_location"),
        "assigned_posko": _legacy_link(
            "RN Posko", row.get("assigned_posko_id")
        ),
        "notes": row.get("notes"),
        "verification_status": row.get("verification_status"),
        "source_updated_at": row.get("updated_at"),
    })
    return data


def _map_volunteer_assignment(row):
    data = _common(row)

    assigned_to_type = (
        str(row.get("assigned_to_type") or "")
        .strip()
        .lower()
    )

    allowed_types = {
        "posko",
        "medical",
        "shelter",
        "logistics",
        "distribution",
        "field_assessment",
        "search_rescue",
    }

    assignment_type = (
        assigned_to_type
        if assigned_to_type in allowed_types
        else "other"
    )

    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event",
            row.get("disaster_event_id"),
        ),
        "volunteer": _legacy_link(
            "RN Volunteer Profile",
            row.get("volunteer_id"),
        ),
        "posko": _legacy_link(
            "RN Posko",
            row.get("assigned_to_id"),
        ),
        "assignment_type": assignment_type,
        "task_title": row.get("task_name"),
        "target_reference": row.get("assigned_to_id"),
        "priority": row.get("priority"),
        "assignment_status": row.get("status"),
        "assignment_notes": row.get("task_description"),
    })

    return data


def _map_missing_person(row):
    data = _common(row)
    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "posko": _legacy_link("RN Posko", row.get("source_posko_id")),
        "person_code": row.get("person_code"),
        "person_name": row.get("person_name"),
        "last_seen_location": row.get("last_seen_location"),

        # Source may contain "Kemarin sore".
        # Full original row is retained in legacy_payload.
        "last_seen_time": None,

        "description": row.get("description"),
        "clothing_description": row.get("clothing_description"),
        "report_status": row.get("status"),
        "legacy_payload": _json(dict(row)),
    })
    return data


def _map_found_person(row):
    data = _common(row)
    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "posko": _legacy_link("RN Posko", row.get("source_posko_id")),
        "person_code": row.get("person_code"),
        "person_name": row.get("person_name"),
        "found_location": row.get("found_location"),

        # Source may contain "Hari ini pagi".
        # Full original row is retained in legacy_payload.
        "found_time": None,

        "description": row.get("description"),
        "clothing_description": row.get("clothing_description"),
        "report_status": row.get("status"),
        "legacy_payload": _json(dict(row)),
    })
    return data


def _map_search_found_match(row):
    data = _common(row)
    data.update({
        "missing_report": _legacy_link(
            "RN Missing Person Report", row.get("missing_report_id")
        ),
        "found_report": _legacy_link(
            "RN Found Person Report", row.get("found_report_id")
        ),
        "match_status": {
            "candidate": "proposed",
        }.get(
            row.get("status"),
            row.get("status"),
        ),
        "match_basis": row.get("match_reason"),
        "review_notes": row.get("reunion_notes"),
    })
    return data


def _map_resource_profile(row):
    data = _common(row)
    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "owner_type": row.get("owner_type"),
        "owner_id": row.get("owner_id"),
        "resource_name": row.get("resource_name"),
        "resource_type": row.get("resource_type"),
        "category": row.get("category"),
        "quantity": _decimal(row.get("quantity")),
        "unit": row.get("unit"),
        "capacity_description": row.get("capacity_description"),
        "availability_status": row.get("availability_status"),
        "current_location": row.get("current_location"),
        "coverage_area": row.get("coverage_area"),
        "pic_name": row.get("pic_name"),
        "pic_phone": row.get("pic_phone"),
        "notes": row.get("notes"),
    })
    return data


def _map_legacy_resource(row):
    data = _common(row)

    capacity = row.get("capacity_json")

    if isinstance(capacity, dict):
        capacity_text = ", ".join(
            f"{key}={value}"
            for key, value in sorted(
                capacity.items()
            )
        )
    elif capacity:
        capacity_text = str(capacity)
    else:
        capacity_text = None

    description = row.get("description")

    capacity_description = "\n".join(
        x for x in (
            description,
            capacity_text,
        )
        if x
    )

    notes_parts = []

    for key in (
        "visibility_scope",
        "access_policy",
        "trust_level",
    ):
        value = row.get(key)

        if value not in (None, ""):
            notes_parts.append(
                f"{key}={value}"
            )

    notes_parts.append(
        f"[legacy_resource:{row['id']}]"
    )

    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event",
            row.get("disaster_event_id"),
        ),
        "owner_type": (
            row.get("owner_type")
            or "external"
        ),
        "owner_id": row.get("owner_id"),
        "resource_name": (
            row.get("name")
            or str(row["id"])
        ),
        "resource_type": (
            row.get("resource_type")
            or "other"
        ),
        "category": (
            capacity.get("mode")
            if isinstance(capacity, dict)
            else None
        ),
        "quantity": 1,
        "unit": "resource",
        "capacity_description": (
            capacity_description
        ),
        "availability_status": (
            row.get("status")
        ),
        "current_location": (
            row.get("location")
        ),
        "verification_status": (
            row.get("verification_status")
        ),
        "notes": "; ".join(notes_parts),
    })

    return data


def _map_resource_request(row):
    return {
        "sync_event_id": str(row["id"]),
        "source_object_id": str(row["id"]),
        "resource_profile": _legacy_link(
            "RN Resource Profile", row.get("resource_id")
        ),
        "requested_by_type": row.get("requested_by_type"),
        "requested_by_id": row.get("requested_by_id"),
        "request_reason": row.get("request_reason"),
        "related_need_id": row.get("related_need_id"),
        "related_distribution_flow_id": row.get(
            "related_distribution_flow_id"
        ),
        "requested_quantity": _decimal(row.get("requested_quantity")),
        "requested_time": row.get("requested_time"),
        "request_status": row.get("status"),
    }


def _map_work_tool_request(row):
    data = _common(row)
    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event", row.get("disaster_event_id")
        ),
        "requested_by_type": row.get("requested_by_type"),
        "requested_by_id": row.get("requested_by_id"),
        "tool_name": row.get("tool_name"),
        "tool_type": row.get("tool_type"),
        "quantity": _decimal(row.get("quantity")),
        "unit": row.get("unit"),
        "location": row.get("location"),
        "needed_for": row.get("needed_for"),
        "priority": row.get("priority"),
        "required_operator_skill": row.get("required_operator_skill"),
        "request_status": row.get("status"),
        "notes": row.get("notes"),
    })
    return data


def _map_kitchen_production(row):
    data = _common(row)

    notes = row.get("notes") or ""

    legacy_production_time = row.get(
        "production_time"
    )

    if legacy_production_time:
        marker = (
            "[legacy_production_time:"
            f"{legacy_production_time}]"
        )

        if marker not in notes:
            notes = (notes + "\n" + marker).strip()

    data.update({
        "disaster_event": _legacy_link(
            "RN Disaster Event",
            row.get("disaster_event_id"),
        ),
        "posko": _legacy_link(
            "RN Posko",
            row.get("posko_id"),
        ),
        "meal_name": row.get("meal_name"),
        "portions": row.get("portions"),

        # Legacy source contains relative human text,
        # e.g. "Malam ini" / "Hari ini sore".
        "production_time": None,

        "target_distribution_location": row.get(
            "target_distribution_location"
        ),
        "production_status": row.get("status"),
        "notes": notes,
        "legacy_payload": _json({
            "ingredients_json": row.get(
                "ingredients_json"
            ),
            "production_time": (
                legacy_production_time
            ),
        }),
    })

    return data


def _map_donor_program(row):
    source_id = str(row["id"])

    marker = f"[legacy_id:{source_id}]"

    notes = row.get("notes") or ""

    if marker not in notes:
        notes = (notes + "\n" + marker).strip()

    return {
        "_source_id": source_id,
        "disaster_event": str(
            row.get("disaster_event_id") or ""
        ),
        "program_name": row.get("program_name"),
        "program_type": row.get("program_type"),
        "owner_type": row.get("owner_type"),
        "owner_id": row.get("owner_id"),
        "target_description": row.get("target_description"),
        "target_amount": _decimal(row.get("target_amount")),
        "target_unit": row.get("target_unit"),
        "current_amount": _decimal(row.get("current_amount")),
        "status": row.get("status"),
        "location": row.get("location"),
        "contact_person": row.get("contact_person"),
        "contact_phone": row.get("contact_phone"),
        "notes": notes,
        "observed_at": row.get("created_at"),
    }


def _map_donor_program_update(row):
    source_id = str(row["id"])

    marker = f"[legacy_id:{source_id}]"

    notes = (
        row.get("update_notes")
        or row.get("description")
        or ""
    )

    if marker not in notes:
        notes = (notes + "\n" + marker).strip()

    return {
        "_source_id": source_id,
        "program": _find_program(row.get("program_id")),
        "disaster_event": str(
            row.get("disaster_event_id") or ""
        ),
        "update_type": row.get("update_type") or "progress",
        "progress_percent": _decimal(
            row.get("progress_percent")
        ),
        "amount_spent": _decimal(
            row.get("amount_spent")
            if row.get("amount_spent") is not None
            else row.get("amount_used")
        ),
        "amount_unit": row.get("amount_unit"),
        "update_title": row.get("update_title"),
        "update_notes": notes,
        "evidence_file_id": row.get("evidence_file_id"),
        "officer_in_charge_name": (
            row.get("officer_in_charge_name")
        ),
        "officer_in_charge_phone": (
            row.get("officer_in_charge_phone")
        ),
        "public_visibility": row.get("public_visibility"),
        "observed_at": row.get("created_at"),
    }


def _find_program(source_id):
    if not source_id:
        return None

    source_id = str(source_id)

    marker = f"[legacy_id:{source_id}]"

    existing = frappe.db.get_value(
        "RN Donor Program",
        {"notes": ["like", f"%{marker}%"]},
        "name",
    )

    if existing:
        return existing

    if (
        "RN Donor Program",
        source_id,
    ) in _P3_PENDING_LINKS:
        return _pending_link_token(
            "RN Donor Program",
            source_id,
        )

    return None


def _map_recovery_project(row):
    notes = row.get("notes") or ""
    marker = f"[legacy_id:{row['id']}]"
    if marker not in notes:
        notes = (notes + "\n" + marker).strip()

    return {
        "_source_id": str(row["id"]),
        "disaster_event": str(row.get("disaster_event_id") or ""),
        "project_name": row.get("project_name"),
        "project_type": row.get("project_type"),
        "owner_type": row.get("owner_type"),
        "owner_id": row.get("owner_id"),
        "target_description": row.get("target_description"),
        "location": row.get("location"),
        "priority": row.get("priority"),
        "target_amount": _decimal(row.get("target_amount")),
        "current_amount": _decimal(row.get("current_amount")),
        "progress_percent": _decimal(row.get("progress_percent")),
        "status": row.get("status"),
        "start_date": row.get("start_date"),
        "target_finish_date": row.get("target_finish_date"),
        "pic_name": row.get("pic_name"),
        "pic_phone": row.get("pic_phone"),
        "notes": notes,
        "observed_at": row.get("created_at"),
        "version": row.get("version"),
        "is_deleted": 1 if row.get("deleted_at") else 0,
        "deleted_at": row.get("deleted_at"),
    }


def _find_recovery_project(source_id):
    if not source_id:
        return None

    source_id = str(source_id)

    marker = f"[legacy_id:{source_id}]"

    existing = frappe.db.get_value(
        "RN Recovery Project",
        {"notes": ["like", f"%{marker}%"]},
        "name",
    )

    if existing:
        return existing

    if (
        "RN Recovery Project",
        source_id,
    ) in _P3_PENDING_LINKS:
        return _pending_link_token(
            "RN Recovery Project",
            source_id,
        )

    return None


def _map_recovery_project_update(row):
    source_id = str(row["id"])

    marker = f"[legacy_id:{source_id}]"

    notes = row.get("update_notes") or ""

    if marker not in notes:
        notes = (notes + "\n" + marker).strip()

    return {
        "_source_id": source_id,
        "project": _find_recovery_project(row.get("project_id")),
        "disaster_event": str(row.get("disaster_event_id") or ""),
        "update_type": row.get("update_type"),
        "progress_percent": _decimal(row.get("progress_percent")),
        "amount_spent": _decimal(row.get("amount_spent")),
        "update_title": row.get("update_title"),
        "update_notes": notes,
        "evidence_file_id": row.get("evidence_file_id"),
        "verification_status": row.get("verification_status"),
        "observed_at": row.get("created_at"),
        "is_deleted": 1 if row.get("deleted_at") else 0,
        "deleted_at": row.get("deleted_at"),
    }


MAPPINGS = [
    ("stock_movements", "RN Stock Observation", _map_stock_movement),
    ("medical_cases", "RN Medical Case", _map_medical_case),
    ("medical_supply_uses", "RN Medical Supply Use", _map_medical_supply_use),
    ("shelter_occupancies", "RN Shelter Occupancy", _map_shelter_occupancy),
    ("shelter_needs", "RN Shelter Need", _map_shelter_need),
    ("volunteer_profiles", "RN Volunteer Profile", _map_volunteer_profile),
    (
        "volunteer_assignments",
        "RN Volunteer Assignment",
        _map_volunteer_assignment,
    ),
    (
        "missing_person_reports",
        "RN Missing Person Report",
        _map_missing_person,
    ),
    (
        "found_person_reports",
        "RN Found Person Report",
        _map_found_person,
    ),
    (
        "search_found_matches",
        "RN Search Found Match",
        _map_search_found_match,
    ),
    ("resource_profiles", "RN Resource Profile", _map_resource_profile),
    ("resources", "RN Resource Profile", _map_legacy_resource),
    ("resource_requests", "RN Resource Request", _map_resource_request),
    ("work_tool_requests", "RN Work Tool Request", _map_work_tool_request),
    (
        "kitchen_meal_productions",
        "RN Kitchen Production",
        _map_kitchen_production,
    ),
    ("donor_programs", "RN Donor Program", _map_donor_program),
    (
        "donor_program_updates",
        "RN Donor Program Update",
        _map_donor_program_update,
    ),
    ("recovery_projects", "RN Recovery Project", _map_recovery_project),
    (
        "recovery_project_updates",
        "RN Recovery Project Update",
        _map_recovery_project_update,
    ),
]


def _key_spec(doctype, fields):
    if doctype == "RN Stock Observation":
        return "title", fields.get("title")

    if "sync_event_id" in fields:
        return (
            "sync_event_id",
            fields["sync_event_id"],
        )

    if (
        "legacy_id" in fields
        and frappe.get_meta(doctype).has_field("legacy_id")
    ):
        return (
            "legacy_id",
            fields["legacy_id"],
        )

    source_id = fields.get("_source_id")

    if doctype in (
        "RN Donor Program",
        "RN Recovery Project",
    ):
        return (
            "notes",
            [
                "like",
                f"%[legacy_id:{source_id}]%",
            ],
        )

    if doctype in (
        "RN Donor Program Update",
        "RN Recovery Project Update",
    ):
        return (
            "update_notes",
            [
                "like",
                f"%[legacy_id:{source_id}]%",
            ],
        )

    raise ValueError(
        f"No deterministic upsert key for {doctype}"
    )


def _validate_required_links(doctype, fields):
    meta = frappe.get_meta(doctype)
    errors = []

    for df in meta.fields:
        value = fields.get(df.fieldname)

        if df.reqd and value in (None, ""):
            errors.append(
                f"missing required field {df.fieldname}"
            )
            continue

        if value in (None, ""):
            continue

        if (
            df.fieldtype == "Link"
            and df.options
            and not _is_pending_link(value)
            and not frappe.db.exists(
                df.options,
                value,
            )
        ):
            errors.append(
                f"invalid link {df.fieldname}={value}"
            )

        if df.fieldtype == "Select" and df.options:
            allowed = {
                x.strip()
                for x in str(df.options).splitlines()
                if x.strip()
            }

            if (
                allowed
                and str(value) not in allowed
            ):
                errors.append(
                    f"invalid select {df.fieldname}={value}"
                )

    return errors


def _upsert_doc(doctype, fields):
    key_field, key_value = _key_spec(
        doctype,
        fields,
    )

    if key_value in (None, ""):
        raise ValueError(
            f"{doctype}: empty upsert key {key_field}"
        )

    existing = frappe.db.exists(
        doctype,
        {
            key_field: key_value,
        },
    )

    if existing:
        doc = frappe.get_doc(
            doctype,
            existing,
        )
        action = "updated"
    else:
        doc = frappe.new_doc(doctype)
        action = "inserted"

    valid_columns = set(
        doc.meta.get_valid_columns()
    )

    for key, value in fields.items():
        if (
            key.startswith("_")
            or key not in valid_columns
        ):
            continue

        doc.set(key, value)

    doc.save(ignore_permissions=True)

    return action


def compare_doctype_counts_p3():
    result = {}

    for doctype in P3_TABLES:
        result[doctype] = (
            frappe.db.count(doctype)
            if frappe.db.exists("DocType", doctype)
            else None
        )

    return result


def source_counts_p3():
    import psycopg2
    import psycopg2.extras

    with psycopg2.connect(get_rescuenet_pg_dsn()) as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            result = {}

            for table, sql in SOURCE_COUNTS_SQL_P3.items():
                cur.execute(sql)
                result[table] = cur.fetchone()["count"]

            return result


def _source_table_has_column(cur, table, column):
    cur.execute(
        """
        select exists (
            select 1
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
              and column_name = %s
        )
        """,
        (table, column),
    )

    return bool(cur.fetchone()["exists"])


def _fetch_source_rows(cur, table, limit=None):
    has_deleted_at = _source_table_has_column(
        cur,
        table,
        "deleted_at",
    )

    sql = f"select * from {table}"

    if has_deleted_at:
        sql += " where deleted_at is null"

    sql += " order by created_at nulls last, id"

    if limit:
        sql += " limit %s"
        cur.execute(sql, (limit,))
    else:
        cur.execute(sql)

    return cur.fetchall()


def import_from_pg_p3(dry_run=True, limit=None):
    import psycopg2
    import psycopg2.extras

    dry_run = str(dry_run).lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    limit = int(limit) if limit else None

    summary = {
        "dry_run": dry_run,
        "tables": {},
        "target_counts_before": compare_doctype_counts_p3(),
    }

    _P3_PENDING_LINKS.clear()

    try:
        with psycopg2.connect(
            get_rescuenet_pg_dsn()
        ) as conn:

            with conn.cursor(
                cursor_factory=(
                    psycopg2.extras.RealDictCursor
                )
            ) as cur:

                # Dry-run must be able to validate child rows
                # whose parents are part of this same import,
                # without writing temporary Frappe documents.
                if dry_run:
                    for table, doctype, _mapper in MAPPINGS:
                        if table in P3_DEFERRED_TABLES:
                            continue

                        rows = _fetch_source_rows(
                            cur,
                            table,
                            limit=limit,
                        )

                        for row in rows:
                            source_id = row.get("id")

                            if source_id is None:
                                continue

                            _P3_PENDING_LINKS.add(
                                (
                                    doctype,
                                    str(source_id),
                                )
                            )

                for table, doctype, mapper in MAPPINGS:
                    rows = _fetch_source_rows(
                        cur,
                        table,
                        limit=limit,
                    )

                    stat = {
                        "source_rows": len(rows),
                        "valid": 0,
                        "invalid": 0,
                        "deferred": 0,
                        "inserted": 0,
                        "updated": 0,
                        "errors": [],
                    }

                    if table in P3_DEFERRED_TABLES:
                        stat["deferred"] = len(rows)
                        stat["defer_reason"] = (
                            P3_DEFERRED_TABLES[table]
                        )

                        summary["tables"][table] = stat
                        continue

                    for row in rows:
                        try:
                            fields = mapper(row)

                            errors = _validate_required_links(
                                doctype,
                                fields,
                            )

                            if errors:
                                stat["invalid"] += 1
                                stat["errors"].append({
                                    "id": row.get("id"),
                                    "errors": errors,
                                })
                                continue

                            stat["valid"] += 1

                            if not dry_run:
                                action = _upsert_doc(
                                    doctype,
                                    fields,
                                )

                                stat[action] += 1

                        except Exception as exc:
                            stat["invalid"] += 1
                            stat["errors"].append({
                                "id": row.get("id"),
                                "errors": [str(exc)],
                            })

                    summary["tables"][table] = stat

        if not dry_run:
            frappe.db.commit()

        summary["target_counts_after"] = (
            compare_doctype_counts_p3()
        )

        return summary

    finally:
        _P3_PENDING_LINKS.clear()


def import_live_p3():
    return import_from_pg_p3(dry_run=False)
