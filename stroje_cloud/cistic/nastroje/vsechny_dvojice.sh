#!/bin/bash
# vsechny_dvojice.sh tag  → ve scratchpadu vytvoří dvojice foto | model | překryv pro 11–14 (srovnani/c<N>_<tag>.png)
S=${KUF_SCRATCH:-/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad}
H=$(dirname "$0")/..
for n in 11 12 13 14; do python3 $H/nastroje/dvojice.py $S/../images/$n.jpg $H/srovnani/c${n}_$1.png $S/stroj/d${n}_$1.png 560 $H/zdroje/masky/m$n.json; done
