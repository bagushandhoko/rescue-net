#!/bin/sh
# Deploy rescue-net ke VM Aspire (sac-vm). Jalankan dari clone repo di LXC claude-admin.
#   scripts/deploy-vm.sh            -> sinkron statis + backend, restart bila backend berubah
#   scripts/deploy-vm.sh --dry-run  -> hanya tampilkan perubahan
# Tanpa --delete: berkas yang hanya ada di VM tidak pernah dihapus.
set -eu
VM="${RN_VM:-debian@192.168.100.51}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=""; [ "${1:-}" = "--dry-run" ] && DRY="-n"

cd "$ROOT"
[ -z "$(git status --porcelain)" ] || { echo "Working tree kotor - commit dulu." >&2; exit 1; }

echo "== statis -> /srv/rescue-net/repo"
rsync -rlci $DRY --exclude='.git' \
  pages assets index.html manifest.webmanifest sw.js "$VM:/srv/rescue-net/repo/"

echo "== backend -> /srv/rescue-net/apps/rescue_net"
OUT=$(rsync -rlci $DRY --exclude='__pycache__' --exclude='*.pyc' --exclude=tests \
  frappe_shadow/apps/rescue_net/ "$VM:/srv/rescue-net/apps/rescue_net/")
echo "$OUT"
[ -n "$DRY" ] && exit 0

if echo "$OUT" | grep -q '^<f'; then
  echo "== backend berubah -> restart backend/worker/scheduler"
  ssh "$VM" 'cd /srv/rescue-net && docker compose restart backend worker-default scheduler'
else
  echo "== backend tidak berubah, tanpa restart"
fi
echo "Selesai. Commit: $(git rev-parse --short HEAD)"
