#!/bin/bash
# Znovu sestaví modely DS300/DS400 a spočítá IoU obrysu proti studiovým fotografiím (c01 zavřený s madlem nahoře, c02 zavřený, c03 otevřený) při ULOŽENÝCH kamerách
# (kufriky_cloud/srovnani/<kód>/*.json; kamery odhadnuty fit_ts2.mjs – obrys + ručně odečtené landmarky v zdroje/landmarky/). Fotografie se čtou ze scratchpadu (mimo repo).
# Použití: FOTO=<složka s podsložkami DWST83294-1 a DWST83342-1> KUF_SCRATCH=<scratch> ./srovnej_vse_ts2.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s podsložkami DWST83294-1 a DWST83342-1 (soubory c01.jpg ... c03.jpg)}"
node ../vytvor_ts2.mjs
for S in DWST83294 DWST83342; do
  LM=../zdroje/landmarky
  node iou_ts2.mjs --glb ../modely/$S.glb --foto $FOTO/$S-1/c01.jpg --sku $S --pohled sikmo-c01 --len 1000 --L 640 --lm $LM/${S}_sikmo-c01.json
  node iou_ts2.mjs --glb ../modely/$S.glb --foto $FOTO/$S-1/c02.jpg --sku $S --pohled sikmo-c02 --len 1000 --L 640 --lm $LM/${S}_sikmo-c02.json
  node iou_ts2.mjs --glb ../modely/$S.glb --foto $FOTO/$S-1/c03.jpg --sku $S --pohled otevreny-c03 --len 1000 --L 640
  node iou_ts2.mjs --glb ../modely/$S.glb --foto $FOTO/$S-1/c01.jpg --sku $S --pohled obrys-c01 --png 0 --L 640 --lm $LM/${S}_sikmo-c01.json
  node iou_ts2.mjs --glb ../modely/$S.glb --foto $FOTO/$S-1/c02.jpg --sku $S --pohled obrys-c02 --png 0 --L 640 --lm $LM/${S}_sikmo-c02.json
done
