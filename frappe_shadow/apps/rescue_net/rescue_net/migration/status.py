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
    'inline_counts_matched': 'Inline P0 source-to-shadow counts must have zero blocked doctypes.',
}


def build_status_report():
    validation = build_validation_report()
    war_room = preview_shadow_snapshot()
    status = shadow_status()
    source = source_counts()
    target = compare_doctype_counts()
    inline_plan = _inline_migration_plan(source, target, validation)
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': status['mode'],
        'source': status['source'],
        'target_app': status['target_app'],
        'source_counts': source,
        'target_counts': target,
        'inline_migration_plan': inline_plan,
        'war_room_metrics': war_room.get('metrics', {}),
        'war_room_counts': war_room.get('counts', {}),
        'validation_summary': validation['summary'],
        'readiness': _readiness(status, validation, war_room, inline_plan),
    }
    return report


def build_status_report_json():
    return json.dumps(build_status_report(), ensure_ascii=False, indent=2, sort_keys=True)


def _inline_migration_plan(source, target, validation):
    p0_map = {
        'RN Disaster Event': ['disaster_events'],
        'RN Organization': ['organizations'],
        'RN Posko': ['posko_nodes'],
        'RN Logistic Need': ['logistic_needs', 'consolidated_needs'],
        'RN Aid Offer': ['aid_offers'],
        'RN Distribution Flow': ['distribution_flows'],
        'RN War Room Snapshot': [],
    }
    rows = []
    totals = {
        'source': 0,
        'target': 0,
        'delta': 0,
        'matched_doctypes': 0,
        'blocked_doctypes': 0,
    }
    validation_counts = validation.get('counts', {})
    for doctype, tables in p0_map.items():
        source_count = sum(source.get(table, 0) for table in tables)
        target_count = target.get(doctype) or 0
        delta = source_count - target_count
        coverage = 100 if source_count == 0 and target_count >= 0 else round((target_count / source_count) * 100, 2)
        validation_status = validation_counts.get(doctype, {}).get('status', 'n/a')
        action = 'ready'
        if doctype == 'RN War Room Snapshot':
            action = 'rebuild_snapshot'
        elif delta > 0:
            action = 'run_import_live'
        elif delta < 0:
            action = 'inspect_extra_shadow_rows'
        elif validation_status not in {'pass', 'n/a'}:
            action = 'fix_validation'
        rows.append({
            'doctype': doctype,
            'source_tables': tables,
            'source_count': source_count,
            'target_count': target_count,
            'delta_source_minus_target': delta,
            'coverage_percent': coverage,
            'validation_status': validation_status,
            'action': action,
        })
        if doctype != 'RN War Room Snapshot':
            totals['source'] += source_count
            totals['target'] += target_count
            totals['delta'] += delta
            if delta == 0 and validation_status in {'pass', 'n/a'}:
                totals['matched_doctypes'] += 1
            else:
                totals['blocked_doctypes'] += 1
    totals['coverage_percent'] = 100 if totals['source'] == 0 else round((totals['target'] / totals['source']) * 100, 2)
    return {
        'scope': 'P0 inline source-to-shadow calculation',
        'totals': totals,
        'rows': rows,
        'next_step': 'continue_shadow_only' if totals['blocked_doctypes'] == 0 else 'rerun_import_backfill_validation',
    }


def _readiness(status, validation, war_room, inline_plan):
    checks = {
        'validation_passed': validation['summary'].get('status') == 'pass'
        and validation['summary'].get('failure_count') == 0,
        'war_room_available': bool(war_room.get('metrics')) and bool(war_room.get('counts')),
        'shadow_only': status.get('mode') == 'shadow-only',
        'inline_counts_matched': inline_plan['totals'].get('blocked_doctypes') == 0,
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
