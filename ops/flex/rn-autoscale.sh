#!/bin/bash
# Penjaga otomatis Flex (owner 2026-11-14): saat Rescue-Net ramai -> Home Assistant dimatikan rapi + RAM RN dinaikkan;
# saat sepi lagi -> RAM RN normal + HA dinyalakan. Dijalankan rn-autoscale.timer tiap 1 menit.
# Saklar: echo ha-on > /etc/rn-autoscale.hold (HA jangan pernah dimatikan) | echo ha-off (HA tetap mati) | rm (otomatis)
# Log: /var/lib/rn-autoscale/events.log (dibaca pemantau CT105 -> Telegram). Status: /var/lib/rn-autoscale/state
set -u
CONF=/etc/rn-autoscale.conf; [ -f $CONF ] && . $CONF
HA_VMID=${HA_VMID:-100}; RN_CT=${RN_CT:-201}
MEM_NORMAL=${MEM_NORMAL:-5120}; MEM_BUSY=${MEM_BUSY:-6656}
CPU_BUSY=${CPU_BUSY:-70}; MEMPCT_BUSY=${MEMPCT_BUSY:-80}; REQ_BUSY=${REQ_BUSY:-20000}; P95_BUSY=${P95_BUSY:-1.0}
CPU_CALM=${CPU_CALM:-40}; MEMPCT_CALM=${MEMPCT_CALM:-65}; REQ_CALM=${REQ_CALM:-5000}; P95_CALM=${P95_CALM:-0.5}
BUSY_MIN=${BUSY_MIN:-3}; CALM_MIN=${CALM_MIN:-30}; GAP_MIN=${GAP_MIN:-30}
D=/var/lib/rn-autoscale; mkdir -p $D; ST=$D/state; EV=$D/events.log
mode=normal; busy=0; calm=0; last=0
[ -f $ST ] && . $ST
now=$(date +%s); ts=$(date '+%F %T')
ev() { echo "$ts $*" >> $EV; tail -n 500 $EV > $EV.tmp && mv $EV.tmp $EV; }

# --- indikator ---
read -r _ a1 b1 c1 d1 e1 f1 g1 _ < /proc/stat; sleep 5; read -r _ a2 b2 c2 d2 e2 f2 g2 _ < /proc/stat
tot=$(( (a2+b2+c2+d2+e2+f2+g2) - (a1+b1+c1+d1+e1+f1+g1) )); idle=$(( (d2+e2) - (d1+e1) ))
cpu=$(( tot > 0 ? 100 * (tot - idle) / tot : 0 ))
cg=/sys/fs/cgroup/lxc/$RN_CT
memcur=$(cat $cg/memory.current 2>/dev/null || echo 0); memmax=$(cat $cg/memory.max 2>/dev/null || echo 0)
# memory.current termasuk cache berkas; pakai anon (proses nyata) untuk keputusan
anon=$(awk '/^anon /{print $2}' $cg/memory.stat 2>/dev/null || echo 0)
[ "$memmax" = "max" ] && memmax=$((MEM_NORMAL*1048576))
mempct=$(( memmax > 0 ? 100 * anon / memmax : 0 ))
req=$(pct exec $RN_CT -- docker logs --since 60s rescuenet-web-1 2>/dev/null | wc -l)
p95=$(for i in 1 2 3; do curl -s -o /dev/null -m 10 -w '%{time_total}\n' "http://10.255.255.20:8182/rescue-net-frappe/api/method/rescue_net.api_auth.account_status"; done | sort -n | tail -1)
p95=${p95:-9}
gt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>b)}'; }
lt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a<b)}'; }

hot=0; gt $cpu $CPU_BUSY && hot=1; gt $mempct $MEMPCT_BUSY && hot=1; gt $req $REQ_BUSY && hot=1; gt $p95 $P95_BUSY && hot=1
cool=1; lt $cpu $CPU_CALM || cool=0; lt $mempct $MEMPCT_CALM || cool=0; lt $req $REQ_CALM || cool=0; lt $p95 $P95_CALM || cool=0
[ $hot = 1 ] && busy=$((busy+1)) || busy=0
[ $cool = 1 ] && calm=$((calm+1)) || calm=0
hold=$(cat /etc/rn-autoscale.hold 2>/dev/null | tr -d '[:space:]')
ha_exists=0; qm status $HA_VMID >/dev/null 2>&1 && ha_exists=1
gap_ok=1; [ $(( (now - last) / 60 )) -lt $GAP_MIN ] && gap_ok=0
info="cpu=${cpu}% ramRN=${mempct}% req/mnt=${req} jawab=${p95}s"

if [ "$mode" = normal ] && [ $busy -ge $BUSY_MIN ] && [ $gap_ok = 1 ]; then
  pct set $RN_CT -memory $MEM_BUSY && ev "RAMAI ($info): RAM Rescue-Net dinaikkan ke ${MEM_BUSY} MB"
  if [ $ha_exists = 1 ] && [ "$hold" != "ha-on" ] && qm status $HA_VMID | grep -q running; then
    (qm shutdown $HA_VMID --timeout 180 >/dev/null 2>&1 || qm stop $HA_VMID >/dev/null 2>&1) &
    ev "RAMAI: Home Assistant (VM $HA_VMID) dimatikan sementara"
  fi
  mode=busy; last=$now; busy=0; calm=0
elif [ "$mode" = busy ] && [ $calm -ge $CALM_MIN ] && [ $gap_ok = 1 ]; then
  pct set $RN_CT -memory $MEM_NORMAL && ev "SEPI ($info): RAM Rescue-Net kembali ${MEM_NORMAL} MB"
  if [ $ha_exists = 1 ] && [ "$hold" != "ha-off" ] && ! qm status $HA_VMID | grep -q running; then
    qm start $HA_VMID >/dev/null 2>&1 && ev "SEPI: Home Assistant (VM $HA_VMID) dinyalakan lagi"
  fi
  mode=normal; last=$now; busy=0; calm=0
fi
printf 'mode=%s\nbusy=%s\ncalm=%s\nlast=%s\n' "$mode" "$busy" "$calm" "$last" > $ST
echo "$ts mode=$mode $info busy=$busy calm=$calm hold=${hold:-otomatis}" > $D/terakhir
