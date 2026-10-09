#!/bin/sh
# Probe sesudah import/cutover (jalankan di server baru). Setiap baris harus 200 (atau kode yang tertulis).
set -u
ok=0; bad=0
chk() { # url kode-harapan label
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1" || echo 000)
  if [ "$code" = "$2" ]; then ok=$((ok+1)); printf 'OK   %s  %s\n' "$code" "$3"; else bad=$((bad+1)); printf 'GAGAL %s (harap %s)  %s\n' "$code" "$2" "$3"; fi
}
RN=http://127.0.0.1:8182/rescue-net-frappe/api/method/rescue_net
chk http://127.0.0.1:8181/                      200 "web SAC"
chk http://127.0.0.1:8181/privacy.html          200 "web SAC — privasi"
chk http://127.0.0.1:8180/login                 200 "portal SAC — login"
chk http://127.0.0.1:8180/sac                   301 "portal SAC — /sac tanpa login dialihkan"
chk http://127.0.0.1:8182/rescue-net/           200 "web Rescue-Net"
chk "$RN.api_events.disasters"                  200 "RN — daftar bencana (tamu)"
chk "$RN.api_ai.ai_providers"                   200 "RN — penyedia AI"
chk "$RN.api_control_centre.active_disasters_board" 200 "RN — Bencana Aktif"
chk "$RN.api_public_needs.board"                200 "RN — papan kebutuhan publik"
chk "$RN.api_aid_card.my_shelters"              403 "RN — endpoint login menolak tamu"
chk "$RN.api_custody.custody_chain"             403 "RN — rantai bukti menolak tamu"
echo "ringkas: $ok OK, $bad gagal"; [ $bad -eq 0 ]
