#!/bin/bash
# Závěrečné dofitování kamer pro oba modely (varianta dofit_final) – po dokončení geometrie. Použití: fit_final.sh 4932464078|4932478161
cd "$(dirname "$0")"
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
SKU=$1; K=../../kufriky_cloud/srovnani_opravy/$SKU/kamery_$SKU.json; G=../modely/$SKU.glb; N=dofit_final
f() { node fit.mjs --glb $G --foto $S/kufry3/$SKU/$1.jpg --kam $K --pohled $1 --start $2 --nazev $N --fix roll "${@:3}"; }
if [ $SKU = 4932464078 ]; then
  f c01 dofit_v3; f c02 dofit_v3 --pose madlo_1=130; f c05 dofit_v3 --pose madlo_1=130,madlo_2=479
  f c09 dofit_v1 --ymin 790; f c08 dofit_v1 --ymin 880; f c07 dofit_v1 --pose madlo_1=130,madlo_2=479 --ymin 700
else
  f c06 dofit_v3; f c01 dofit_v3 --pose madlo=285; node fit.mjs --glb $G --foto $S/kufry3/$SKU/c02.jpg --kam $K --pohled c02 --start dofit_v3 --nazev $N --fix roll,fov --pose vicko=95,madlo=285
  node fit.mjs --glb $G --foto $S/kufry3/$SKU/c05.jpg --kam $K --pohled c05 --start dofit_v3 --nazev $N --maxroll 180 --iter 120
fi
