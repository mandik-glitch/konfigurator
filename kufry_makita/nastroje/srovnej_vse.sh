#!/bin/bash
# Přegeneruje GLB a spočítá IoU obrysu proti všem použitelným fotografiím (kamera se pro každý pohled znovu odhadne: IoU + ruční landmarky, póza madla/víka se doladí).
# Fotografie se čtou ze scratchpadu (mimo repo). Výstup: kufriky_cloud/srovnani/<kód>/<pohled>.png|json (jen vlastní rendery + čísla).
# Použití: FOTO=<scratchpad>/kufry2 KUF_SCRATCH=<scratchpad>/ks ./srovnej_vse.sh [kód ...]
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka kufry2 (s podsložkami 821549-5 ...)}"
node ../vytvor.mjs
declare -A DIR=( [8215495]=821549-5 [8215500]=821550-0 [8215518]=821551-8 [8215526]=821552-6 )
KODY=${@:-8215495 8215500 8215518 8215526}
LOG=${KUF_SCRATCH:-/tmp/kuf_scratch}/srovnej_vse.log; mkdir -p "$(dirname $LOG)"; : > $LOG
run() { # kod foto pohled start extra...
  local k=$1 f=$2 p=$3 st=$4; shift 4
  local lm=""; [ -f ../zdroje/landmarky/${k}_$p.json ] && lm="--lm ../zdroje/landmarky/${k}_$p.json --wl 0.004"
  node srovnej.mjs --kod $k --foto "$FOTO/${DIR[$k]}/$f.jpg" --pohled $p --start $st --fov0 17.8 --dist 1450 $lm "$@" 2>&1 | tail -1 | cut -c1-200 >> $LOG
}
for k in $KODY; do
  run $k c01 c01 35,18 --pose madlo=90 --free madlo --lim madlo=84:97 &
  run $k c02 c02 -35,18 --pose madlo=90 --free madlo --lim madlo=84:97 &
  run $k c03 c03 0,18 --pose madlo=90 --free madlo --lim madlo=84:97 &
  wait
  run $k c04 c04 35,30 --pose madlo=0,vicko=100 --free vicko --lim vicko=70:125
done
[ -f "$FOTO/821552-6/c09.jpg" ] && node celo.mjs --kod 8215526 --foto "$FOTO/821552-6/c09.jpg" --pohled c09-celo --dist 8000 --pose madlo=0 | grep IoU >> $LOG
cat $LOG | cut -c1-140
