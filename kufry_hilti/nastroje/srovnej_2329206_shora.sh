#!/bin/bash
# IoU zavřeného kufru shora (c01). Použití: FOTO=<složka s c01..c04.jpg> KUF_SCRATCH=<scratch> ./srovnej_2329206_shora.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2329206}"
node porovnej_celo.mjs --glb ../modely/2329206.glb --foto "$FOTO/c01.jpg" --sku 2329206 --pohled shora --az 180 --el 89.5 --dist 8000 | grep IoU
