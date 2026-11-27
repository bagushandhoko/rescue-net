#!/bin/sh
# Agen tombol "Burst ke VPS" (Protokol Burst VPS, Suri 2026-11-27). Cron CT102 tiap menit.
# Mengambil permintaan dari RN (api_burst.agent_next, token /root/.rn-burst-token = site_config burst_agent_token),
# menjalankan rn-burst.sh, dan mengirim kemajuan ke halaman RN (agent_update) tiap 15 detik.
set -eu
API="https://rescue-net.online/rescue-net-frappe/api/method/rescue_net.api_burst"
TOK=/root/.rn-burst-token
exec 9>/tmp/rn-burst-agent.lock; flock -n 9 || exit 0
[ -s $TOK ] || exit 0
J=$(curl -fsS --max-time 30 -X POST --data-urlencode "token@$TOK" "$API.agent_next") || exit 0
W=$(mktemp -d /tmp/rn-burst.XXXXXX); chmod 700 "$W"
printf "%s" "$J" | python3 -c '
import json,sys,os
j=json.load(sys.stdin)["message"]["job"]
if not j: sys.exit(3)
d=sys.argv[1]
open(d+"/job","w").write("%s %s %s %s\n" % (j["name"], j["mode"], j["ip"], j["ssh_user"]))
fd=os.open(d+"/pw", os.O_WRONLY|os.O_CREAT, 0o600); os.write(fd, j["login_code"].encode()); os.close(fd)
' "$W" || { rm -rf "$W"; exit 0; }
read NAME MODE IP USR < "$W/job"
kirim() {  # $1 status, isi log baru sejak kiriman terakhir
  N=$(wc -c < "$W/log" 2>/dev/null || echo 0); S=$(cat "$W/sent" 2>/dev/null || echo 0)
  tail -c +$((S + 1)) "$W/log" 2>/dev/null | head -c $((N - S)) > "$W/baru" || true
  curl -fsS --max-time 30 -o /dev/null -X POST --data-urlencode "token@$TOK" --data-urlencode "name=$NAME" \
    --data-urlencode "status=$1" --data-urlencode "log@$W/baru" "$API.agent_update" && echo "$N" > "$W/sent" || true
}
/root/bin/lapor-owner.sh Suri "Burst VPS dimulai: mode $MODE ke $IP (permintaan dari tombol RN)." >/dev/null 2>&1 || true
: > "$W/log"
( while [ ! -f "$W/done" ]; do sleep 15; kirim Berjalan; done ) &
if /root/bin/rn-burst.sh --ip "$IP" --user "$USR" --sandi-berkas "$W/pw" --mode "$MODE" --log "$W/log" >> "$W/log.out" 2>&1; then ST=Selesai; else ST=Gagal; fi
rm -f "$W/pw"; touch "$W/done"; sleep 1; kirim $ST
cp "$W/log" "/root/rn-burst-$NAME.log"; rm -rf "$W"
