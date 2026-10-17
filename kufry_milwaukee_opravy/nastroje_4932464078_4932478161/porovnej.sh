#!/bin/bash
# porovnej.sh <SKU> <foto cNN> <varianta kamery> [pose] [další volby iou.mjs]  → IoU + render do scratchpadu (rend_<SKU>_<cNN>.png) + dvojice
cd "$(dirname "$0")"
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
SKU=$1; C=$2; V=$3; POSE=$4; shift 4
K=../../kufriky_cloud/srovnani_opravy/$SKU/kamery_$SKU.json
node iou.mjs --glb ../modely/$SKU.glb --foto $S/kufry3/$SKU/$C.jpg --kam $K --pohled $C --kamvar $V ${POSE:+--pose $POSE} --rend $S/ms/rend_${SKU}_$C.png --pair $S/ms/dv_${SKU}_$C.png "$@"
