#!/bin/bash
# Znovu sestaví modely DeWalt TSTAK (DWST83346, DWST83345) a spočítá IoU obrysu proti studiovým fotografiím
# (DWST83346: c02 čelo, c01 šikmo, c03 čelo; DWST83345: c02 čelo, c01 šikmo). Kamera každého pohledu se hledá z ručních landmarků
# (../zdroje/landmarky/<kód>_<pohled>_lm.json, start kamery <kód>_<pohled>_start.json) a překryvu obrysu v rámu fotografie (fit_lm.mjs);
# u fotografií se zvednutým držadlem se fituje i jeho úhel (skupina drzadlo). Výstup: ../../kufriky_cloud/srovnani/<kód>/<pohled>.json (kamera, pose, iou),
# render modelu ve stejném rámu (.png) a do scratchpadu překryv/dvojice. Fotografie se jen čtou ze scratchpadu (v repu nejsou).
# Použití: FOTO=<scratch>/kufry2 KUF_SCRATCH=<scratch>/tstak [ONLY="DWST83346_celo-c02 ..."] ./srovnej_vse_tstak.sh
#   c03 DWST83346 = kufr + vyjmutá vložka pod ním; do $KUF_SCRATCH/c03_box.jpg se uloží ořez bez vložky (řádky 0..1735, zbytek bílý).
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s podsložkami DWST83346-1 a DWST83345-1 (cNN.jpg)}" ; : "${KUF_SCRATCH:?KUF_SCRATCH=pracovní složka mimo repo}"
mkdir -p "$KUF_SCRATCH"
node ../vytvor_tstak.mjs
python3 -I -c "
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB'); b = Image.new('RGB', im.size, 'white'); b.paste(im.crop((0, 0, im.width, 1735)), (0, 0)); b.save(sys.argv[2], quality=95)" "$FOTO/DWST83346-1/c03.jpg" "$KUF_SCRATCH/c03_box.jpg"
LM=../zdroje/landmarky
# kód | pohled | fotografie | pevná pozice (k=v) | fitovaná skupina | váha landmarků
POHLEDY=(
 "DWST83346|celo-c02|$FOTO/DWST83346-1/c02.jpg||-|0.003"
 "DWST83346|sikmo-c01|$FOTO/DWST83346-1/c01.jpg|drzadlo=60|drzadlo|0.001"
 "DWST83346|celo-c03|$KUF_SCRATCH/c03_box.jpg||-|0.004"
 "DWST83345|celo-c02|$FOTO/DWST83345-1/c02.jpg|drzadlo=73|drzadlo|0.003"
 "DWST83345|sikmo-c01|$FOTO/DWST83345-1/c01.jpg|drzadlo=65|drzadlo|0.001"
)
for r in "${POHLEDY[@]}"; do
  IFS='|' read -r K P F POSE FP W <<< "$r"
  KEY="${K}_${P}"
  if [ -n "${ONLY:-}" ] && [[ " $ONLY " != *" $KEY "* ]]; then continue; fi
  ARGS=(--glb ../modely/$K.glb --foto "$F" --lm $LM/${K}_${P}_lm.json --kam $LM/${K}_${P}_start.json --sku $K --pohled $P --wl $W --roll --len 480)
  [ -n "$POSE" ] && ARGS+=(--pose $POSE)
  [ "$FP" != "-" ] && ARGS+=(--fit-pose $FP)
  echo "== $KEY"; node fit_lm.mjs "${ARGS[@]}" | tail -1 | cut -c1-260
  POSEJ=$(node -e "const j=JSON.parse(require('fs').readFileSync('../../kufriky_cloud/srovnani/$K/$P.json'));console.log(Object.entries(j.pose||{}).map(([a,b])=>a+'='+b).join(','))")
  (cd ../../kufriky_cloud && node render/srovnej.mjs --glb ../kufry_dewalt/modely/$K.glb --foto "$F" --sku $K --pohled $P --reuse ${POSEJ:+--pose $POSEJ} --len 1600 | tail -1 | cut -c1-120)
  python3 -I prekryv.py "$F" ../../kufriky_cloud/srovnani/$K/$P.png "$KUF_SCRATCH/${K}_${P}_prekryv.png" 0.5
done
python3 -I anotuj_json.py
