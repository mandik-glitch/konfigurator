#!/bin/bash
# přefituje kamery všech 5 pohledů (maska bez vyplnění děr) podle aktuálních modelů → srovnani_opravy/<SKU>/<id>_kamera_dofit.json
S=/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad
cd /home/user/konfigurator/kufry_milwaukee_opravy
F=nastroje_4932498651_4932478162_4932501784/fit_cam.mjs; O=../kufriky_cloud/srovnani_opravy
node $F --nofill --glb modely/4932478162.glb --foto $S/kufry3/4932478162/c01.jpg --cam $O/4932478162/c01_kamera_dofit.json --out $S/m/cam/n_478162_c01.json --iters ${ITERS:-80} > $S/m/cam/n1.log &
node $F --nofill --glb modely/4932501784.glb --foto $S/kufry3/4932501784/c01.jpg --cam $O/4932501784/c01_kamera_dofit.json --out $S/m/cam/n_501784_c01.json --pose madlo_nosne=180 --iters ${ITERS:-80} > $S/m/cam/n2.log &
node $F --nofill --glb modely/4932501784.glb --foto $S/kufry3/4932501784/c02.jpg --cam $O/4932501784/c02_kamera_dofit.json --out $S/m/cam/n_501784_c02.json --pose madlo_nosne=180 --iters ${ITERS:-80} > $S/m/cam/n3.log &
node $F --nofill --glb modely/4932498651.glb --foto $S/kufry3/4932498651/c01.jpg --cam $O/4932498651/c01_kamera_dofit.json --out $S/m/cam/n_498651_c01.json --pos madlo_horni=618,madlo_stredni=254 --fixfov 17.7 --iters ${ITERS:-80} > $S/m/cam/n4.log &
node $F --nofill --glb modely/4932498651.glb --foto $S/kufry3/4932498651/c02.jpg --cam $O/4932498651/c02_kamera_dofit.json --out $S/m/cam/n_498651_c02.json --pos zasuvka=330 --iters ${ITERS:-80} > $S/m/cam/n5.log &
wait
for p in "4932478162 c01 n_478162_c01" "4932501784 c01 n_501784_c01" "4932501784 c02 n_501784_c02" "4932498651 c01 n_498651_c01" "4932498651 c02 n_498651_c02"; do set -- $p; cp $S/m/cam/$3.json $O/$1/$2_kamera_dofit.json; done
cat $S/m/cam/n?.log
