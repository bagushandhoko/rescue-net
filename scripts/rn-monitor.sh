#!/bin/bash
# Pemantau rescue-net (2026-10-26). Dijalankan cron tiap 5 menit di CT102.
# Log: /root/rn-monitor/monitor.log ; status terakhir: status.json
# Alarm: bila ada /root/rn-monitor/alert.sh (bisa dieksekusi), dipanggil dengan
# satu argumen pesan setiap kali status BERUBAH (rusak <-> pulih).
D=/root/rn-monitor; LOG=$D/monitor.log; ST=$D/status.json; PREV=$D/last-state
B=https://rescue-net.online
now=$(date '+%F %T')
fail=()
check() {  # nama url kode-yang-diterima...
  local name=$1 url=$2; shift 2
  local out; out=$(curl -s -o /dev/null -A "rn-monitor/1" -m 20 -w "%{http_code} %{time_total}" "$url")
  local code=${out% *} t=${out#* }
  local ok=0; for c in "$@"; do [ "$code" = "$c" ] && ok=1; done
  [ "$ok" = 1 ] || fail+=("$name HTTP $code")
  awk -v t="$t" 'BEGIN{exit !(t>8)}' && fail+=("$name lambat ${t}s")
  echo "\"$name\":{\"code\":\"$code\",\"detik\":$t}"
}
r1=$(check beranda "$B/" 200 302)
r2=$(check api "$B/rescue-net-frappe/api/method/rescue_net.api_early_warning.banner" 200)
r3=$(check login "$B/rescue-net/pages/auth.html" 200)
# backup harian & disk di VM (baca saja)
vm=$(ssh -o BatchMode=yes -o ConnectTimeout=10 debian@192.168.100.51 \
  'a=$(docker exec osiun-frappe-backend bash -c "f=\$(ls -t sites/osiun.localhost/private/backups/*-database.sql.gz | head -1); echo \$(( (\$(date +%s) - \$(stat -c %Y \$f)) / 3600 ))" 2>/dev/null); d=$(df --output=pcent / | tail -1 | tr -dc 0-9); echo "${a:-999} $d"' 2>/dev/null)
bk=${vm% *}; disk=${vm#* }
if [ -z "$vm" ]; then fail+=("VM tidak terjangkau lewat SSH"); bk=-1; disk=-1
else
  [ "$bk" -gt 26 ] && fail+=("backup terakhir ${bk} jam lalu")
  [ "$disk" -gt 85 ] && fail+=("disk VM ${disk}%")
fi
state=OK; [ ${#fail[@]} -gt 0 ] && state="MASALAH: $(IFS='; '; echo "${fail[*]}")"
echo "{\"waktu\":\"$now\",\"status\":\"${state//\"/}\",$r1,$r2,$r3,\"backup_jam\":$bk,\"disk_persen\":$disk}" > $ST
echo "$now $state" >> $LOG
tail -n 5000 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
last=$(cat $PREV 2>/dev/null)
if [ "$state" != "$last" ]; then
  echo "$state" > $PREV
  if [ -x $D/alert.sh ]; then
    if [ "$state" = OK ]; then $D/alert.sh "rescue-net PULIH ($now)"; else $D/alert.sh "rescue-net $state ($now)"; fi
  fi
fi
