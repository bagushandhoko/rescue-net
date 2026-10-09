#!/bin/sh
# Ekspor SEMUA yang dibangun (Rescue-Net + SAC) dari NAS menjadi satu bundel untuk server baru.
#   sh ops/proxmox/export-from-nas.sh            # buat bundel di /volume1/migrasi/bundle-<waktu>
#   sh ops/proxmox/export-from-nas.sh --dry-run  # hanya tunjukkan apa yang akan dilakukan (tidak menulis apa pun)
# Tidak menyentuh OSIUN selain membaca situs Rescue-Net (osiun.localhost) lewat `bench backup`.
# Bundel memuat RAHASIA (secrets/): simpan terenkripsi, jangan diunggah ke GitHub/cloud publik.
set -eu
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
D="sudo docker"
TS=$(date +%Y%m%d-%H%M%S)
OUT=${BUNDLE_ROOT:-/volume1/migrasi}/bundle-$TS
RN_C=osiun-frappe-backend;  RN_SITE=osiun.localhost
SAC_C=sac-frappe-backend;   SAC_SITE=sac.localhost
B=/home/frappe/frappe-bench
RN_DIR=/volume1/web/rescue-net
SAC_APP_DIR=/volume1/docker/sac-frappe
SAC_WEB_DIR=/volume1/web/sac

say() { printf '== %s\n' "$*"; }
run() { if [ $DRY -eq 1 ]; then printf '   [dry-run] %s\n' "$*"; else "$@"; fi; }

say "0. pemeriksaan awal"
for c in $RN_C $SAC_C; do $D inspect -f '{{.State.Running}}' $c >/dev/null 2>&1 || { echo "kontainer $c tidak berjalan"; exit 1; }; done
for r in $RN_DIR $SAC_APP_DIR $SAC_WEB_DIR; do
  [ -d "$r/.git" ] || { echo "$r bukan repo git"; exit 1; }
  dirty=$(cd "$r" && git status --porcelain | wc -l)
  [ "$dirty" -eq 0 ] || echo "   PERINGATAN: $r punya $dirty berkas belum di-commit (tidak ikut git bundle; commit dulu)"
done
[ $DRY -eq 1 ] || { mkdir -p "$OUT"/db "$OUT"/git "$OUT"/infra "$OUT"/secrets "$OUT"/static; chmod 700 "$OUT" "$OUT"/secrets; }
say "bundel: $OUT"

backup_site() { # kontainer situs awalan
  c=$1; site=$2; pre=$3
  say "1. backup situs $site (DB + berkas publik/privat)"
  run $D exec "$c" sh -c "cd $B && bench --site $site backup --with-files | tail -6"
  if [ $DRY -eq 0 ]; then
    for suffix in database.sql.gz files.tar private-files.tar site_config_backup.json; do
      f=$($D exec "$c" sh -c "ls -t $B/sites/$site/private/backups/*$suffix 2>/dev/null | head -1")
      [ -n "$f" ] || { echo "backup $suffix tidak ditemukan untuk $site"; exit 1; }
      $D cp "$c:$f" "$OUT/db/$pre-$(basename "$f")"
    done
    $D cp "$c:$B/sites/$site/site_config.json" "$OUT/secrets/$pre-site_config.json"   # memuat encryption_key + db_password
    $D cp "$c:$B/sites/common_site_config.json" "$OUT/infra/$pre-common_site_config.json"
    $D exec "$c" sh -c "cat $B/sites/apps.txt" > "$OUT/infra/$pre-apps.txt"
    $D exec "$c" sh -c "cd $B && bench --site $site list-apps" > "$OUT/infra/$pre-list-apps.txt" 2>&1 || true
  fi
}
backup_site $RN_C  $RN_SITE  rn
backup_site $SAC_C $SAC_SITE sac

say "2. kode sumber (git bundle: seluruh riwayat)"
run sh -c "cd $RN_DIR && git bundle create $OUT/git/rescue-net.bundle --all"
run sh -c "cd $SAC_APP_DIR && git bundle create $OUT/git/sac-frappe.bundle --all"
run sh -c "cd $SAC_WEB_DIR && git bundle create $OUT/git/sac-web.bundle --all"

say "3. berkas statis hasil build + konfigurasi infrastruktur"
run sh -c "[ -d /volume1/web/rescue-net-app ] && tar czf $OUT/static/rescue-net-app.tgz -C /volume1/web rescue-net-app || true"
run cp /volume1/docker/rescue-web/default.conf   "$OUT/infra/rescue-web.default.conf"
run cp /volume1/docker/rescue-web/rn-proxy.conf  "$OUT/infra/rn-proxy.conf"
run cp /volume1/docker/sac-web/default.conf      "$OUT/infra/sac-web.default.conf"
run cp /volume1/docker/osiun-frappe-shadow/docker-compose.yml "$OUT/infra/osiun-frappe-shadow.compose.yml"

say "4. rahasia (chmod 600): .env SAC, kredensial, token tunnel"
if [ $DRY -eq 0 ]; then
  [ -f $SAC_APP_DIR/.env ]  && cp $SAC_APP_DIR/.env  "$OUT/secrets/sac.env"
  [ -f $SAC_APP_DIR/.cred ] && cp $SAC_APP_DIR/.cred "$OUT/secrets/sac.cred"
  $D inspect cloudflared --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^TUNNEL_TOKEN=' > "$OUT/secrets/cloudflared.env" || echo "   catatan: TUNNEL_TOKEN tidak ada di env kontainer cloudflared; ambil dari dashboard Cloudflare"
  grep -E 'MYSQL_ROOT_PASSWORD' /volume1/docker/osiun-frappe-shadow/docker-compose.yml | sed 's/^ *//' > "$OUT/secrets/rn-db-root.env" || true
  chmod 600 "$OUT"/secrets/* 2>/dev/null || true
fi

say "5. manifes + checksum"
if [ $DRY -eq 0 ]; then
  { echo "bundle $TS"; echo "git rescue-net: $(cd $RN_DIR && git rev-parse --short HEAD)"; echo "git sac-frappe: $(cd $SAC_APP_DIR && git rev-parse --short HEAD)"; echo "git sac-web: $(cd $SAC_WEB_DIR && git rev-parse --short HEAD)"; } > "$OUT/MANIFEST.txt"
  (cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | xargs -0 sha256sum > SHA256SUMS)
  du -sh "$OUT"; ls -R "$OUT" | head -40
fi
say "selesai. Salin bundel ke server baru (scp/rsync), lalu jalankan import-on-new-host.sh."
