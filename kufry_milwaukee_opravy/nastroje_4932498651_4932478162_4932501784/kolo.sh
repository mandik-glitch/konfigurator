#!/bin/bash
# kolo.sh SKU glb pohled foto kamera.json [extra args]  → pair do scratchpadu m/, iou na stdout
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
D=$(dirname "$0")
SKU=$1; GLB=$2; P=$3; FOTO=$4; CAM=$5; shift 5
node $D/rend.mjs --glb $GLB --foto $FOTO --cam $CAM --png $S/m/${SKU}_${P}.png --pair $S/m/${SKU}_${P}_pair.png "$@"
