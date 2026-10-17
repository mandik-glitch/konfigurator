#!/bin/bash
# Dofit kamery pro JOHNOVY modely (referenční – jen čteno) ve stejném postupu jako pro naše: umožní srovnání "horní meze" jablka s jablkem.
cd "$(dirname "$0")"
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
J=../../kufriky_john/nahled-modely-v6/modely
K1=../../kufriky_cloud/srovnani_opravy/4932464078/kamery_4932464078.json
K2=../../kufriky_cloud/srovnani_opravy/4932478161/kamery_4932478161.json
for c in c01 c02; do node fit.mjs --glb $J/4932464078.glb --foto $S/kufry3/4932464078/$c.jpg --kam $K1 --pohled $c --start z_bodu --nazev john_dofit --fix roll; done
node fit.mjs --glb $J/4932464078.glb --foto $S/kufry3/4932464078/c05.jpg --kam $K1 --pohled c05 --start z_bodu --nazev john_dofit --fix roll
node fit.mjs --glb $J/4932478161.glb --foto $S/kufry3/4932478161/c06.jpg --kam $K2 --pohled c06 --start z_bodu --nazev john_dofit --fix roll
node fit.mjs --glb $J/4932478161.glb --foto $S/kufry3/4932478161/c01.jpg --kam $K2 --pohled c01 --start z_obrysu --nazev john_dofit --fix roll
