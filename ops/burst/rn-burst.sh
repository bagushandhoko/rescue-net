#!/bin/sh
# Protokol Burst VPS Rescue-Net (docs/PROTOKOL-BURST-VPS.md) — Suri 2026-11-27.
# Membangun Rescue-Net LENGKAP di VPS kosong dari IP + kode login, memakai paket node/ (pasang.sh --pulihkan).
#
#   rn-burst.sh --ip <IP> --sandi-berkas <file> [--user root] --mode gladi|siaga|pindah|darurat [--log <file>]
#     gladi   : uji di VPS simulasi. Cadangan terbaru (HDD Aspire), TANPA jobs & TANPA tunnel. Produksi tidak disentuh.
#     siaga   : sama dengan gladi di VPS sungguhan (siap dipakai, belum menerima lalu lintas).
#     pindah  : Flex mode pemeliharaan -> cadangan final -> pulihkan + jobs -> alihkan Cloudflare -> Flex jobs mati.
#     darurat : Flex mati: cadangan otomatis terakhir (HDD Aspire) -> pulihkan + jobs -> alihkan Cloudflare.
# Dijalankan di CT102 (punya akses Flex, Aspire, Edith). Kode login VPS dipakai SEKALI untuk memasang kunci agen.
set -eu
IP=""; USR=root; PW=""; MODE=""; LOG=/dev/null
while [ $# -gt 0 ]; do case "$1" in
  --ip) IP="$2"; shift 2;; --user) USR="$2"; shift 2;; --sandi-berkas) PW="$2"; shift 2;;
  --mode) MODE="$2"; shift 2;; --log) LOG="$2"; shift 2;; *) echo "opsi tidak dikenal: $1" >&2; exit 2;; esac; done
case "$MODE" in gladi|siaga|pindah|darurat) ;; *) echo "--mode gladi|siaga|pindah|darurat" >&2; exit 2;; esac
[ -n "$IP" ] || { echo "--ip wajib" >&2; exit 2; }
FLEX=root@192.168.100.3; ASP=root@192.168.100.2; CADANGAN=/var/lib/vz/rn-cadangan
KEY=/root/.ssh/rn-burst_ed25519; T0=$(date +%s)
[ -f $KEY ] || ssh-keygen -q -t ed25519 -N "" -C rn-burst-agent -f $KEY
SSHO="-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/root/.ssh/rn-burst_known -o ConnectTimeout=15"
V() { ssh $SSHO -o BatchMode=yes -i $KEY "$USR@$IP" "$@"; }
langkah() { m="[$(( $(date +%s) - T0 ))s] $*"; echo "$m"; echo "$m" >> "$LOG"; }
lapor() { /root/bin/lapor-owner.sh Suri "Burst VPS ($MODE, $IP): $*" >/dev/null 2>&1 || true; }
gagal() { langkah "GAGAL: $*"; lapor "GAGAL di langkah: $*"; exit 1; }
trap 'gagal "terhenti tak terduga"' INT TERM

langkah "1. masuk VPS & pasang kunci agen"
if ! V true 2>/dev/null; then
  [ -n "$PW" ] && [ -f "$PW" ] || gagal "kode login (berkas sandi) tidak ada"
  sshpass -f "$PW" ssh $SSHO -o PreferredAuthentications=password -o PubkeyAuthentication=no "$USR@$IP" \
    "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys" < $KEY.pub || gagal "login dengan kode login ditolak"
fi
V true || gagal "kunci agen tidak bisa dipakai"
if [ "$MODE" != gladi ]; then   # VPS sungguhan: matikan login sandi setelah kunci terpasang
  V "sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && rm -f /etc/ssh/sshd_config.d/*pwauth* && systemctl reload ssh || true"
fi

langkah "2. cek VPS"
INFO=$(V 'echo "$(nproc) $(awk "/MemTotal/{print int(\$2/1024)}" /proc/meminfo) $(df -Pm / | awk "NR==2{print \$4}") $(. /etc/os-release; echo $ID$VERSION_ID)"')
set -- $INFO; CPU=$1; RAM=$2; DISK=$3; OS=$4
langkah "   CPU=$CPU RAM=${RAM}MB disk_bebas=${DISK}MB os=$OS"
[ "$CPU" -ge 2 ] && [ "$RAM" -ge 2800 ] && [ "$DISK" -ge 15000 ] || gagal "VPS terlalu kecil (min 2 CPU, 3 GB, 15 GB bebas)"

