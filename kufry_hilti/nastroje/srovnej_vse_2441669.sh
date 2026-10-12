#!/bin/bash
# Znovu sestaví model 2441669 a spočítá IoU obrysu proti fotografiím c01 (čelo), c02 a c03 (šikmo shora; STEJNÝ záběr - c03 je c02 s kótami a bez příčky).
# Kamery c02/c03 jsou uložené v kufriky_cloud/srovnani/2441669/otevreny-c0X.json (z 6 ručně změřených bodů na čelní rovině: zdroje/landmarky_2441669_c0X.json,
# + doladění překryvem obrysu: fit_2441669.mjs). Fotografie se čtou ze scratchpadu (mimo repo). Vlastní rendery (bez fotografií) se ukládají do srovnani/2441669/.
# Použití: FOTO=<složka s c01..c04.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse_2441669.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2441669}"
node ../vytvor.mjs 2441669
node porovnej_celo.mjs --glb ../modely/2441669.glb --foto "$FOTO/c01.jpg" --sku 2441669 --pohled celo | grep IoU
node iou_kamera.mjs --glb ../modely/2441669.glb --foto "$FOTO/c02.jpg" --sku 2441669 --pohled otevreny-c02 --cervena 1
node iou_kamera.mjs --glb ../modely/2441669.glb --foto "$FOTO/c03.jpg" --sku 2441669 --pohled otevreny-c03 --cervena 1
node dvojice_2441669.mjs --glb ../modely/2441669.glb --foto "$FOTO/c02.jpg" --pohled otevreny-c02 --vlastni-render otevreny-c02.png >/dev/null
node dvojice_2441669.mjs --glb ../modely/2441669.glb --foto "$FOTO/c03.jpg" --pohled otevreny-c03 --vlastni-render otevreny-c03.png >/dev/null
