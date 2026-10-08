#!/bin/bash
# Jednorazova oprava orientace karoserii (bot22 2026-09-05).
# Spustit MUSI Robert pres "!" - sandbox blokuje botovi prepis guarded GLB.
#
#   ! bash /opt/konfigurator/scripts/2026-09-05_orientation_fix_run.sh CI18     # TEST: jedna karoserie
#   ! bash /opt/konfigurator/scripts/2026-09-05_orientation_fix_run.sh --all    # VSECH 190 najednou
#
# Co dela: flip GLB (baked 180Y, zalohy) -> re-audit (B_midZ<0) ->
# prepocet regalu v dotcenych sestavach (car_body party na identite).
# Vse zalohovane v backups/2026-09-05_mass_orientation_flip/.
set -e
cd /opt/konfigurator
MODE="${1:?Zadej argument: nazev karoserie (napr CI18) nebo --all}"

echo "######## 1/2 FLIP GLB ########"
if [ "$MODE" = "--all" ]; then
  node scripts/2026-09-05_mass_orientation_fix.js --all
else
  node scripts/2026-09-05_mass_orientation_fix.js --only "$MODE"
fi

echo
echo "######## 2/2 PREPOCET REGALU V SESTAVACH ########"
api/venv/bin/python3 scripts/2026-09-05_mass_flip_assembly_parts.py

echo
echo "######## HOTOVO - obnov scenu (F5) a zkontroluj ########"
