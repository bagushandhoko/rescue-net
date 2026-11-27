#!/bin/sh
# Pengalih lalu lintas Cloudflare untuk Protokol Burst VPS (Suri 2026-11-27).
#   rn-burst-alih.sh ke-vps <IP> | ke-flex
# Tunnel "aspire-vm" sekarang dipakai SEMUA situs (RN, OSIUN, Portal, SAC) dengan konektor di Aspire VM101 & Flex,
# jadi RN tidak bisa dipindah sendirian lewat tunnel itu. Dibutuhkan SEKALI (owner): tunnel khusus RN "rn-burst"
# + izin token Cloudflare (Account: Cloudflare Tunnel Edit). Konfigurasi disimpan di /root/.rn-burst-cf.conf (600):
#   CF_TOKEN=..  CF_ACCOUNT=..  CF_ZONE=..  RN_TUNNEL_FLEX=<id tunnel normal>  RN_TUNNEL_BURST=<id tunnel rn-burst>
#   RN_TUNNEL_BURST_TOKEN=<token konektor rn-burst>
# Cara kerja: VPS menjalankan konektor rn-burst; DNS rescue-net.online (CNAME, proxied) dibalik ke tunnel rn-burst.
set -eu
C=/root/.rn-burst-cf.conf
[ -f $C ] || { echo "Pengalih Cloudflare BELUM disiapkan: butuh tunnel khusus RN + izin token (sekali oleh owner). Lihat docs/PROTOKOL-BURST-VPS.md bagian 8." >&2; exit 3; }
. $C
api() { curl -fsS -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" "$@"; }
REC=$(api "https://api.cloudflare.com/client/v4/zones/$CF_ZONE/dns_records?type=CNAME&name=rescue-net.online" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"][0]["id"])')
case "${1:-}" in
  ke-vps)  T=$RN_TUNNEL_BURST ;;
  ke-flex) T=$RN_TUNNEL_FLEX ;;
  *) echo "pakai: ke-vps <IP> | ke-flex" >&2; exit 2 ;;
esac
api -X PATCH "https://api.cloudflare.com/client/v4/zones/$CF_ZONE/dns_records/$REC" \
  --data "{\"content\":\"$T.cfargotunnel.com\",\"proxied\":true}" >/dev/null
echo "rescue-net.online -> tunnel $T"
