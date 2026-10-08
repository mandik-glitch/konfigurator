#!/bin/bash
set -e
cd /opt/konfigurator

declare -A CARID=( [FO10]=254 [FO11]=257 [FO21]=260 [FO27]=263 [FO28]=266 [FO29]=269 [FO31]=272 [FO38]=275 [FO39]=278 [FO47]=281 [FO48]=284 [FO55]=287 [FO56]=290 [VW11]=890 [VW12]=893 [VW15]=896 [VW25]=899 [VW27]=902 [VW29]=905 [VW30]=908 [VW42]=911 [VW43]=914 )
declare -A LABEL=( [FO10]="Custom FO10" [FO11]="Custom FO11" [FO21]="Custom FO21" [FO27]="Custom FO27" [FO28]="Custom FO28" [FO29]="Custom FO29" [FO31]="Transit Custom L2 FO31" [FO38]="Custom FO38" [FO39]="Custom FO39" [FO47]="E-Transit Custom L1 FO47" [FO48]="E-Transit Custom L2 FO48" [FO55]="Custom FO55" [FO56]="Custom FO56" [VW11]="T6 VW11" [VW12]="T6 VW12" [VW15]="T6 VW15" [VW25]="T7 VW25" [VW27]="T7 VW27" [VW29]="T7 TwinCab VW29" [VW30]="T7 TwinCab VW30" [VW42]="T7 VW42" [VW43]="T7 VW43" )

OK_KEYS=$(python3 -c "
import json
d = json.load(open('scripts/tmp_2026-08-31_batch_results.json'))
print(' '.join(k for k,v in d.items() if v['ok']))
")
echo "OK keys: $OK_KEYS"

for key in $OK_KEYS; do
  echo "=== $key ==="
  node scripts/tmp_2026-08-31_gen2d_generic.js "$key" || { echo "$key: GATE FAILED - skipping insert"; continue; }
  /opt/konfigurator/api/venv/bin/python3 scripts/tmp_2026-08-31_batch_insert.py "$key" "${CARID[$key]}" "${LABEL[$key]}" "Batch Ford Custom/Transit Custom + VW Transporter T6/T7 (bot16, 2026-08-31/09-01). Generic pipeline: orientation-flip + mirror-X auto-detected, leg 30x30 D=326 H=1180 (T6-derived design, custom_shapes 512/513 converted), fresh collision-stepped bulkhead/floor/wall/rear-boundary/arch-extension/rail-floor/ceiling per vehicle, height diversity per rule 6, box-overhang per rule 7. See KOMPONENTY_EUROBOXY.md batch section for full recipe and caveats."
done
