#!/bin/bash
# Znovu sestaví model 2294834 a spočítá IoU obrysu proti jediné fotografii (c01 = L137214, pohled shora na zavřený kufr).
# Otevřený pohled pro 2294834 fotografie nemá – víko/vnitřek jsou odvozené z 2329229 (viz zdroje/2294834_poznamky.md).
# Použití: FOTO=<složka s c01.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse_2294834.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografií 2294834}"
node ../vytvor.mjs 2294834
node porovnej_celo.mjs --glb ../modely/2294834.glb --foto "$FOTO/c01.jpg" --sku 2294834 --pohled celo --az 180 --el 89.99 --dist 6000 | grep IoU
