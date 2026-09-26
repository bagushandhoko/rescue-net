#!/bin/sh
# Install the native wrapper (apps/rescue-net-shell) into the Android build
# folder, keeping a copy of what was there. Then run the Android build.
set -e
REPO=$(cd "$(dirname "$0")/.." && pwd)
APP=/volume1/web/rescue-net-build/app
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p /volume1/web/rescue-net-build/artifacts
tar czf /volume1/web/rescue-net-build/artifacts/app-before-shell-$TS.tgz -C "$APP" \
  --exclude=node_modules --exclude=android --exclude=ios . 2>/dev/null || true
rm -rf "$APP/src" "$APP/www"
cp -a "$REPO/apps/rescue-net-shell/." "$APP/"
echo "wrapper installed in $APP (previous app saved as artifacts/app-before-shell-$TS.tgz)"
echo "next: cd /volume1/web/rescue-net-build && sudo sh scripts/rn-build-android-sudo.sh"
