#!/bin/bash
# JEDNOU PROVZDY: srovnani orientace VSECH karoserii v katalogu i ve tvarech.
# Robert 2026-09-05: "Uz 1 provzdy nastavme v katalogu a ve tvarech ty karoserie
# tak jak je potrebuji hned teď to vyres" (po nalezu, ze Ducato i Scudo jsou
# vsechny opacne). bot8 2026-09-05.
#
#   ! bash /opt/konfigurator/scripts/2026-09-05_orientace_vse.sh --dry-run   # jen ukaze, co by udelal
#   ! bash /opt/konfigurator/scripts/2026-09-05_orientace_vse.sh             # provede
#
# Spustit MUSI clovek pres "!" - sandbox bota nepusti k prepisu guarded GLB
# (webapp/*). Overeno 2026-09-05: klasifikator odmitl, zamek se ani nevzal.
#
# BEZPECNOSTNI VLASTNOSTI (proc to jde pustit i opakovane):
#  1. Audit se PREMERUJE z aktualnich GLB pri kazdem behu (krok 1), necte se
#     zadny ulozeny seznam. Uz spravne otocena karoserie se proto preskoci -
#     NIKDY nedojde k dvojitemu flipu, ktery by ji vratil zpatky do spatne
#     orientace. Cely postup je idempotentni a nezavisly na tom, co uz kdo
#     driv flipnul (CI18, pet Jumpy, cokoli).
#  2. Zalohy se nikdy neprepisuji (GLB i sestavy) - prvni beh ulozi pred-flip
#     stav a dalsi behy ho nechaji byt.
#  3. Krok 4 overi vysledek nezavislym premerenim vsech 304 modelu.
#
# CO SE MENI:
#  - GLB karoserii (baked 180 deg kolem Y: POSITION+NORMAL (x,y,z)->(-x,y,-z))
#  - product_assemblies: ne-car_body dily dotcenych sestav (car_body dily
#    zustavaji na identite - mesh se otoci sam se souborem)
#  - custom_shapes (karoserie vcelku) se NEMENI: overeno, ze vsech 304 ma
#    car_body party na identite, takze se otoci automaticky s GLB.
set -e
cd /opt/konfigurator

DRY=""
if [ "$1" = "--dry-run" ]; then DRY="--dry-run"; fi

echo "######## 1/4 CERSTVY AUDIT (mereno z aktualnich GLB) ########"
api/venv/bin/python3 scripts/2026-09-05_orientace_dump.py
node scripts/2026-09-05_orientace_audit.js

if [ -n "$DRY" ]; then
  echo
  echo "######## DRY-RUN: co by se flipnulo ########"
  node scripts/2026-09-05_mass_orientation_fix.js --dry-run
  echo
  echo "######## DRY-RUN: ktere sestavy by se prepocitaly ########"
  echo "(seznam car_body id se bere z auditu, ne z predchoziho behu)"
  node -e '
    const fs=require("fs");
    const rows=fs.readFileSync("/tmp/orient_audit_fresh.jsonl","utf8").split("\n")
      .filter(l=>l.trim().startsWith("{")).map(l=>JSON.parse(l));
    const ids=[];
    rows.filter(r=>r.verdict==="NEEDS_FLIP").forEach(r=>String(r.ids||"").split("/")
      .map(s=>parseInt(s.trim(),10)).filter(Number.isFinite).forEach(n=>ids.push(n)));
    fs.writeFileSync("/tmp/flipped_cb_ids.json", JSON.stringify([...new Set(ids)],null,1));
    console.log("car_body id, kterych se to tyka: "+ids.length);
  '
  api/venv/bin/python3 scripts/2026-09-05_mass_flip_assembly_parts.py --dry-run
  echo
  echo "######## DRY-RUN HOTOVO - nic se nezmenilo ########"
  exit 0
fi

echo
echo "######## 2/4 FLIP GLB ########"
node scripts/2026-09-05_mass_orientation_fix.js --all

echo
echo "######## 3/4 PREPOCET REGALU V DOTCENYCH SESTAVACH ########"
api/venv/bin/python3 scripts/2026-09-05_mass_flip_assembly_parts.py

echo
echo "######## 4/4 NEZAVISLE OVERENI (premereni vsech 304 modelu) ########"
api/venv/bin/python3 scripts/2026-09-05_orientace_dump.py
node scripts/2026-09-05_orientace_audit.js --report

echo
echo "######## HOTOVO ########"
echo "Ocekavany vysledek kroku 4: NEEDS_FLIP = 0."
echo "Pak obnov scenu (F5) a zkontroluj - do kazde karoserie se musis divat"
echo "zadnimi dvermi dovnitr."
