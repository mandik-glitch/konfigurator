#!/bin/bash
# Znovu sestaví model 2437354 (PKC 61) a spočítá IoU obrysu proti použitelným fotografiím (kamery jsou uložené v kufriky_cloud/srovnani/2437354/*.json,
# odhadnuté z ručně změřených bodů (zdroje/landmarky/2437354_*_vstup.json) + obrysu: kalibruj.py → fit_lm.mjs). Fotografie se čtou ze scratchpadu (mimo repo).
# ISO (L153711_ISO, na hilti.cz jen 250 × 234 px) se pro masku zvětší 4× do L153711_ISO_x4.jpg (jen ve scratchpadu).
# Použití: FOTO=<složka s L153710_f2000.jpg, L156512_f2000.jpg, L156505_f2000.jpg, L153711_ISO_x4.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse_2437354.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2437354 (vyšší rozlišení f2000)}"
node ../vytvor.mjs 2437354
node porovnej_celo_2437354.mjs --glb ../modely/2437354.glb --foto "$FOTO/L153710_f2000.jpg" --sku 2437354 --pohled celo | grep IoU
node iou_kamera.mjs --glb ../modely/2437354.glb --foto "$FOTO/L156512_f2000.jpg" --sku 2437354 --pohled otevreny-c02 --cervena 1
node iou_kamera.mjs --glb ../modely/2437354.glb --foto "$FOTO/L156505_f2000.jpg" --sku 2437354 --pohled otevreny-c03 --cervena 1
node iou_kamera.mjs --glb ../modely/2437354.glb --foto "$FOTO/L153711_ISO_x4.jpg" --sku 2437354 --pohled zavreny-iso-L153711
cd ../../kufriky_cloud
for v in "L156512_f2000:otevreny-c02" "L156505_f2000:otevreny-c03"; do f=${v%%:*}; p=${v##*:}; U=$(python3 -c "import json;print(json.load(open('srovnani/2437354/$p.json'))['pose']['vicko'])"); node render/srovnej.mjs --glb ../kufry_hilti/modely/2437354.glb --foto "$FOTO/$f.jpg" --sku 2437354 --pohled $p --pose vicko=$U --reuse >/dev/null; done
node render/srovnej.mjs --glb ../kufry_hilti/modely/2437354.glb --foto "$FOTO/L153711_ISO_x4.jpg" --sku 2437354 --pohled zavreny-iso-L153711 --pose vicko=0 --reuse --len 1000 >/dev/null
