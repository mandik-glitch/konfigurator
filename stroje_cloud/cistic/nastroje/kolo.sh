#!/bin/bash
# kolo.sh <tag> <predchozi_tag>  – přestaví GLB, dofituje kamery 11–14 (start = předchozí kolo), zapíše IoU do zdroje/iou_kola.tsv, vytvoří dvojice ve scratchpadu
cd "$(dirname "$0")/.."
node vytvor.mjs | head -1 || exit 1
node nastroje/landmarky_xyz.mjs > zdroje/landmarky/xyz_model.json
for n in 11 12 13 14; do node nastroje/fit_kamery.mjs --foto $n --tag $1 --start srovnani/c${n}_$2.json > /tmp/fit_$n.txt 2>&1 & done; wait
python3 - "$1" <<'P'
import json,sys
tag=sys.argv[1]; r=[json.load(open(f'srovnani/c{n}_{tag}.json')) for n in (11,12,13,14)]
row=[tag]+[f"{x['iou']:.4f}" for x in r]+[f"{sum(x['iou'] for x in r)/4:.4f}"]+[f"{x['prumer_chyby_px']:.1f}" for x in r]
open('zdroje/iou_kola.tsv','a').write('\t'.join(row)+'\n'); print('\t'.join(row))
P
nastroje/vsechny_dvojice.sh $1
