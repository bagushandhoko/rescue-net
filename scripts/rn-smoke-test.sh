#!/bin/sh
set -eu

# Synology non-interactive SSH sessions can miss /usr/local/bin, where Node.js is installed.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

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
grep -q "audit-events" /tmp/rn-openapi.json || fail "openapi missing audit-events"
grep -q "sync-conflicts" /tmp/rn-openapi.json || fail "openapi missing sync-conflicts"
pass "OpenAPI Resource/Recovery/Audit/Sync routes"

echo "6. Audit and conflict endpoints"
curl -fsS "$API/audit-events?limit=5" >/tmp/rn-audit-events.json || fail "audit-events failed"
python3 -m json.tool /tmp/rn-audit-events.json >/dev/null || fail "audit-events invalid JSON"
curl -fsS "$API/sync-conflicts?limit=5" >/tmp/rn-sync-conflicts.json || fail "sync-conflicts failed"
python3 -m json.tool /tmp/rn-sync-conflicts.json >/dev/null || fail "sync-conflicts invalid JSON"
pass "audit-events and sync-conflicts"

echo "7. JS syntax check"
cd "$WEB"
node -c assets/js/war-room.js >/dev/null || fail "war-room.js syntax"
node -c assets/js/resource-profile.js >/dev/null || fail "resource-profile.js syntax"
node -c assets/js/recovery-reconstruction.js >/dev/null || fail "recovery-reconstruction.js syntax"
node -c assets/js/mockup.js >/dev/null || fail "mockup.js syntax"
node -c assets/js/sync-console.js >/dev/null || fail "sync-console.js syntax"
pass "JS syntax"

echo "8. Backend source compile"
python3 -m py_compile backend/main.py backend/app_shared.py backend/routes/*.py || fail "backend source compile failed"
pass "backend source compile"

echo "9. Duplicate route check"
python3 - <<'PY' >/tmp/rn-route-check.txt
from pathlib import Path
import re
from collections import defaultdict
text = Path("backend/main.py").read_text(errors="ignore")
routes = []
for m in re.finditer(r'@app\.(get|post|put|patch|delete)\("([^"]+)"', text):
    routes.append((m.group(1).upper(), m.group(2), text[:m.start()].count("\n") + 1))
seen = defaultdict(list)
for method, path, line in routes:
    seen[(method, path)].append(line)
duplicates = {k: v for k, v in seen.items() if len(v) > 1}
if duplicates:
    for (method, path), lines in sorted(duplicates.items()):
        print(f"{method} {path} {lines}")
    raise SystemExit(1)
print(f"route_count={len(routes)}")
PY
cat /tmp/rn-route-check.txt
pass "no duplicate backend routes"

echo "10. Required pages"
test -f pages/war-room.html || fail "missing war-room.html"
test -f pages/resource-profile.html || fail "missing resource-profile.html"
test -f pages/recovery-reconstruction.html || fail "missing recovery-reconstruction.html"
test -f pages/mockup.html || fail "missing mockup.html"
test -f pages/program-khusus.html || fail "missing program-khusus.html"
test -f pages/ai-analyst.html || fail "missing ai-analyst.html"
test -f pages/sync-console.html || fail "missing sync-console.html"
pass "required pages"

echo ""
echo "OK: ALL SMOKE TESTS PASSED"
