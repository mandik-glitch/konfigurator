#!/bin/bash
# Jedno kolo ověření jednoho SKU: node vytvor_zasuvky.mjs + render všech pohledů + IoU + trojice foto | model | překryv (jen do scratchpadu).
# kolo.sh <SKU> <kolo> [pohledy…]    KAM=john → původní kamery z reportu kontroly (jinak přepočtené srovnani_opravy/<SKU>/cNN.json)
SKU=$1; KOLO=$2; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$HERE/../.."
if [ "$KAM" = "john" ]; then KAMOPT=""; SUF=_john; else KAMOPT="--kam doladena"; SUF=""; fi
SC=${SCRATCH:-/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad}
OUT=$SC/mszas/k$KOLO$SUF; mkdir -p $OUT
(cd $HERE/.. && node vytvor_zasuvky.mjs $SKU >/dev/null) || exit 1
POHL=${@:-$(ls $REPO/kufriky_cloud/kontrola_john_v6/$SKU | grep -o '^c0[0-9]' | sort -u)}
LIST=$(echo $POHL | tr ' ' ',')
node $HERE/srovnej.mjs --sku $SKU --pohled $LIST --out $OUT $KAMOPT >/dev/null
for P in $POHL; do
  echo -n "$SKU $P: "; python3 $HERE/dvojice.py $SC/kufry3/$SKU/$P.jpg $OUT/${SKU}_${P}_model.png $OUT/${SKU}_${P}_maska.png $OUT/${SKU}_${P}_dvojice.png $OUT/${SKU}_${P}_iou.json
done
