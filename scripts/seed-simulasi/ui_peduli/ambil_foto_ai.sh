#!/bin/bash
# foto AI simulasi untuk UI Peduli (coba ulang sampai berhasil, maks ~40 menit per foto)
cd "$(dirname "$0")"
declare -A P
P[cover]="documentary photo, a newly finished semi-permanent emergency school building in rural Lampung Indonesia, long single-storey row of classrooms with light steel frame, white fiber cement walls, blue zinc roof, aluminium windows, Indonesian red and white flag on pole, elementary students in red and white uniforms standing in front, volcanic island smoking faintly on the sea horizon, daylight, realistic, 35mm"
P[kondisi]="documentary photo, damaged elementary school in Indonesia covered with thick grey volcanic ash, collapsed roof, ash on ground, children studying inside blue emergency tents next to the building, overcast hazy sky, realistic news photo, 35mm"
P[pondasi]="realistic photo of a construction site in Indonesia, rows of small square concrete foundation footings connected by low reinforced concrete ground beams on flat grey ash covered ground, steel rebar, two Indonesian construction workers wearing hard hats, small orange cement mixer, wooden boards, daylight, documentary photography"
P[rangka]="documentary photo, construction site in Indonesia, light steel columns and galvanized cold-formed steel roof trusses installed on a long single-storey school building, workers with helmets on scaffolding, stack of zinc roof sheets on the ground, daylight, realistic, 35mm"
for k in cover kondisi pondasi rangka; do
  [ -s "$k.jpg" ] && continue
  enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "${P[$k]}")
  for i in $(seq 1 160); do
    code=$(curl -s -o "$k.tmp" -w "%{http_code}" --max-time 150 "https://image.pollinations.ai/prompt/$enc?width=1280&height=760&nologo=true&seed=$((RANDOM%9000+11))&model=flux")
    if [ "$code" = "200" ] && file "$k.tmp" | grep -qi "image"; then mv "$k.tmp" "$k.jpg"; echo "$(date +%T) OK $k"; break; fi
    sleep 15
  done
done
ls -la *.jpg
