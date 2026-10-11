#!/bin/bash
# Znovu sestaví model 2437394 a spočítá IoU obrysu proti všem použitelným fotografiím (kamery jsou uložené v kufriky_cloud/srovnani/2437394/*.json,
# odhadnuté z ručně změřených bodů + obrysu: nastroje/kalibruj.py → fit_lm.mjs). Fotografie se čtou ze scratchpadu (mimo repo).
# Použití: FOTO=<složka s c01..c04.jpg> ISO=<L153707_f2000.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2437394}" ; : "${ISO:?ISO=soubor L153707_f2000.jpg}"
node ../vytvor.mjs
node porovnej_celo.mjs --glb ../modely/2437394.glb --foto "$FOTO/c01.jpg" --sku 2437394 --pohled celo | grep IoU
node iou_kamera.mjs --glb ../modely/2437394.glb --foto "$FOTO/c02.jpg" --sku 2437394 --pohled otevreny-c02
node iou_kamera.mjs --glb ../modely/2437394.glb --foto "$FOTO/c03.jpg" --sku 2437394 --pohled otevreny-c03 --cervena 1
node iou_kamera.mjs --glb ../modely/2437394.glb --foto "$ISO" --sku 2437394 --pohled zavreny-iso-L153707
cd ../../kufriky_cloud
for v in "c02:otevreny-c02" "c03:otevreny-c03"; do f=${v%%:*}; p=${v##*:}; U=$(python3 -c "import json;print(json.load(open('srovnani/2437394/$p.json'))['pose']['vicko'])"); node render/srovnej.mjs --glb ../kufry_hilti/modely/2437394.glb --foto "$FOTO/$f.jpg" --sku 2437394 --pohled $p --pose vicko=$U --reuse >/dev/null; done
node render/srovnej.mjs --glb ../kufry_hilti/modely/2437394.glb --foto "$ISO" --sku 2437394 --pohled zavreny-iso-L153707 --reuse --len 1200 >/dev/null
