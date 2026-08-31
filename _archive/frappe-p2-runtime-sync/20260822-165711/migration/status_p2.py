import json
from datetime import datetime, timezone

import frappe

from rescue_net.migration.import_p2_from_rescuenet_pg import compare_doctype_counts_p2, shadow_status_p2, source_counts_p2
from rescue_net.migration.validation_p2 import build_validation_report_p2


READINESS_GATES_P2 = {
    'validation_passed': 'P2 validation summary must be pass with zero failures.',
    'shadow_only': 'Migration mode must remain shadow-only until an explicit cutover decision.',
    'counts_matched': 'P2 source-to-shadow counts must have zero blocked doctypes.',
    'links_backfilled': 'Every expected legacy-id reference must resolve to a Link field value.',
    'no_secret_leak': 'Raw session tokens must never appear in the shadow app (fingerprint only).',
}


def build_status_report_p2():
    validation = build_validation_report_p2()
    status = shadow_status_p2()
    source = source_counts_p2()
    target = compare_doctype_counts_p2()
    plan = _migration_plan(source, target, validation)
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': status['mode'],
        'source': status['source'],
        'target_app': status['target_app'],
        'source_counts': source,
        'target_counts': target,
        'migration_plan': plan,
        'link_coverage': validation['link_coverage'],
        'secret_leak_scan': validation['secret_leak_scan'],
        'validation_summary': validation['summary'],
        'readiness': _readiness(status, validation, plan),
    }
    return report


def build_status_report_p2_json():
    return json.dumps(build_status_report_p2(), ensure_ascii=False, indent=2, sort_keys=True)


def _migration_plan(source, target, validation):
    doctype_map = {
        'RN User Account': ['user_accounts'],
        'RN User Session': ['user_sessions'],
        'RN Device': ['devices'],
        'RN Verification Request': ['verification_requests'],
        'RN Verifier Profile': ['verifier_profiles'],
        'RN Verification Endorsement': ['verification_endorsements'],
        'RN Verification Action': ['verification_actions'],
        'RN Trusted Verification Request': ['trusted_verification_requests'],
    }
    rows = []
    totals = {'source': 0, 'target': 0, 'delta': 0, 'matched_doctypes': 0, 'blocked_doctypes': 0}
    validation_counts = validation.get('counts', {})
    for doctype, tables in doctype_map.items():
        source_count = sum(source.get(table, 0) for table in tables)
        target_count = target.get(doctype) or 0
        delta = source_count - target_count
        coverage = 100 if source_count == 0 and target_count >= 0 else round((target_count / source_count) * 100, 2)
        validation_status = validation_counts.get(doctype, {}).get('status', 'n/a')
        if delta > 0:
            action = 'run_import_p2_live'
        elif delta < 0:
            action = 'inspect_extra_shadow_rows'
        elif validation_status not in {'pass', 'n/a'}:
            action = 'fix_validation'
        else:
            action = 'ready'
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
        totals['source'] += source_count
        totals['target'] += target_count
        totals['delta'] += delta
        if delta == 0 and validation_status in {'pass', 'n/a'}:
            totals['matched_doctypes'] += 1
        else:
            totals['blocked_doctypes'] += 1
    totals['coverage_percent'] = 100 if totals['source'] == 0 else round((totals['target'] / totals['source']) * 100, 2)
    return {
        'scope': 'P2 inline source-to-shadow calculation',
        'totals': totals,
        'rows': rows,
        'next_step': 'continue_shadow_only' if totals['blocked_doctypes'] == 0 else 'rerun_import_p2_backfill_validation',
    }


def _readiness(status, validation, plan):
    links_ok = all(
        field_stats.get('missing_or_mismatch_count', 0) == 0
        for fields in validation.get('link_coverage', {}).values()
        for field_stats in fields.values()
    )
    secrets_ok = all(
        check.get('status') == 'pass'
        for check in validation.get('secret_leak_scan', {}).values()
    )
    checks = {
        'validation_passed': validation['summary'].get('status') == 'pass'
        and validation['summary'].get('failure_count') == 0,
        'shadow_only': status.get('mode') == 'shadow-only',
        'counts_matched': plan['totals'].get('blocked_doctypes') == 0,
        'links_backfilled': links_ok,
        'no_secret_leak': secrets_ok,
    }
    return {
        'status': 'ready-for-next-shadow-step' if all(checks.values()) else 'needs-attention',
        'checks': {
            key: {'passed': passed, 'description': READINESS_GATES_P2[key]}
            for key, passed in checks.items()
        },
        'cutover_allowed': False,
        'cutover_note': 'Existing Rescue-Net remains live. This report does not authorize reroute/cutover.',
    }
