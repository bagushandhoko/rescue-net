#!/bin/sh
set -eu

cd /volume1/web/rescue-net

echo "=== Rescue-Net Contributor Push to DEV ==="

GITHUB_TOKEN="$(sudo sh -c '. /volume1/docker/osiun-deploy/osiun-deploy.env; printf "%s" "$GITHUB_TOKEN"')"

if [ -z "$GITHUB_TOKEN" ]; then
  echo "ERROR: GITHUB_TOKEN not found."
  exit 1
fi

git checkout dev

if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to push."
  exit 0
fi

git config user.name "bagushandhoko"
git config user.email "bagushandhoko@users.noreply.github.com"

git add .
git commit -m "Dev update Rescue-Net $(date '+%Y-%m-%d %H:%M:%S')"

git remote set-url origin "https://${GITHUB_TOKEN}@github.com/bagushandhoko/rescue-net.git"
git push origin dev
git remote set-url origin "https://github.com/bagushandhoko/rescue-net.git"

echo "OK: pushed to GitHub dev."
