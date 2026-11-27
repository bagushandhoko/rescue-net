#!/bin/sh
# Protokol Burst VPS P1 (Suri 2026-11-27): cadangan LENGKAP Rescue-Net tiap jam KELUAR laptop Flex.
# Flex CT201 node/cadangan.sh (DB + berkas + site_config/kunci enkripsi) -> HDD Aspire /var/lib/vz/rn-cadangan/<waktu>/
# (simulasi penyimpanan luar; nanti bisa R2/VPS). Dicek SHA256 di Aspire. Simpan 48 terakhir + 1/hari 14 hari.
# Cron CT102 tiap jam menit 17. Gagal -> lapor owner (maks 1x per 6 jam).
set -eu
FLEX=root@192.168.100.3; ASP=root@192.168.100.2; DST=/var/lib/vz/rn-cadangan
exec 9>/tmp/rn-cadangan.lock; flock -n 9 || exit 0
gagal() {
  f=/tmp/rn-cadangan.gagal
  if [ ! -f $f ] || [ $(( $(date +%s) - $(stat -c %Y $f) )) -gt 21600 ]; then
    touch $f; /root/bin/lapor-owner.sh Suri "Cadangan RN tiap jam GAGAL: $1. Dicoba lagi tiap jam." >/dev/null 2>&1 || true
  fi
  exit 1
}
OUT=$(ssh -o BatchMode=yes $FLEX "pct exec 201 -- sh -c 'cd /opt/rescue-net/node && ./cadangan.sh 2>&1 | tail -1'") || gagal "cadangan.sh di Flex"
TS=$(printf "%s" "$OUT" | sed -n 's#^Cadangan: backups/##p')
[ -n "$TS" ] || gagal "nama cadangan tidak terbaca ($OUT)"
ssh -o BatchMode=yes $FLEX "pct exec 201 -- tar -C /opt/rescue-net/node/backups -cf - $TS" \
  | ssh -o BatchMode=yes $ASP "mkdir -p $DST && chmod 700 $DST && tar -C $DST -xf - && cd $DST/$TS && sha256sum -c --quiet SHA256SUMS" \
  || gagal "salin/cek ke Aspire ($TS)"
ssh -o BatchMode=yes $FLEX "pct exec 201 -- rm -rf /opt/rescue-net/node/backups/$TS" || true
# rotasi: 48 terbaru + yang pertama tiap hari selama 14 hari
ssh -o BatchMode=yes $ASP "cd $DST && ls -1d 2*-* 2>/dev/null | sort > /tmp/rnc.all; tail -48 /tmp/rnc.all > /tmp/rnc.keep;
  for d in \$(seq 0 13); do h=\$(date -d \"-\$d day\" +%Y%m%d); grep \"^\$h-\" /tmp/rnc.all | head -1; done >> /tmp/rnc.keep;
  grep -vxF -f /tmp/rnc.keep /tmp/rnc.all | xargs -r rm -rf; ls -1d 2*-* | tail -1 > $DST/TERBARU"
rm -f /tmp/rn-cadangan.gagal
echo "ok $TS"
