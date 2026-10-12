#!/bin/bash
# Znovu sestaví model 2329229 a spočítá IoU obrysu proti všem fotografiím (c01 pohled shora zavřený, c02/c03/c04 otevřený).
# Kamery otevřených pohledů jsou uložené v kufriky_cloud/srovnani/2329229/*.json (landmarky zdroje/landmarky/2329229_c0N_vstup.json → fit_lm.mjs --pose-fix, víko 135,7°).
# Fotografie se čtou ze scratchpadu (mimo repo). Použití: FOTO=<složka s c01..c04.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse_2329229.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2329229}"
node ../vytvor.mjs 2329229
node porovnej_celo.mjs --glb ../modely/2329229.glb --foto "$FOTO/c01.jpg" --sku 2329229 --pohled celo --az 180 --el 89.99 --dist 6000 | grep IoU
node iou_kamera.mjs --glb ../modely/2329229.glb --foto "$FOTO/c02.jpg" --sku 2329229 --pohled otevreny-c02
node iou_kamera.mjs --glb ../modely/2329229.glb --foto "$FOTO/c03.jpg" --sku 2329229 --pohled otevreny-c03
node iou_kamera.mjs --glb ../modely/2329229.glb --foto "$FOTO/c04.jpg" --sku 2329229 --pohled otevreny-c04
cd ../../kufriky_cloud
for v in "c02:otevreny-c02" "c03:otevreny-c03" "c04:otevreny-c04"; do f=${v%%:*}; p=${v##*:}; U=$(python3 -c "import json;print(json.load(open('srovnani/2329229/$p.json'))['pose']['vicko'])"); node render/srovnej.mjs --glb ../kufry_hilti/modely/2329229.glb --foto "$FOTO/$f.jpg" --sku 2329229 --pohled $p --pose vicko=$U --reuse >/dev/null; done
