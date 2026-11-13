#!/bin/sh
# Deploy rescue-net ke server Flex (Proxmox pve-flex5, LXC 201; sejak 2026-11-13 menggantikan VM Aspire).
# Jalankan dari clone repo yang bersih, dari mesin yang punya kunci SSH root ke Flex.
#   scripts/deploy-flex.sh             -> sinkron statis + backend; bila backend berubah: restart + clear-cache
#   scripts/deploy-flex.sh --migrate   -> sama, ditambah bench migrate (doctype/field baru). Backup DB dulu!
#   scripts/deploy-flex.sh --dry-run   -> hanya tampilkan perubahan
# Tanpa --delete: berkas yang hanya ada di server tidak pernah dihapus.
set -eu
FLEX="${RN_FLEX:-root@192.168.100.3}"; CT="${RN_CT:-201}"; SITE="${RN_SITE:-osiun.localhost}"
STAGE=/root/rn-stage
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-}"; DRY=""; [ "$MODE" = "--dry-run" ] && DRY="-n"
cd "$ROOT"
[ -z "$(git status --porcelain)" ] || { echo "Working tree kotor - commit dulu." >&2; exit 1; }

ssh "$FLEX" "mkdir -p $STAGE/app"
echo "== statis"
S=$(rsync -rlci $DRY --exclude='.git' pages assets index.html manifest.webmanifest sw.js "$FLEX:$STAGE/")
echo "$S" | grep '^<f' | head -40 || true
echo "== backend"
OUT=$(rsync -rlci $DRY --exclude='__pycache__' --exclude='*.pyc' --exclude=tests \
  frappe_shadow/apps/rescue_net/ "$FLEX:$STAGE/app/")
echo "$OUT" | grep '^<f' | head -40 || true
[ -n "$DRY" ] && exit 0

# salin ke dalam kontainer lewat pct exec (pemilik berkas = root kontainer, bukan root host)
ssh "$FLEX" "cd $STAGE && tar -cf - --exclude=./app . | pct exec $CT -- tar -C /opt/rescue-net -xf - && \
  tar -C $STAGE/app -cf - . | pct exec $CT -- tar -C /opt/rescue-net/frappe_shadow/apps/rescue_net -xf -"

if echo "$OUT" | grep -q '^<f' || [ "$MODE" = "--migrate" ]; then
  MIG=""; [ "$MODE" = "--migrate" ] && MIG="docker compose exec -T backend bench --site $SITE migrate &&"
  echo "== backend berubah -> restart backend/worker/scheduler + clear-cache"
  ssh "$FLEX" "pct exec $CT -- bash -lc 'cd /opt/rescue-net/node && $MIG \
    docker compose --profile jobs restart backend worker scheduler >/dev/null && \
    for i in \$(seq 1 40); do c=\$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8182/rescue-net-frappe/api/method/rescue_net.api_auth.account_status); [ \$c = 200 ] && break; sleep 3; done; \
    docker compose exec -T backend bench --site $SITE clear-cache && echo backend=\$c'"
else
  echo "== backend tidak berubah, tanpa restart"
fi
echo "Selesai. Commit: $(git rev-parse --short HEAD) -> Flex LXC $CT"
