#!/bin/bash
# Znovu sestaví model 2329206 a spočítá IoU obrysu proti všem použitelným fotografiím.
# c01 = zavřený kufr shora (téměř ortografický pohled, render ořezán na obrys); c02/c03/c04 = otevřený kufr, JEDEN záběr (stejná kamera) –
# kamery jsou uložené v kufriky_cloud/srovnani/2329206/*.json (z ručně změřených bodů zdroje/landmarky_2329206_c02.json + obrys; fit_lm_2329206.mjs).
# Fotografie se čtou ze scratchpadu (mimo repo). Použití: FOTO=<složka s c01..c04.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse_2329206.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2329206}"
node ../vytvor.mjs 2329206
node porovnej_celo.mjs --glb ../modely/2329206.glb --foto "$FOTO/c01.jpg" --sku 2329206 --pohled shora --az 180 --el 89.97 --dist 8000 | grep IoU
for p in c02 c03 c04; do node iou_kamera_2329206.mjs --glb ../modely/2329206.glb --foto "$FOTO/$p.jpg" --sku 2329206 --pohled otevreny-$p; done
