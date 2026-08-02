import os

import frappe


P0_TABLES = {
    'RN Disaster Event': ['disaster_events', 'disasters'],
    'RN Organization': ['organizations'],
    'RN Posko': ['posko', 'poskos'],
    'RN Logistic Need': ['logistic_needs', 'consolidated_needs'],
    'RN Aid Offer': ['aid_offers'],
    'RN Distribution Flow': ['distribution_flows'],
    'RN War Room Snapshot': [],
}


def get_rescuenet_pg_dsn():
    return os.environ.get('RESCUENET_PG_DSN') or os.environ.get('DATABASE_URL')


def shadow_status():
    return {
        'mode': 'shadow-only',
        'source': 'rescue-net FastAPI/PostgreSQL',
        'target_app': 'rescue_net',
        'p0_doctypes': list(P0_TABLES),
        'has_pg_dsn': bool(get_rescuenet_pg_dsn()),
    }


def compare_doctype_counts():
    result = {}
    for doctype in P0_TABLES:
        if frappe.db.exists('DocType', doctype):
            result[doctype] = frappe.db.count(doctype)
        else:
            result[doctype] = None
    return result


def import_from_pg(dry_run=True):
    # Placeholder for the first real importer. Keep dry_run=True until field
    # mapping and row-count validation are approved.
    return {
        'dry_run': dry_run,
        'status': 'not_implemented',
        'next': 'Map source tables from docs/migration/db-schema-inventory.txt to P0 DocTypes.',
    }
