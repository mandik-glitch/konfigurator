#!/bin/bash
# přefituje kamery XL (3 fotky) podle aktuálního modelu; výstup cam/xl_*.json
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
cd /home/user/konfigurator/kufry_milwaukee_opravy
F=nastroje_4932498651_4932478162_4932501784/fit_cam.mjs
node $F --glb modely/4932478162.glb --foto $S/kufry3/4932478162/c01.jpg --cam $S/m/cam/o_4932478162_c01_s12.json --out $S/m/cam/xl_478162_c01.json --iters 100 &
node $F --glb modely/4932501784.glb --foto $S/kufry3/4932501784/c01.jpg --cam $S/m/cam/o_4932501784_c01_s12.json --out $S/m/cam/xl_501784_c01.json --pose madlo_nosne=180 --iters 100 &
node $F --glb modely/4932501784.glb --foto $S/kufry3/4932501784/c02.jpg --cam $S/m/cam/o_start12.json --out $S/m/cam/xl_501784_c02.json --pose madlo_nosne=180 --iters 100 &
wait
