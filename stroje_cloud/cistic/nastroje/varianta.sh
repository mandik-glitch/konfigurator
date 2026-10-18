#!/bin/bash
# varianta.sh <tag> <SY> <predchozi_tag> – pomocná varianta modelu s jiným koeficientem SY (např. 1.0 = „poctivě z fotografií“, obálka v Y ≈ 610); do repa se ukládá jen srovnani/*.json/png
cd "$(dirname "$0")/.."
export CISTIC_SY=$2; export CISTIC_MODE=${CISTIC_MODE:-uni}
node vytvor.mjs | head -1
cp modely/cistic.glb /tmp/cistic_var_$1.glb
node nastroje/landmarky_xyz.mjs > zdroje/landmarky/xyz_model.json
for n in 11 12 13 14; do node nastroje/fit_kamery.mjs --glb /tmp/cistic_var_$1.glb --foto $n --tag $1 --start srovnani/c${n}_$3.json > /tmp/fitV_$n.txt 2>&1 & done; wait
python3 - "$1" <<'P'
import json,sys
tag=sys.argv[1]; r=[json.load(open(f'srovnani/c{n}_{tag}.json')) for n in (11,12,13,14)]
print(tag,[x['iou'] for x in r], round(sum(x['iou'] for x in r)/4,4), [x['prumer_chyby_px'] for x in r])
P
unset CISTIC_SY
node vytvor.mjs | head -1
node nastroje/landmarky_xyz.mjs > zdroje/landmarky/xyz_model.json
