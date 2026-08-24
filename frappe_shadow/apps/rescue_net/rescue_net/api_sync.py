import hashlib
import json

import frappe
from frappe.utils import now_datetime

from rescue_net.access_policy import (
    is_system_manager,
    rn_actor,
)


SYNC_MANAGER_ROLES = {
    "command_center",
}


def _require_login():
    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(
            "Login diperlukan untuk Sync.",
            frappe.PermissionError,
        )

    return user


def _has_control():
    if is_system_manager():
        return True

    if (
        not frappe.session.user
        or frappe.session.user == "Guest"
    ):
        return False

    try:
        actor = rn_actor()
    except Exception:
        return False

    return bool(
        actor
        and getattr(
            actor,
            "role",
            None,
        ) in SYNC_MANAGER_ROLES
    )


def _require_control():
    _require_login()

    if _has_control():
        return

    frappe.throw(
        "Sync write saat ini hanya "
        "untuk Control Centre.",
        frappe.PermissionError,
    )


def _loads(value, default=None):
    if default is None:
        default = {}

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return default

        return json.loads(value)

    return value


def _dumps(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _checksum(payload):
    raw = _dumps(payload)

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()


def _event_id(value=None):
    value = (value or "").strip()

    if value:
        return value

    return (
        "sync-"
        + frappe.generate_hash(
            length=16
        )
    )


def _existing_log(event_id):
    name = frappe.db.get_value(
        "RN Sync Log",
        {"event_id": event_id},
        "name",
    )

    if not name:
        return None

    return frappe.get_doc(
        "RN Sync Log",
        name,
    )


def _disaster_from_payload(payload):
    return (
        payload.get("disaster_event_id")
        or payload.get("disaster_event")
        or None
    )


def _apply_resource_request(
    event_id,
    event,
):
    payload = event.get(
        "payload_json"
    ) or {}

    resource_id = payload.get(
        "resource_id"
    )
    requested_by_type = payload.get(
        "requested_by_type"
    )
    requested_by_id = payload.get(
        "requested_by_id"
    )

    if (
        not resource_id
        or not requested_by_type
        or not requested_by_id
    ):
        return {
            "apply_status": "rejected",
            "reason": (
                "resource_id, "
                "requested_by_type, and "
                "requested_by_id are required"
            ),
        }

    if not frappe.db.exists(
        "RN Resource Profile",
        resource_id,
    ):
        raise frappe.DoesNotExistError(
            "RN Resource Profile not found: "
            + str(resource_id)
        )

    existing = frappe.db.get_value(
        "RN Resource Request",
        {"sync_event_id": event_id},
        "name",
    )

    if existing:
        return {
            "apply_status":
                "duplicate_ignored",
            "object_type":
                "resource_request",
            "local_object_id":
                event.get("object_id"),
            "server_object_id":
                existing,
        }

    doc = frappe.new_doc(
        "RN Resource Request"
    )

    doc.sync_event_id = event_id
    doc.source_object_id = (
        event.get("object_id")
    )
    doc.resource_profile = resource_id
    doc.requested_by_type = (
        requested_by_type
    )
    doc.requested_by_id = (
        requested_by_id
    )
    doc.request_reason = payload.get(
        "request_reason"
    )
    doc.related_need_id = payload.get(
        "related_need_id"
    )
    doc.related_distribution_flow_id = (
        payload.get(
            "related_distribution_flow_id"
        )
    )
    doc.requested_quantity = payload.get(
        "requested_quantity"
    )
    doc.requested_time = payload.get(
        "requested_time"
    )
    doc.request_status = "requested"
    doc.source_user_id = event.get(
        "source_user_id"
    )

    doc.insert(
        ignore_permissions=True
    )

    return {
        "apply_status": "applied",
        "object_type":
            "resource_request",
        "local_object_id":
            event.get("object_id"),
        "server_object_id":
            doc.name,
    }


def _apply_event(
    event_id,
    event,
):
    if (
        event.get("object_type")
        == "resource_request"
        and event.get("operation")
        == "create"
    ):
        return _apply_resource_request(
            event_id,
            event,
        )

    return {
        "apply_status": "stored_only",
        "reason": (
            "No apply rule for this "
            "object_type/operation yet"
        ),
    }


def _normalize_event(
    event,
    source_device_id=None,
    source_server_id=None,
):
    event = _loads(event, {})

    payload = _loads(
        event.get("payload_json"),
        {},
    )

    return {
        "event_id": _event_id(
            event.get("event_id")
        ),
        "object_type":
            event.get("object_type"),
        "object_id":
            event.get("object_id"),
        "operation":
            event.get("operation")
            or "create",
        "payload_json": payload,
        "source_server_id":
            event.get("source_server_id")
            or source_server_id,
        "source_device_id":
            event.get("source_device_id")
            or source_device_id,
        "source_user_id":
            event.get("source_user_id"),
        "source_organization_id":
            event.get(
                "source_organization_id"
            ),
    }


def _accepted_result(
    event,
    apply_status,
    apply_result=None,
):
    result = {
        "event_id":
            event["event_id"],
        "object_type":
            event.get("object_type"),
        "object_id":
            event.get("object_id"),
        "operation":
            event.get("operation"),
        "apply_status":
            apply_status,
    }

    if apply_result is not None:
        result["apply_result"] = (
            apply_result
        )

    return result


def _push(
    source_device_id=None,
    source_server_id=None,
    events=None,
):
    events = _loads(events, [])

    if not isinstance(events, list):
        frappe.throw(
            "events harus berupa list"
        )

    accepted = []
    rejected = []

    for raw in events:
        event = _normalize_event(
            raw,
            source_device_id,
            source_server_id,
        )

        event_id = event["event_id"]

        existing = _existing_log(
            event_id
        )

        if existing:
            accepted.append(
                _accepted_result(
                    event,
                    "duplicate_ignored",
                )
            )
            continue

        savepoint = (
            "sync_"
            + frappe.generate_hash(
                length=12
            )
        )

        frappe.db.savepoint(
            savepoint
        )

        try:
            payload = event[
                "payload_json"
            ]

            log = frappe.new_doc(
                "RN Sync Log"
            )

            log.event_id = event_id
            log.object_type = (
                event.get("object_type")
                or "unknown"
            )
            log.object_id = event.get(
                "object_id"
            )
            log.operation = (
                event.get("operation")
                or "create"
            )
            log.source_server_id = (
                event.get(
                    "source_server_id"
                )
            )
            log.source_device_id = (
                event.get(
                    "source_device_id"
                )
            )
            log.source_user_id = (
                event.get(
                    "source_user_id"
                )
            )
            log.source_organization_id = (
                event.get(
                    "source_organization_id"
                )
            )
            log.disaster_event_id = (
                _disaster_from_payload(
                    payload
                )
            )
            log.payload_json = _dumps(
                payload
            )
            log.payload_checksum = (
                _checksum(payload)
            )
            log.verification_status = (
                "unverified"
            )
            log.apply_status = (
                "accepted"
            )
            log.received_at = (
                now_datetime()
            )

            log.insert(
                ignore_permissions=True
            )

            apply_result = _apply_event(
                event_id,
                event,
            )

            apply_status = (
                apply_result.get(
                    "apply_status",
                    "accepted",
                )
            )

            log.apply_status = (
                apply_status
            )
            log.apply_result_json = (
                _dumps(apply_result)
            )

            if apply_status == "applied":
                log.applied_at = (
                    now_datetime()
                )

            if apply_status in {
                "rejected",
                "conflict",
            }:
                log.conflict_status = (
                    "needs_review"
                )
                log.error_message = (
                    apply_result.get(
                        "reason"
                    )
                )

            log.save(
                ignore_permissions=True
            )

            accepted.append(
                _accepted_result(
                    event,
                    apply_status,
                    apply_result,
                )
            )

        except Exception as ex:
            frappe.db.rollback(
                save_point=savepoint
            )

            rejected.append({
                "event_id": event_id,
                "object_type":
                    event.get(
                        "object_type"
                    ),
                "object_id":
                    event.get(
                        "object_id"
                    ),
                "operation":
                    event.get(
                        "operation"
                    ),
                "error": str(ex),
            })

    return {
        "status": "ok",
        "accepted_count":
            len(accepted),
        "rejected_count":
            len(rejected),
        "accepted": accepted,
        "rejected": rejected,
    }


def _identity_keys(value):
    if not value:
        return set()

    value = str(value).strip()

    if not value:
        return set()

    keys = {value}

    if ":" in value:
        keys.add(
            value.split(":", 1)[1]
        )

    return keys


def _same_identity(left, right):
    return bool(
        _identity_keys(left)
        & _identity_keys(right)
    )


def _prepare_scoped_booking_events(events):
    actor = rn_actor()

    if not actor:
        frappe.throw(
            "RN User Account aktif diperlukan "
            "untuk Sync booking.",
            frappe.PermissionError,
        )

    actor_name = getattr(
        actor,
        "name",
        None,
    )
    actor_org = getattr(
        actor,
        "organization",
        None,
    )
    actor_posko = getattr(
        actor,
        "posko",
        None,
    )

    raw_events = _loads(
        events,
        [],
    )

    if not isinstance(
        raw_events,
        list,
    ):
        frappe.throw(
            "events harus berupa list."
        )

    prepared = []

    for raw_event in raw_events:
        event = dict(
            raw_event or {}
        )

        object_type = str(
            event.get(
                "object_type"
            ) or ""
        ).strip()

        operation = str(
            event.get(
                "operation"
            ) or ""
        ).strip()

        if (
            object_type
            != "resource_request"
            or operation != "create"
        ):
            frappe.throw(
                "User biasa hanya boleh "
                "Sync booking resource_request/create.",
                frappe.PermissionError,
            )

        payload = _loads(
            event.get(
                "payload_json"
            ),
            {},
        )

        if not isinstance(
            payload,
            dict,
        ):
            frappe.throw(
                "payload_json booking tidak valid."
            )

        requested_by_type = str(
            payload.get(
                "requested_by_type"
            )
            or "user"
        ).strip().lower()

        requested_by_id = (
            payload.get(
                "requested_by_id"
            )
        )

        if requested_by_type in {
            "user",
            "individual",
            "personal",
            "other",
            "lainnya",
        }:
            requested_by_type = "user"
            requested_by_id = (
                actor_name
                or frappe.session.user
            )

        elif requested_by_type in {
            "organization",
            "organisation",
            "kelompok",
            "group",
        }:
            if not actor_org:
                frappe.throw(
                    "Akun ini belum terhubung "
                    "ke Kelompok.",
                    frappe.PermissionError,
                )

            requested_by_type = "organization"
            requested_by_id = actor_org

        elif requested_by_type == "posko":
            if not actor_posko:
                frappe.throw(
                    "Akun ini belum terhubung "
                    "ke Posko.",
                    frappe.PermissionError,
                )

            requested_by_id = actor_posko

        else:
            frappe.throw(
                "Tipe requester booking "
                "tidak valid.",
                frappe.PermissionError,
            )

        payload["requested_by_type"] = (
            requested_by_type
        )
        payload["requested_by_id"] = (
            requested_by_id
        )

        # Browser tidak menjadi authority
        # untuk identitas user.
        event["source_user_id"] = (
            actor_name
            or frappe.session.user
        )

        event[
            "source_organization_id"
        ] = actor_org

        event[
            "disaster_event_id"
        ] = payload.get(
            "disaster_event_id"
        )

        event[
            "payload_json"
        ] = payload

        prepared.append(event)

    return prepared


@frappe.whitelist()
def push(
    source_device_id=None,
    source_server_id=None,
    events=None,
):
    _require_login()

    if _has_control():
        prepared_events = events
    else:
        prepared_events = (
            _prepare_scoped_booking_events(
                events
            )
        )

    return _push(
        source_device_id,
        source_server_id,
        prepared_events,
    )


def _resolve_disaster_event(value):
    if not value:
        return value

    if frappe.db.exists(
        "RN Disaster Event",
        value,
    ):
        return value

    for legacy_id in (
        value,
        "disaster_events:" + value,
    ):
        name = frappe.db.get_value(
            "RN Disaster Event",
            {"legacy_id": legacy_id},
            "name",
        )

        if name:
            return name

    return value


def _event_filter(
    doctype,
    event_id,
):
    if not frappe.db.exists(
        "DocType",
        doctype,
    ):
        return None

    if doctype == "RN Disaster Event":
        return {
            "name": event_id
        }

    meta = frappe.get_meta(
        doctype
    )

    for fieldname in (
        "disaster_event",
        "disaster_event_id",
    ):
        if meta.has_field(
            fieldname
        ):
            return {
                fieldname: event_id
            }

    return {}


def _rows(
    doctype,
    event_id,
    fields,
    limit=200,
):
    filters = _event_filter(
        doctype,
        event_id,
    )

    if filters is None:
        return []

    meta = frappe.get_meta(
        doctype
    )

    actual = ["name"]

    for fieldname in fields:
        if meta.has_field(fieldname):
            actual.append(fieldname)

    return frappe.get_all(
        doctype,
        filters=filters,
        fields=actual,
        order_by="modified desc",
        limit_page_length=limit,
    )


def _resource_requests(
    event_id,
):
    if not frappe.db.exists(
        "DocType",
        "RN Resource Request",
    ):
        return []

    requests = frappe.get_all(
        "RN Resource Request",
        fields=[
            "name",
            "sync_event_id",
            "source_object_id",
            "resource_profile",
            "requested_by_type",
            "requested_by_id",
            "request_reason",
            "related_need_id",
            "related_distribution_flow_id",
            "requested_quantity",
            "requested_time",
            "request_status",
            "creation",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=300,
    )

    result = []

    for row in requests:
        resource = frappe.db.get_value(
            "RN Resource Profile",
            row.resource_profile,
            [
                "resource_name",
                "resource_type",
                "owner_id",
                "disaster_event",
            ],
            as_dict=True,
        )

        if not resource:
            continue

        if (
            resource.get(
                "disaster_event"
            )
            != event_id
        ):
            continue

        result.append({
            "id": row.name,
            "resource_id":
                row.resource_profile,
            "requested_by_type":
                row.requested_by_type,
            "requested_by_id":
                row.requested_by_id,
            "request_reason":
                row.request_reason,
            "related_need_id":
                row.related_need_id,
            "related_distribution_flow_id":
                row.related_distribution_flow_id,
            "requested_quantity":
                row.requested_quantity,
            "requested_time":
                row.requested_time,
            "status":
                row.request_status,
            "disaster_event_id":
                resource.get(
                    "disaster_event"
                ),
            "resource_name":
                resource.get(
                    "resource_name"
                ),
            "resource_type":
                resource.get(
                    "resource_type"
                ),
            "owner_id":
                resource.get(
                    "owner_id"
                ),
            "created_at":
                row.creation,
            "updated_at":
                row.modified,
        })

    return result


def _sync_events(
    since=None,
    disaster_event_id=None,
    resolved_event=None,
    safe=False,
):
    filters = {}

    if since:
        filters["creation"] = [
            ">=",
            since,
        ]

    if safe and disaster_event_id:
        event_ids = []

        for value in (
            disaster_event_id,
            resolved_event,
        ):
            if (
                value
                and value not in event_ids
            ):
                event_ids.append(value)

        filters["disaster_event_id"] = [
            "in",
            event_ids,
        ]

    fields = [
        "name",
        "event_id",
        "object_type",
        "object_id",
        "operation",
        "source_server_id",
        "source_device_id",
        "source_user_id",
        "source_organization_id",
        "verification_status",
        "apply_status",
        "conflict_status",
        "error_message",
        "creation",
        "modified",
    ]

    if not safe:
        fields.insert(
            5,
            "payload_json",
        )

    rows = frappe.get_all(
        "RN Sync Log",
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=200,
    )

    result = []

    for row in rows:
        item = dict(row)

        item["id"] = item.pop(
            "name"
        )
        item["created_at"] = (
            item.pop("creation")
        )
        item["updated_at"] = (
            item.pop("modified")
        )

        if (
            not safe
            and "payload_json" in item
        ):
            try:
                item["payload_json"] = (
                    _loads(
                        item.get(
                            "payload_json"
                        ),
                        {},
                    )
                )
            except Exception:
                pass

        result.append(item)

    return result


def _pull(
    disaster_event_id,
    since=None,
    safe_sync_events=False,
):
    resolved_event = (
        _resolve_disaster_event(
            disaster_event_id
        )
    )

    return {
        "disaster_event_id":
            disaster_event_id,
        "generated_at":
            now_datetime(),
        "disasters": _rows(
            "RN Disaster Event",
            resolved_event,
            [
                "legacy_id",
                "title",
                "name",
                "status",
                "started_at",
            ],
            10,
        ),
        "ecosystem_members": [],
        "resources": _rows(
            "RN Resource Profile",
            resolved_event,
            [
                "legacy_id",
                "resource_name",
                "resource_type",
                "owner_type",
                "owner_id",
                "quantity",
                "unit",
                "availability_status",
                "current_location",
                "coverage_area",
            ],
            300,
        ),
        "resource_shares": [],
        "resource_requests":
            _resource_requests(
                resolved_event
            ),
        "resource_assignments": [],
        "aid_offers": _rows(
            "RN Aid Offer",
            resolved_event,
            [
                "legacy_id",
                "donor_name",
                "item_name",
                "quantity",
                "unit",
                "offer_status",
                "target_posko",
            ],
            300,
        ),
        "transport_spaces": [],
        "distribution_flows":
            _rows(
                "RN Distribution Flow",
                resolved_event,
                [
                    "legacy_id",
                    "item_name",
                    "quantity",
                    "unit",
                    "flow_status",
                    "source_posko",
                    "destination_posko",
                ],
                300,
            ),
        "sync_events":
            _sync_events(
                since,
                disaster_event_id,
                resolved_event,
                safe_sync_events,
            ),
    }


@frappe.whitelist()
def pull(
    disaster_event_id,
    since=None,
):
    _require_login()

    return _pull(
        disaster_event_id,
        since,
        safe_sync_events=(
            not _has_control()
        ),
    )


@frappe.whitelist()
def status(limit=50):
    _require_control()

    limit = min(
        max(int(limit or 50), 1),
        200,
    )

    rows = frappe.get_all(
        "RN Sync Log",
        fields=[
            "event_id",
            "object_type",
            "object_id",
            "operation",
            "source_device_id",
            "apply_status",
            "conflict_status",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )

    counts = {}

    for row in rows:
        key = (
            row.apply_status
            or "unknown"
        )
        counts[key] = (
            counts.get(key, 0) + 1
        )

    return {
        "counts": counts,
        "items": rows,
    }
