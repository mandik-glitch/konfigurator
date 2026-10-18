#!/bin/bash
# rozdily_vse.sh tag – diff obrysů (zelená = shoda, červená = jen fotografie, modrá = jen model) pro 11–14 do jednoho obrázku ve scratchpadu
cd "$(dirname "$0")/.."; S=${KUF_SCRATCH:-/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad}
for n in 11 12 13 14; do node nastroje/fit_kamery.mjs --foto $n --nofit --tag $1 --start srovnani/c${n}_$1.json --maskout $S/stroj/mk$n.bin > /dev/null; python3 nastroje/rozdil.py $S/../images/$n.jpg $S/stroj/mk$n.bin zdroje/masky/m$n.json $S/stroj/diff$n.png 560 > /dev/null; done
python3 - <<'P'
import os
from PIL import Image
S=os.environ.get('KUF_SCRATCH','/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad')+'/stroj/'
ims=[Image.open(S+f'diff{n}.png') for n in (11,12,13,14)]; h=max(i.height for i in ims); W=Image.new('RGB',(1126,h*2+6),'white')
for k,i in enumerate(ims): W.paste(i,((k%2)*566,(k//2)*(h+6)))
W.save(S+'diff_all.png')
P
