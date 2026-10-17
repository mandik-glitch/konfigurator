#!/bin/bash
# Přefituje kamery c01, c02, c05 pro aktuální model 4932464078 (varianta dofit_v2) a vypíše IoU.
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
K=../../kufriky_cloud/srovnani_opravy/4932464078/kamery_4932464078.json
N=${1:-dofit_v2}
cd "$(dirname "$0")"
node fit.mjs --glb ../modely/4932464078.glb --foto $S/kufry3/4932464078/c01.jpg --kam $K --pohled c01 --start dofit_v2 --nazev $N --fix roll &
node fit.mjs --glb ../modely/4932464078.glb --foto $S/kufry3/4932464078/c02.jpg --kam $K --pohled c02 --start dofit_v2 --nazev $N --fix roll --pose madlo_1=130 &
node fit.mjs --glb ../modely/4932464078.glb --foto $S/kufry3/4932464078/c05.jpg --kam $K --pohled c05 --start dofit_v2 --nazev $N --fix roll --pose madlo_1=130,madlo_2=460 &
wait
