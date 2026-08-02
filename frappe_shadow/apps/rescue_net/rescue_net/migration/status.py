import json
from datetime import datetime, timezone

import frappe

from rescue_net.migration.import_from_rescuenet_pg import compare_doctype_counts, shadow_status, source_counts
from rescue_net.migration.validation import build_validation_report
from rescue_net.migration.war_room import preview_shadow_snapshot


READINESS_GATES = {
    'validation_passed': 'Validation summary must be pass with zero failures.',
    'war_room_available': 'Shadow War Room snapshot preview must build successfully.',
    'shadow_only': 'Migration mode must remain shadow-only until an explicit cutover decision.',
}


def build_status_report():
    validation = build_validation_report()
    war_room = preview_shadow_snapshot()
    status = shadow_status()
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': status['mode'],
        'source': status['source'],
        'target_app': status['target_app'],
        'source_counts': source_counts(),
        'target_counts': compare_doctype_counts(),
        'war_room_metrics': war_room.get('metrics', {}),
        'war_room_counts': war_room.get('counts', {}),
        'validation_summary': validation['summary'],
        'readiness': _readiness(status, validation, war_room),
    }
    return report


def build_status_report_json():
    return json.dumps(build_status_report(), ensure_ascii=False, indent=2, sort_keys=True)


def _readiness(status, validation, war_room):
    checks = {
        'validation_passed': validation['summary'].get('status') == 'pass'
        and validation['summary'].get('failure_count') == 0,
        'war_room_available': bool(war_room.get('metrics')) and bool(war_room.get('counts')),
        'shadow_only': status.get('mode') == 'shadow-only',
    }
    return {
        'status': 'ready-for-next-shadow-step' if all(checks.values()) else 'needs-attention',
        'checks': {
            key: {
                'passed': passed,
                'description': READINESS_GATES[key],
            }
            for key, passed in checks.items()
        },
        'cutover_allowed': False,
        'cutover_note': 'Existing Rescue-Net remains live. This report does not authorize reroute/cutover.',
    }
