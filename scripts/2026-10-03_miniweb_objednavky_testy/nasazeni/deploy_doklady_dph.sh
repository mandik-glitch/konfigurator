#!/bin/bash
# Mini-shop krok 3: doklady (zalohova faktura, VDD, faktura) s DPH 0 % a dolozkou pro platne IC DPH (shop_orders.vat_mode = 'reverse_charge') a s textem o prepoctu EUR x kurz v poznamce.
# Patchuje api/documents.py a api/bank_statements.py (sdilene moduly hlavniho e-shopu: pro objednavky bez vat_mode je chovani BEZE ZMENY), commitne i dokonceny api/miniweb_objednavky_admin.py.
# PORADI: az PO sade "objednavky". NEPOUSTET bez PRIMEHO povoleni Roberta v session, ktera skript spousti (commit guarded api/*.py = nasazeni, na ostro pri planovanem nasazeni 3:30/12:30).
# OTEVRENY BOD pro ucetni: zneni dolozky documents.VAT_ZERO_NOTE (navrh: "Osvobozene plneni - dodani zbozi do jineho clenskeho statu (par. 64 zakona c. 235/2004 Sb., o DPH). IC DPH odberatele: ...").
set -u
trap '' HUP
cd /opt/konfigurator || exit 1
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
K=scripts/2026-10-03_miniweb_objednavky_testy
D=$K/nasazeni
G="api/documents.py api/bank_statements.py"
scripts/lock.sh acquire bot5 "api/documents.py + api/bank_statements.py: DPH 0 % s dolozkou pro objednavky mini-shopu" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G 2>/dev/null; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
trap 'rollback "preruseno signalem"' INT TERM
for f in $G; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
grep -q "miniweb_objednavky_admin" api/app.py || abort "sada objednavky neni nasazena"
grep -q "_order_vat_rate" api/documents.py && abort "uz nasazeno"
for f in documents bank_statements; do patch -p1 --dry-run -s -i $D/$f.py.patch > /dev/null || abort "patch $f nesedi"; done
for f in documents bank_statements; do patch -p1 -s -i $D/$f.py.patch || rollback "patch $f"; done
$PY -m py_compile api/documents.py api/bank_statements.py api/miniweb_objednavky_admin.py api/miniweb_objednavky.py || rollback "py_compile"
run() { timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY "$@" > /tmp/claude-0/dd_out.txt 2>&1 || { grep -E "^FAIL|CHYBA" /tmp/claude-0/dd_out.txt | head -8 | cut -c1-300; rollback "test $1"; }; echo "$1: $(grep -E 'VYSLEDEK|OK [0-9]' /tmp/claude-0/dd_out.txt | tail -1 | cut -c1-110)"; }
run $K/test_miniweb_objednavky.py
run scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py
run scripts/2026-10-02_dealeri_testy/test_objednavky.py
run scripts/2026-10-01_zastupce_montaz_testy/test_kosik_zastupce_db.py
run scripts/2026-10-01_zastupce_montaz_testy/test_cena_varianty_zastupce.py
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "
import app, documents, bank_statements
assert documents.PODPORA_PRENESENE_DPH is True and documents._order_vat_rate({'vat_mode': 'reverse_charge'}) == 0 and documents._order_vat_rate({}) == documents.VAT_RATE and documents._order_vat_rate({'vat_mode': 'standard'}) == documents.VAT_RATE
print('import app OK, doklady s podporou DPH 0 % a beze zmeny pro bezne objednavky')" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app / doklady"
git add $K
BOT_ID=bot5 git commit -q -F - -- $G api/miniweb_objednavky_admin.py api/miniweb_objednavky.py $K <<'MSG'
feat(doklady): DPH 0 % s dolozkou pro objednavky mini-shopu s platnym IC DPH (shop_orders.vat_mode), text o prepoctu EUR x kurz na zalohove fakture (bot5)

Robert pres bot3 2026-10-03: zakaznik z jineho clenskeho statu s platnym IC DPH (VIES) = DPH se neuctuje, na dokladu dolozka; platba na jediny cesky ucet v Kc = cena v EUR x kurz.
- api/documents.py: _order_vat_rate(order) a _order_doc_note(order, base); zalohova faktura, VDD i faktura berou sazbu z objednavky (vat_mode reverse_charge = 0 %), poznamka nese dolozku (par. 64 zakona o DPH,
  IC DPH odberatele, zneni k potvrzeni ucetni) a text o prepoctu; bez vat_mode beze zmeny. api/bank_statements.py: castka bez DPH pri parovani platby podle sazby objednavky.
- api/miniweb_objednavky_admin.py: text o kurzu pro fakturu ze snimku objednavky, uprava stejne ceny dopravy podruhe neni chyba

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-120
