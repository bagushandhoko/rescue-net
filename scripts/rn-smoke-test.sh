#!/bin/sh
set -eu

API="${RN_API_BASE:-http://127.0.0.1:8092}"
WEB="${RN_WEB_ROOT:-/volume1/web/rescue-net}"
EVENT="${RN_EVENT_ID:-event-sim-001}"

echo "=== Rescue-Net Smoke Test ==="
echo "API: $API"
echo "WEB: $WEB"
echo "EVENT: $EVENT"
echo ""

fail() {
  echo "❌ FAIL: $1"
  exit 1
}

pass() {
  echo "✅ PASS: $1"
}

echo "1. API health"
curl -fsS "$API/health" >/tmp/rn-health.json || fail "API /health failed"
pass "API /health"

echo "2. AI context"
curl -fsS "$API/ai/context/$EVENT" >/tmp/rn-ai-context.json || fail "AI context failed"
python3 -m json.tool /tmp/rn-ai-context.json >/dev/null || fail "AI context invalid JSON"
grep -q '"summary"' /tmp/rn-ai-context.json || fail "AI context missing summary"
pass "AI context"

echo "3. Resource Profile endpoint"
curl -fsS "$API/resource-profiles?disaster_event_id=$EVENT" >/tmp/rn-resource.json || fail "resource-profiles failed"
python3 -m json.tool /tmp/rn-resource.json >/dev/null || fail "resource-profiles invalid JSON"
pass "resource-profiles"

echo "4. Recovery endpoint"
curl -fsS "$API/recovery-projects?disaster_event_id=$EVENT" >/tmp/rn-recovery.json || fail "recovery-projects failed"
python3 -m json.tool /tmp/rn-recovery.json >/dev/null || fail "recovery-projects invalid JSON"
pass "recovery-projects"

echo "5. OpenAPI route check"
curl -fsS "$API/openapi.json" >/tmp/rn-openapi.json || fail "openapi failed"
grep -q "resource-profiles" /tmp/rn-openapi.json || fail "openapi missing resource-profiles"
grep -q "recovery-projects" /tmp/rn-openapi.json || fail "openapi missing recovery-projects"
grep -q "recovery-project-updates" /tmp/rn-openapi.json || fail "openapi missing recovery-project-updates"
pass "OpenAPI Resource/Recovery routes"

echo "6. JS syntax check"
cd "$WEB"
node -c assets/js/war-room.js >/dev/null || fail "war-room.js syntax"
node -c assets/js/resource-profile.js >/dev/null || fail "resource-profile.js syntax"
node -c assets/js/recovery-reconstruction.js >/dev/null || fail "recovery-reconstruction.js syntax"
node -c assets/js/mockup.js >/dev/null || fail "mockup.js syntax"
pass "JS syntax"

echo "7. Required pages"
test -f pages/war-room.html || fail "missing war-room.html"
test -f pages/resource-profile.html || fail "missing resource-profile.html"
test -f pages/recovery-reconstruction.html || fail "missing recovery-reconstruction.html"
test -f pages/mockup.html || fail "missing mockup.html"
pass "required pages"

echo ""
echo "✅ ALL SMOKE TESTS PASSED"
