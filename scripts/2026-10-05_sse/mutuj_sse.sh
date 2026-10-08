#!/usr/bin/env bash
# mutuj_sse.sh <nazev> <soubor-v-api> <python-kod-upravujici-s> [test.py]   (bot8, 2026-10-05)
# Vytvori izolovanou kopii api/ (symlinky + zmeneny soubor), spusti test SSE (vychozi test_sse_jadro.py; jen Python, bez DB) a hlasi, zda mutace test SHODILA (CHYCENA = dobre).
# Kopie jde do mktemp adresare, ktery se po behu smaze; produkcni soubory se nemeni.
N=$1; SOUBOR=$2; CODE=$3; TEST=${4:-test_sse_jadro.py}
REPO=/opt/konfigurator
D=$(mktemp -d /tmp/mut_sse_XXXXXX)
mkdir -p $D/api
for f in $REPO/api/*.py $REPO/api/*.json; do ln -s $f $D/api/$(basename $f); done
ln -s $REPO/webapp $D/webapp
rm $D/api/$SOUBOR
python3 - "$D/api/$SOUBOR" "$REPO/api/$SOUBOR" "$CODE" <<'PYEOF'
import sys
p, src, code = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(src, encoding="utf-8").read()
g = {"s": s}
exec(code, g)
assert g["s"] != s, "mutace nic nezmenila"
open(p, "w", encoding="utf-8").write(g["s"])
PYEOF
[ $? -ne 0 ] && { rm -rf $D; exit 9; }
cd $REPO
STUL_API_OVERRIDE=$D/api $REPO/api/venv/bin/python3 scripts/2026-10-05_sse/$TEST > $D/vystup.log 2>&1
rc=$?
echo "mutace $N: rc=$rc ($( [ $rc -ne 0 ] && echo CHYCENA || echo NECHYCENA ))  $(grep -c '^FAIL' $D/vystup.log) FAIL"
rm -rf $D
