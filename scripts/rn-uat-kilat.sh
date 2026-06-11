#!/bin/sh
set -eu

API="${RN_API_BASE:-http://127.0.0.1:8092}"
WEB="${RN_WEB_BASE:-http://192.168.100.32/rescue-net}"
EVENT="${RN_EVENT_ID:-event-sim-001}"
TS="$(date +%Y%m%d%H%M%S)"
TMP="/tmp/rn-uat-kilat"
mkdir -p "$TMP"

pass(){ echo "PASS: $1"; }
fail(){ echo "FAIL: $1"; exit 1; }
json_ok(){ python3 -m json.tool "$1" >/dev/null || fail "$2 invalid JSON"; }

printf '=== RN UAT KILAT ===\nAPI=%s\nWEB=%s\nEVENT=%s\n\n' "$API" "$WEB" "$EVENT"

code=$(curl -fsS -o "$TMP/health.json" -w "%{http_code}" "$API/health") || fail "health request"
[ "$code" = "200" ] || fail "health HTTP $code"
json_ok "$TMP/health.json" "health"
pass "API health"

curl -fsS -X POST "$API/auth/demo-login" \
  -H "Content-Type: application/json" \
  -d '{"username":"command"}' > "$TMP/login.json" || fail "demo login command"
json_ok "$TMP/login.json" "demo login"
grep -q 'session_token' "$TMP/login.json" || fail "demo login missing session_token"
pass "Demo login command role"

curl -fsS "$API/ai/context/$EVENT" > "$TMP/context.json" || fail "AI context"
json_ok "$TMP/context.json" "AI context"
python3 - "$TMP/context.json" <<'PY'
import json, sys
ctx=json.load(open(sys.argv[1]))
s=ctx.get('summary') or {}
required=['posko_count','open_logistic_need_count','donor_program_count','resource_request_count']
missing=[k for k in required if k not in s]
if missing:
    print('missing summary keys:', ','.join(missing))
    raise SystemExit(1)
print('summary posko=%s needs=%s donor_program=%s resource_request=%s' % tuple(s.get(k) for k in required))
PY
pass "AI context summary"

curl -fsS "$API/resource-profiles?disaster_event_id=$EVENT" > "$TMP/resources.json" || fail "resource profiles"
json_ok "$TMP/resources.json" "resource profiles"
python3 - "$TMP/resources.json" <<'PY'
import json, sys
items=json.load(open(sys.argv[1]))
print('resource_profiles=%d' % len(items))
raise SystemExit(0 if len(items) > 0 else 1)
PY
pass "Resource Profile has data"

curl -fsS "$API/recovery-projects?disaster_event_id=$EVENT" > "$TMP/recovery.json" || fail "recovery projects"
json_ok "$TMP/recovery.json" "recovery projects"
python3 - "$TMP/recovery.json" <<'PY'
import json, sys
items=json.load(open(sys.argv[1]))
print('recovery_projects=%d' % len(items))
raise SystemExit(0 if len(items) > 0 else 1)
PY
pass "Recovery has data"

for page in \
  "/" \
  "/pages/war-room.html?event=$EVENT" \
  "/pages/resource-profile.html?event=$EVENT" \
  "/pages/recovery-reconstruction.html?event=$EVENT" \
  "/pages/ai-analyst.html?event=$EVENT" \
  "/pages/sync-console.html?event=$EVENT" \
  "/pages/evidence.html?event=$EVENT" \
  "/pages/verification-approval.html?event=$EVENT" \
  "/pages/mockup.html?screen=welcome"
do
  code=$(curl -fsS -o "$TMP/page.html" -w "%{http_code}" "$WEB$page") || fail "page $page"
  [ "$code" = "200" ] || fail "page $page HTTP $code"
done
pass "Core web pages local 200"

EVENT_ID="uat-sync-$TS"
REQ_ID="uat-resource-request-$TS"
cat > "$TMP/sync-payload.json" <<JSON
{
  "source_device_id": "uat-device-$TS",
  "source_server_id": "uat-script",
  "events": [
    {
      "event_id": "$EVENT_ID",
      "object_type": "resource_request",
      "object_id": "$REQ_ID",
      "operation": "create",
      "source_device_id": "uat-device-$TS",
      "source_user_id": "uat-command-user",
      "source_organization_id": "org-sim-bpbd",
      "payload_json": {
        "disaster_event_id": "$EVENT",
        "resource_id": "res-tni-transport-air-01",
        "requested_by_type": "organization",
        "requested_by_id": "org-sim-bpbd",
        "request_reason": "UAT kilat sync push test $TS",
        "requested_quantity": 1,
        "requested_time": "UAT now",
        "local_status": "pending_sync"
      }
    }
  ]
}
JSON
curl -fsS -X POST "$API/sync/push" -H "Content-Type: application/json" -d @"$TMP/sync-payload.json" > "$TMP/sync-push.json" || fail "sync push"
json_ok "$TMP/sync-push.json" "sync push"
python3 - "$TMP/sync-push.json" <<'PY'
import json, sys
r=json.load(open(sys.argv[1]))
print('sync accepted=%s rejected=%s' % (r.get('accepted_count'), r.get('rejected_count')))
if int(r.get('accepted_count') or 0) < 1:
    raise SystemExit(1)
PY
pass "Sync push accepted UAT event"

curl -fsS "$API/sync/pull/$EVENT" > "$TMP/sync-pull.json" || fail "sync pull"
json_ok "$TMP/sync-pull.json" "sync pull"
grep -q "$EVENT_ID" "$TMP/sync-pull.json" || fail "sync pull missing UAT event"
pass "Sync pull sees UAT event"

curl -fsS "$API/audit-events?limit=5" > "$TMP/audit.json" || fail "audit events"
json_ok "$TMP/audit.json" "audit events"
pass "Audit endpoint reachable"

curl -fsS "$API/sync-conflicts?limit=5" > "$TMP/conflicts.json" || fail "sync conflicts"
json_ok "$TMP/conflicts.json" "sync conflicts"
pass "Sync conflict endpoint reachable"

echo ""
echo "OK: RN UAT KILAT PASSED"
