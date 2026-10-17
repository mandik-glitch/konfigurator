#!/bin/bash
# Závěrečný běh: sestaví GLB, vyrenderuje všechny pohledy z kamer (přepočtených i původních z reportu), spočítá IoU, dofit kamer,
# volné pohledy modelu a složí výsledky do kufriky_cloud/srovnani_opravy/<SKU>/ + nahled/<SKU>.html.   finalni_beh.sh <kolo>
KOLO=$1; HERE="$(cd "$(dirname "$0")" && pwd)"; SC=${SCRATCH:-/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad}
SKUS="4932472129 4932472130 4932493189 4932493190"
for s in $SKUS; do python3 $HERE/kamery_znovu.py $s > /dev/null; done
for s in $SKUS; do $HERE/kolo.sh $s $KOLO; KAM=john $HERE/kolo.sh $s $KOLO; done
POH_ALL="4932472129:c01,c02 4932472130:c01,c02 4932493189:c01,c02,c03,c04,c05 4932493190:c01,c02,c03,c04,c05,c06"
for it in $POH_ALL; do node $HERE/fit_kamera.mjs --sku ${it%%:*} --pohled ${it##*:} --scratch $SC; done
python3 $HERE/sloz_vysledky.py $SC $KOLO $KOLO $SKUS
for s in $SKUS; do
  OUT=$HERE/../../kufriky_cloud/srovnani_opravy/$s
  node $HERE/pohledy.mjs --sku $s --out $OUT --sada zakladni; node $HERE/pohledy.mjs --sku $s --out $OUT --sada otevrene
  rm -f $OUT/${s}_shora.png $OUT/${s}_bok.png $OUT/${s}_bok_plne.png $OUT/${s}_shora_plne.png
done
node $HERE/zabal_nahled.mjs $SKUS
