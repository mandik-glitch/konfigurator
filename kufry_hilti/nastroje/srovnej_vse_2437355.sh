#!/bin/bash
# Znovu sestaví model 2437355 (PKC 19) a spočítá IoU obrysu proti čelní fotografii (c01) a ISO fotografii (L153709).
# Kamera ISO se doladí z landmarků zdroje/landmarky/zavreny-iso-L153709.json (4 šrouby čepů západek) + překryv obrysu (fit_lm_2437355.mjs, start = kamera z minulého běhu).
# Fotografie se čtou ze scratchpadu (mimo repo). Použití: FOTO=<složka s c01.jpg> ISO=<L153709_f2000.jpg> KUF_SCRATCH=<scratch> ./srovnej_vse_2437355.sh
set -e
cd "$(dirname "$0")"
: "${FOTO:?FOTO=složka s fotografiemi 2437355 (c01.jpg)}" ; : "${ISO:?ISO=soubor L153709_f2000.jpg}"
node ../vytvor.mjs 2437355
node porovnej_celo.mjs --glb ../modely/2437355.glb --foto "$FOTO/c01.jpg" --sku 2437355 --pohled celo | grep IoU
START=$(mktemp); echo '{"azim":40,"elev":19.8,"roll":0,"dist":8890,"fov":2.26,"cx":600,"cy":329.5,"vicko":0}' > "$START"
node fit_lm_2437355.mjs --glb ../modely/2437355.glb --foto "$ISO" --lm ../zdroje/landmarky/zavreny-iso-L153709.json --kam "$START" --sku 2437355 --pohled zavreny-iso-L153709 --pose-fix --wl 0.01
cd ../../kufriky_cloud
node render/srovnej.mjs --glb ../kufry_hilti/modely/2437355.glb --foto "$ISO" --sku 2437355 --pohled zavreny-iso-L153709 --reuse --len 1200 | tail -1
