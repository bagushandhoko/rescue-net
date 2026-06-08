#!/bin/sh
set -eu

cd /volume1/web/rescue-net

echo "=== Rescue-Net Git Auto Push ==="

# Load token dari OSIUN deploy env tanpa print token
GITHUB_TOKEN="$(sudo sh -c '. /volume1/docker/osiun-deploy/osiun-deploy.env; printf "%s" "$GITHUB_TOKEN"')"

if [ -z "$GITHUB_TOKEN" ]; then
  echo "ERROR: GITHUB_TOKEN not found."
  exit 1
fi

# Pastikan di branch dev
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || echo '')"
if [ "$CURRENT_BRANCH" != "dev" ]; then
  git checkout dev
fi

# Jangan push kalau tidak ada perubahan
if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to push."
  exit 0
fi

# Set identity
git config user.name "bagushandhoko"
git config user.email "bagushandhoko@users.noreply.github.com"

# Cek secret sederhana sebelum push
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
git commit -m "Update Rescue-Net $(date '+%Y-%m-%d %H:%M:%S')"

git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bagushandhoko/rescue-net.git"
git push origin dev
git remote set-url origin "https://github.com/bagushandhoko/rescue-net.git"

echo "OK: pushed to GitHub dev."
