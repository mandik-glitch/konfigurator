#!/bin/bash
# dev.sh <SKU> <pohled> [tag] : sestaví model do /tmp/dev_<SKU>.glb (modely/ se nemění) a vyrenderuje z uložené dofitované kamery (bez fitu) → scratchpad/mk79/rend_<tag>.png + dvojice
cd /home/user/konfigurator/kufry_milwaukee_opravy
SKU=$1; P=$2; TAG=${3:-dev_$SKU_$P}
KUF_OUT=/tmp/dev_$SKU.glb node vytvor_4932464079_4932499703.mjs $SKU | cut -c1-110
cd nastroje_4932464079_4932499703
export KUF_SCRATCH=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad/mk79
ST=$(python3 -c "
import json,os
f='../../kufriky_cloud/srovnani_opravy/$SKU/kamery_dofit_$SKU.json'
d=json.load(open(f)) if os.path.exists(f) else {}
c=d.get('$P')
if c:
    k=c['kamera']; print('--st',','.join(str(k[x]) for x in ['azim','elev','dist','fov','cx','cy']), '--pose', ','.join(f'{a}={b}' for a,b in (c.get('pose') or {}).items()) or 'x=0')
")
node srov.mjs --cfg cfg_$SKU.json --pohled $P --glb /tmp/dev_$SKU.glb $ST --tag $TAG | head -c 160; echo
