#!/bin/sh
# Pasang perubahan nginx RN di Flex TANPA mematikan situs (owner 24 Nov 2026: disiplin operasional).
# 24 Nov siang: template salah langsung dipasang + kontainer web dibuat ulang -> web restart-loop, situs mati ~30 dtk.
# Alur (scripts/flex-nginx/inner.sh): uji template baru di kontainer nginx SEMENTARA (image/env/volume/jaringan sama)
# dengan `nginx -t`; bila lulus: cadangkan, salin, render ulang + `nginx -s reload` (tanpa putus); gagal -> kembalikan.
#   scripts/flex-nginx-apply.sh --check   -> hanya uji, situs tidak disentuh
#   scripts/flex-nginx-apply.sh           -> uji lalu pasang (izin owner per deploy)
# Catatan: perubahan docker-compose.yml (volume/port) tetap butuh `docker compose up -d web` (putus singkat).
set -eu
FLEX="${RN_FLEX:-root@192.168.100.3}"; CT="${RN_CT:-201}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; MODE=apply; [ "${1:-}" = "--check" ] && MODE=check
cd "$ROOT"
[ $MODE = check ] || [ -z "$(git status --porcelain node/nginx scripts/flex-nginx)" ] || { echo "node/nginx belum di-commit." >&2; exit 1; }
tar -cf - -C node nginx -C ../scripts/flex-nginx inner.sh | ssh "$FLEX" \
  "pct exec $CT -- sh -c 'rm -rf /tmp/rn-nginx-new && mkdir -p /tmp/rn-nginx-new && tar -C /tmp/rn-nginx-new -xf - && sh /tmp/rn-nginx-new/inner.sh $MODE $(date +%Y%m%d-%H%M%S)'"