langkah "3. pasang Docker & alat"
V 'export DEBIAN_FRONTEND=noninteractive; command -v docker >/dev/null && docker compose version >/dev/null 2>&1 && exit 0
   apt-get update -qq && apt-get install -y -qq ca-certificates curl rsync >/dev/null &&
   (apt-get install -y -qq docker.io docker-compose >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 ||
    (curl -fsSL https://get.docker.com | sh >/dev/null)) && systemctl enable --now docker >/dev/null' || gagal "pasang Docker"
V 'docker compose version' >> "$LOG" 2>&1 || gagal "docker compose tidak tersedia"

langkah "4. salin kode Rescue-Net (sama persis dengan yang live di Flex, tanpa rahasia)"
if [ "$MODE" = darurat ] && ! ssh -o BatchMode=yes -o ConnectTimeout=10 $FLEX true 2>/dev/null; then
  gagal "Flex mati: mode darurat butuh salinan kode di Aspire (belum ada — lihat P7)"
fi
ssh -o BatchMode=yes $FLEX "pct exec 201 -- tar -C /opt/rescue-net --exclude=./node/.env --exclude='./node/.env.bak*' \
   --exclude=./node/tunnel.env --exclude=./node/backups --exclude=./node/docker-compose.override.yml \
   --exclude='./node/docker-compose.override.yml.*' --exclude='*.bak-*' -czf - ." \
  | V "mkdir -p /opt/rescue-net && tar -C /opt/rescue-net -xzf - && mkdir -p /opt/rescue-net/node/backups && chmod 700 /opt/rescue-net/node/backups" \
  || gagal "salin kode"

langkah "5. siapkan cadangan data"
if [ "$MODE" = pindah ]; then
  langkah "   Flex -> mode pemeliharaan + cadangan final"
  ssh -o BatchMode=yes $FLEX "pct exec 201 -- sh -c 'cd /opt/rescue-net/node && docker compose exec -T backend bench --site osiun.localhost set-maintenance-mode on'" || gagal "pemeliharaan Flex"
  /root/bin/rn-cadangan-luar.sh >> "$LOG" 2>&1 || gagal "cadangan final"
fi
TS=$(ssh -o BatchMode=yes $ASP "cat $CADANGAN/TERBARU") || gagal "cadangan terbaru tidak ada di Aspire"
langkah "   cadangan $TS"
ssh -o BatchMode=yes $ASP "tar -C $CADANGAN -cf - $TS" | V "tar -C /opt/rescue-net/node/backups -xf - && cd /opt/rescue-net/node/backups/$TS && sha256sum -c --quiet SHA256SUMS" \
  || gagal "kirim/cek cadangan"

langkah "6. pasang & pulihkan Rescue-Net (unduh image ±2 GB bila belum ada; beberapa menit)"
JOBS=""; [ "$MODE" = pindah ] || [ "$MODE" = darurat ] && JOBS="--dengan-jobs"
V "cd /opt/rescue-net/node && ./pasang.sh --pulihkan backups/$TS $JOBS" >> "$LOG" 2>&1 || gagal "pasang.sh (lihat log)"
V "rm -rf /opt/rescue-net/node/backups/$TS"   # paket berisi kunci enkripsi: jangan disimpan di VPS

langkah "7. uji sehat"
UJI=$(V 'P=$(sed -n "s/^RN_WEB_PORT=//p" /opt/rescue-net/node/.env); for u in /rescue-net/ /rescue-net/pages/bencana-aktif.html /rescue-net-frappe/api/method/rescue_net.api_auth.account_status /rescue-net-frappe/api/method/rescue_net.api_control_centre.active_disasters_board; do printf "%s " $(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:${P:-8182}$u); done')
langkah "   HTTP: $UJI"
case "$UJI" in *[45]0[0-9]*|*000*) gagal "uji sehat: $UJI";; esac
N=$(V "cd /opt/rescue-net/node && docker compose exec -T backend bench --site osiun.localhost mariadb -N -e 'select count(*) from \`tabRN Disaster Event\`' 2>/dev/null | tail -1" || echo "?")
langkah "   data: $N bencana"

if [ "$MODE" = pindah ] || [ "$MODE" = darurat ]; then
  langkah "8. alihkan lalu lintas Cloudflare ke VPS"
  /root/bin/rn-burst-alih.sh ke-vps "$IP" >> "$LOG" 2>&1 || gagal "alih Cloudflare (VPS sudah siap; Flex masih pemeliharaan — putuskan manual)"
  ssh -o BatchMode=yes $FLEX "pct exec 201 -- sh -c 'cd /opt/rescue-net/node && docker compose stop worker scheduler'" 2>/dev/null || true
else
  langkah "8. (mode $MODE) lalu lintas TIDAK dialihkan; jobs mati"
fi
langkah "SELESAI dalam $(( ($(date +%s) - T0) / 60 )) menit $(( ($(date +%s) - T0) % 60 )) detik"
lapor "SELESAI dalam $(( ($(date +%s) - T0) / 60 )) menit. Uji HTTP: $UJI. Data: $N bencana."
