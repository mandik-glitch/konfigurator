#!/bin/bash
cd "$(dirname "$0")"
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
export KUF_SCRATCH=$S/ms
K=../../kufriky_cloud/srovnani_opravy/4932464078/kamery_4932464078.json
G=../modely/4932464078.glb
node fit.mjs --glb $G --foto $S/kufry3/4932464078/c09.jpg --kam $K --pohled c09 --start start --nazev dofit_v1 --fix roll --ymin 790 --iter 150
node fit.mjs --glb $G --foto $S/kufry3/4932464078/c08.jpg --kam $K --pohled c08 --start start --nazev dofit_v1 --fix roll --ymin 880 --iter 150
