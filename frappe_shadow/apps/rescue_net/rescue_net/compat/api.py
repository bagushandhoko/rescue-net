import json
from datetime import date, datetime
from decimal import Decimal

import frappe

from rescue_net.migration.status import build_status_report
from rescue_net.migration.war_room import preview_shadow_snapshot


DOCTYPE_FIELDS = {
    'RN Disaster Event': [
        'name', 'legacy_id', 'title', 'event_status', 'severity', 'location_summary', 'started_at', 'modified'
    ],
    'RN Organization': [
        'name', 'legacy_id', 'title', 'organization_type', 'verification_status', 'contact_summary', 'modified'
    ],
    'RN Posko': [
        'name', 'legacy_id', 'title', 'disaster_event', 'organization', 'posko_type', 'address',
        'operational_status', 'verification_status', 'latitude', 'longitude', 'modified'
    ],
    'RN Logistic Need': [
        'name', 'legacy_id', 'title', 'disaster_event', 'posko', 'item_name', 'quantity', 'unit',
        'urgency', 'need_status', 'source_table', 'modified'
    ],
    'RN Aid Offer': [
        'name', 'legacy_id', 'title', 'donor_name', 'disaster_event', 'target_posko', 'item_name',
        'quantity', 'unit', 'pickup_location', 'offer_status', 'donor_contact', 'notes', 'modified'
    ],
    'RN Distribution Flow': [
        'name', 'legacy_id', 'title', 'disaster_event', 'logistic_need', 'aid_offer', 'source_posko',
        'destination_posko', 'item_name', 'quantity', 'unit', 'flow_status', 'eta_final', 'modified'
    ],
}

LEGACY_KEYS = {
    'RN Disaster Event': 'disasters',
    'RN Organization': 'organizations',
    'RN Posko': 'poskos',
    'RN Logistic Need': 'logistic_needs',
    'RN Aid Offer': 'aid_offers',
    'RN Distribution Flow': 'distribution_flows',
}


@frappe.whitelist(allow_guest=True)
def health():
    return {
        'system': 'Rescue-Net Frappe Shadow Compatibility API',
        'status': 'running',
        'mode': 'shadow-only',
        'cutover_allowed': False,
    }


@frappe.whitelist(allow_guest=True)
def status():
    return build_status_report()


@frappe.whitelist(allow_guest=True)
def disasters(limit=100):
    return _legacy_response('RN Disaster Event', limit)


@frappe.whitelist(allow_guest=True)
def organizations(limit=100):
    return _legacy_response('RN Organization', limit)


@frappe.whitelist(allow_guest=True)
def poskos(limit=100):
    return _legacy_response('RN Posko', limit)


@frappe.whitelist(allow_guest=True)
def logistic_needs(limit=100):
    return _legacy_response('RN Logistic Need', limit)


@frappe.whitelist(allow_guest=True)
def aid_offers(limit=100):
    return _legacy_response('RN Aid Offer', limit)


@frappe.whitelist(allow_guest=True)
def distribution_flows(limit=100):
    return _legacy_response('RN Distribution Flow', limit)


@frappe.whitelist(allow_guest=True)
def war_room():
    return _serialize(preview_shadow_snapshot())


@frappe.whitelist(allow_guest=True)
def all_p0(limit=100):
    return {
        'mode': 'shadow-only',
        'cutover_allowed': False,
        'data': {
            LEGACY_KEYS[doctype]: _rows(doctype, limit)
            for doctype in DOCTYPE_FIELDS
        },
    }


def _legacy_response(doctype, limit):
    return {
        'mode': 'shadow-only',
        'cutover_allowed': False,
        LEGACY_KEYS[doctype]: _rows(doctype, limit),
    }


def _rows(doctype, limit):
    requested = int(limit or 100)
    capped = max(1, min(requested, 500))
    fields = [field for field in DOCTYPE_FIELDS[doctype] if frappe.get_meta(doctype).has_field(field) or field == 'name']
    rows = frappe.get_all(doctype, fields=fields, order_by='modified desc', limit_page_length=capped)
    return [_normalize_row(row) for row in rows]


def _normalize_row(row):
    data = dict(row)
    legacy_id = data.get('legacy_id') or data.get('name')
    data.setdefault('id', legacy_id)
    data['frappe_name'] = data.get('name')
    return _serialize(data)


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
