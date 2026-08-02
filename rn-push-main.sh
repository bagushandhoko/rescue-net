#!/bin/sh
set -eu

cd /volume1/web/rescue-net

echo "=== Rescue-Net Owner Push to MAIN ==="

GITHUB_TOKEN="$(sudo sh -c '. /volume1/docker/osiun-deploy/osiun-deploy.env; printf "%s" "$GITHUB_TOKEN"')"

if [ -z "$GITHUB_TOKEN" ]; then
  echo "ERROR: GITHUB_TOKEN not found."
  exit 1
fi

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

git remote set-url origin "https://github.com/bagushandhoko/rescue-net.git"

export GITHUB_TOKEN

git -c 'credential.helper=!f() {
  if [ "$1" = "get" ]; then
    printf "%s\n" "username=x-access-token"
    printf "%s\n" "password=$GITHUB_TOKEN"
  fi
}; f' push origin main
git remote set-url origin "https://github.com/bagushandhoko/rescue-net.git"

echo "OK: pushed to GitHub main."
