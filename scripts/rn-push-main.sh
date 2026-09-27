#!/bin/sh
# Owner push: commit everything in the working tree and push to GitHub `main`.
# `main` is the only branch (the old `dev` branch was removed 2026-09-26).
# Push goes over SSH via remote.origin.pushurl (deploy key alias
# `github-rescue-net`); the old GITHUB_TOKEN in osiun-deploy.env expired.
set -eu

cd /volume1/web/rescue-net

echo "=== Rescue-Net Owner Push to MAIN ==="

git checkout main
git fetch origin main

HAS_CHANGES=0
if ! git diff --quiet || ! git diff --cached --quiet; then
  HAS_CHANGES=1
fi

AHEAD_COUNT="$(git rev-list --count origin/main..HEAD 2>/dev/null || printf "0")"

if [ "$HAS_CHANGES" -eq 0 ] && [ "$AHEAD_COUNT" -eq 0 ]; then
  echo "No changes or local commits to push."
  exit 0
fi

if [ -z "$(git config --get remote.origin.pushurl || true)" ]; then
  echo "ERROR: remote.origin.pushurl not set (expected git@github-rescue-net:bagushandhoko/rescue-net.git)."
  exit 1
fi

git config user.name "bagushandhoko"
git config user.email "bagushandhoko@users.noreply.github.com"

if grep -RInE "sk-[A-Za-z0-9_-]{20,}|rescuenet_dev_password|POSTGRES_PASSWORD=[^[:space:]]+|postgresql://[^:]+:[^@]+@" . \
  --exclude-dir="@eaDir" \
  --exclude-dir=".git" \
  --exclude="*.bak*" \
  --exclude="*.zip" \
  --exclude=".env" \
  --exclude="*.png" \
  --exclude="*.jpg" \
  --exclude="*.jpeg" \
  --exclude="*.webp" \
  --exclude="rn-push*.sh" \
  | head -5 | grep .; then
  echo "ERROR: possible secret found. Push cancelled."
  exit 1
fi

if [ "$HAS_CHANGES" -eq 1 ]; then
  git add .
  git commit -m "Owner update Rescue-Net $(date '+%Y-%m-%d %H:%M:%S')"
fi

git push origin main

echo "OK: pushed to GitHub main."
