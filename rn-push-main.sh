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

if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to push."
  exit 0
fi

git config user.name "bagushandhoko"
git config user.email "bagushandhoko@users.noreply.github.com"

if grep -RIn "sk-\|rescuenet_dev_password\|POSTGRES_PASSWORD" . \
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

git add .
git commit -m "Owner update Rescue-Net $(date '+%Y-%m-%d %H:%M:%S')"

git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bagushandhoko/rescue-net.git"
git push origin main
git remote set-url origin "https://github.com/bagushandhoko/rescue-net.git"

echo "OK: pushed to GitHub main."
