#!/bin/bash
# Pemantau rescue-net (2026-10-26; 2026-11-13: server PINDAH ke Flex 192.168.100.3 LXC 201).
# Dijalankan cron tiap 5 menit di CT105 (di LUAR Flex, supaya Flex mati total tetap terlapor).
# Log: /root/rn-monitor/monitor.log ; status terakhir: status.json
# Alarm: bila ada /root/rn-monitor/alert.sh (bisa dieksekusi), dipanggil dengan satu argumen pesan
# setiap kali status BERUBAH (rusak <-> pulih).
D=/root/rn-monitor; LOG=$D/monitor.log; ST=$D/status.json; PREV=$D/last-state
B=https://rescue-net.online
FLEX=${RN_FLEX:-root@192.168.100.3}; CT=${RN_CT:-201}
mkdir -p $D
now=$(date '+%F %T')
fail=()
check() {  # nama url kode-yang-diterima...
  local name=$1 url=$2; shift 2
  local out; out=$(curl -s -o /dev/null -A "rn-monitor/2" -m 20 -w "%{http_code} %{time_total}" "$url")
  local code=${out% *} t=${out#* }
  local ok=0; for c in "$@"; do [ "$code" = "$c" ] && ok=1; done
  [ "$ok" = 1 ] || fail+=("$name HTTP $code")
  awk -v t="$t" 'BEGIN{exit !(t>8)}' && fail+=("$name lambat ${t}s")
  echo "\"$name\":{\"code\":\"$code\",\"detik\":$t}"
}
r1=$(check beranda "$B/" 200 302)
r2=$(check api "$B/rescue-net-frappe/api/method/rescue_net.api_early_warning.banner" 200)
r3=$(check login "$B/rescue-net/pages/auth.html" 200)

# Flex: kontainer, backup harian, disk/RAM kontainer, listrik & baterai (baca saja)
fx=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$FLEX" "
  ac=\$(for p in /sys/class/power_supply/*; do [ \"\$(cat \$p/type 2>/dev/null)\" = Mains ] && cat \$p/online; done 2>/dev/null | head -1); bat=\$(cat /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1)
  pct exec $CT -- bash -c '
    cd /opt/rescue-net/node
    run=\$(docker compose --profile jobs ps --status running --format \"{{.Service}}\" 2>/dev/null | sort -u | tr \"\n\" \",\")
    a=\$(docker compose exec -T backend bash -c \"f=\\\$(ls -t sites/*/private/backups/*-database.sql.gz 2>/dev/null | head -1); [ -n \\\"\\\$f\\\" ] && echo \\\$(( (\\\$(date +%s) - \\\$(stat -c %Y \\\$f)) / 3600 )) || echo 999\" 2>/dev/null)
    d=\$(df --output=pcent / | tail -1 | tr -dc 0-9)
    m=\$(free | awk \"/Mem:/{printf \\\"%d\\\", \\\$3*100/\\\$2}\")
    echo \"\${a:-999} \$d \$m \$run\"
  ' 2>/dev/null | tr -d '\r' | tail -1 | sed \"s/\$/ \${ac:-?} \${bat:-?}/\"
" 2>/dev/null)
if [ -z "$fx" ]; then
  fail+=("Flex tidak terjangkau (mati / jaringan putus?)"); bk=-1; disk=-1; mem=-1; ac="?"; bat="?"
else
  read -r bk disk mem run ac bat <<< "$fx"
  for s in backend mariadb redis-cache redis-queue web scheduler worker; do
    case ",$run" in *",$s,"*) ;; *) fail+=("kontainer $s mati");; esac
  done
  [ "${bk:-999}" -gt 26 ] && fail+=("backup terakhir ${bk} jam lalu")
  [ "${disk:-0}" -gt 85 ] && fail+=("disk Flex ${disk}%")
  [ "${mem:-0}" -gt 92 ] && fail+=("RAM kontainer ${mem}%")
  [ "$ac" = "0" ] && fail+=("Flex pakai BATERAI (listrik padam?) ${bat}%")
fi
# kejadian penjaga otomatis Flex (rn-autoscale): kabarkan sekali per kejadian baru
evl=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$FLEX" "tail -1 /var/lib/rn-autoscale/events.log 2>/dev/null" 2>/dev/null)
if [ -n "$evl" ] && [ "$evl" != "$(cat $D/last-autoscale 2>/dev/null)" ]; then
  echo "$evl" > $D/last-autoscale
  [ -x $D/alert.sh ] && $D/alert.sh "Flex otomatis: $evl"
fi
state=OK; [ ${#fail[@]} -gt 0 ] && state="MASALAH: $(IFS='; '; echo "${fail[*]}")"
echo "{\"waktu\":\"$now\",\"status\":\"${state//\"/}\",$r1,$r2,$r3,\"backup_jam\":${bk:--1},\"disk_persen\":${disk:--1},\"ram_persen\":${mem:--1},\"listrik\":\"${ac}\",\"baterai\":\"${bat}\"}" > $ST
echo "$now $state" >> $LOG
tail -n 5000 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
last=$(cat $PREV 2>/dev/null)
if [ "$state" != "$last" ]; then
  echo "$state" > $PREV
  if [ -x $D/alert.sh ]; then
    if [ "$state" = OK ]; then $D/alert.sh "rescue-net PULIH ($now)"; else $D/alert.sh "rescue-net $state ($now)"; fi
  fi
fi
