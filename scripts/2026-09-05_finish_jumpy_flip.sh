#!/bin/bash
# Dokonceni 180-flipu rodiny Jumpy - zbylych 5 karoserii (bot8 2026-09-05).
#
#   ! bash /opt/konfigurator/scripts/2026-09-05_finish_jumpy_flip.sh
#
# PROC SAMOSTATNY SKRIPT A NE `orientation_fix_run.sh --all`:
# `--all` cte /tmp/orient_audit_fresh.jsonl z 10:47, tedy z doby PRED flipem
# CI18. CI18 je v tom souboru porad veden jako NEEDS_FLIP, takze `--all` by ho
# flipnul PODRUHE = zpatky do spatne orientace. Tenhle skript jede cilene jen
# na 5 karoserii, ktere flip skutecne jeste nedostaly (overeno merenim
# 2026-09-05: CI13 +1943,2 | CI15 +2643,2 | CI19 +1763,5 | CI24 +1943,2 |
# CI26 +2643,2; naopak CI14 -2293,2, CI18 -1410,5, CI25 -2293,2 uz jsou OK).
#
# Sandbox bota nepusti k prepisu guarded GLB (webapp/*), proto to musi spustit
# Robert pres "!". Bot8 pak vysledek overi a commitne.
#
# POZOR (bot8 2026-09-05, doplneno): tenhle skript uz je PREKONANY skriptem
# scripts/2026-09-05_orientace_vse.sh, ktery resi CELY katalog (189 modelu),
# ne jen tuhle petici. Pouzij radeji ten. Tenhle zustava pro pripad, ze by
# nekdo chtel srovnat jen Jumpy rodinu.
#
# BEZPECNOST: krok 0 nize PREMERI audit z aktualnich GLB pri kazdem behu.
# Bez toho hrozil dvojity flip - kdyby uz nekdo tyhle karoserie mezitim
# flipnul (napr. prave pres orientace_vse.sh), zastaraly /tmp audit by je
# porad vedl jako NEEDS_FLIP a `--only` by je otocilo zpatky do spatne
# orientace. S cerstvym auditem se uz spravne otocena karoserie proste
# preskoci a skript je idempotentni.
set -e
cd /opt/konfigurator

KODY="CI13 CI15 CI19 CI24 CI26"

echo "######## 0/3 CERSTVY AUDIT (ochrana proti dvojitemu flipu) ########"
api/venv/bin/python3 scripts/2026-09-05_orientace_dump.py
node scripts/2026-09-05_orientace_audit.js

echo
echo "######## 1/3 FLIP GLB (5 karoserii, 15 souboru) ########"
for K in $KODY; do
  echo "--- $K ---"
  node scripts/2026-09-05_mass_orientation_fix.js --only "$K"
done

echo
echo "######## 2/3 PREPOCET REGALU V SESTAVACH ########"
# Kazdy beh --only prepsal /tmp/flipped_cb_ids.json jen svymi id, takze tady
# slozime uplny seznam vsech 15 car_body id z auditu a pustime prepocet jednou.
node -e '
const fs=require("fs");
const KODY=["CI13","CI15","CI19","CI24","CI26"];
const rows=fs.readFileSync("/tmp/orient_audit_fresh.jsonl","utf8")
  .split("\n").filter(l=>l.trim().startsWith("{")).map(l=>JSON.parse(l));
const ids=[];
for(const k of KODY){
  const r=rows.find(r=>(r.base||"").includes(k));
  if(!r){ console.error("CHYBI v auditu: "+k); process.exit(1); }
  String(r.ids||"").split("/").map(s=>parseInt(s.trim(),10))
    .filter(n=>Number.isFinite(n)).forEach(n=>ids.push(n));
}
if(ids.length!==15){ console.error("Ocekavano 15 car_body id, je "+ids.length); process.exit(1); }
fs.writeFileSync("/tmp/flipped_cb_ids.json", JSON.stringify([...new Set(ids)],null,1));
console.log("car_body id k prepoctu: "+ids.join(", "));
'
api/venv/bin/python3 scripts/2026-09-05_mass_flip_assembly_parts.py

echo
echo "######## 3/3 OVERENI ########"
api/venv/bin/python3 scripts/2026-09-05_verify_jumpy_flip.py

echo
echo "######## HOTOVO - obnov scenu (F5) a zkontroluj ########"
