#!/bin/bash
# Přefituje kamery c06, c01, c02, c05 pro aktuální model 4932478161 (varianta $1) – postupně (sdílí JSON s kamerami).
cd "$(dirname "$0")"
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
K=../../kufriky_cloud/srovnani_opravy/4932478161/kamery_4932478161.json
N=${1:-dofit_v3}; ST=${2:-dofit_v2}
G=../modely/4932478161.glb
node fit.mjs --glb $G --foto $S/kufry3/4932478161/c06.jpg --kam $K --pohled c06 --start dofit_v1 --nazev $N --fix roll
node fit.mjs --glb $G --foto $S/kufry3/4932478161/c01.jpg --kam $K --pohled c01 --start $ST --nazev $N --fix roll --pose madlo=285
node fit.mjs --glb $G --foto $S/kufry3/4932478161/c02.jpg --kam $K --pohled c02 --start z_obrysu --nazev $N --fix roll,fov --pose vicko=95,madlo=285
node fit.mjs --glb $G --foto $S/kufry3/4932478161/c05.jpg --kam $K --pohled c05 --start $ST --nazev $N --maxroll 180 --iter 120
