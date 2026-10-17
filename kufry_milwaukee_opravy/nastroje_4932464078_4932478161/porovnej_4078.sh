#!/bin/bash
# Rychlé porovnání SKU 4932464078: render ve zvolené kameře + detail. použití: porovnej_4078.sh c01 dofit_v2 [pose] -> vypíše IoU a vytvoří rend_<c>.png
cd "$(dirname "$0")"
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
K=../../kufriky_cloud/srovnani_opravy/4932464078/kamery_4932464078.json
node iou.mjs --glb ../modely/4932464078.glb --foto $S/kufry3/4932464078/$1.jpg --kam $K --pohled $1 --kamvar $2 ${3:+--pose $3} ${4:+$4}
