#!/bin/bash
# Puvod objednavky (order_host, order_lang), aliasy hostu mini-shopu a prirazeni mini-shopu dealerovi: patchne api/dealers.py, api/car_storefronts.py a api/orders.py, pusti testy nad ZIVYMI
# (uz patchnutymi) soubory a commitne. NEPOUSTET pred navrhem e-shopu od bot16 (bot3 2026-10-02: "cekej s nasazenim"). Migrace JIZ JE v DB (sql/2026-10-02_puvod_objednavky_storefront_dealer.sql
# a sql/2026-10-02_storefront_hosts.sql). api/*.py jde na ostro pri nasazeni serveru (03:30/12:30), po nasazeni overit /api/dealer/me=401 a hlavni routy.
set -u
cd /opt/konfigurator || exit 1
D=/opt/konfigurator/scripts/2026-10-02_dealeri_testy/nasazeni_puvod_objednavky
export BOT_ID=bot5
PY=/opt/konfigurator/api/venv/bin/python3
G_EXIST="api/dealers.py api/car_storefronts.py api/orders.py"
T=scripts/2026-10-02_dealeri_testy
TESTY="$T/test_storefront.py scripts/2026-09-30_karta_produktu_testy/run_all.sh $D"
scripts/lock.sh acquire bot5 "api/dealers.py+car_storefronts.py+orders.py: puvod objednavky, aliasy hostu, prirazeni mini-shopu dealerovi" --wait=600 || { echo "ZAMEK NEZISKAN"; exit 1; }
abort() { scripts/lock.sh release bot5; echo "ABORT: $1"; exit 1; }
rollback() { git checkout -- $G_EXIST scripts/2026-09-30_karta_produktu_testy/run_all.sh; scripts/lock.sh release bot5; echo "ROLLBACK: $1"; exit 1; }
for f in $G_EXIST; do [ "$(git hash-object $f)" = "$(git rev-parse HEAD:$f)" ] || abort "$f ma necommitnute zmeny"; done
python3 $D/patch_dealers_storefront.py api/dealers.py || rollback "patch dealers.py"
python3 $D/patch_storefronts_origin.py api/car_storefronts.py || rollback "patch car_storefronts.py"
python3 $D/patch_orders_origin.py api/orders.py || rollback "patch orders.py"
$PY -m py_compile $G_EXIST || rollback "py_compile"
python3 - <<'PY' || rollback "run_all.sh"
p = "scripts/2026-09-30_karta_produktu_testy/run_all.sh"
t = open(p, encoding="utf-8").read()
if "test_storefront.py" not in t:
    a = "  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_feed.py || rc=1\n"
    assert t.count(a) == 1
    t = t.replace(a, a + """systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
  ${DEALERS_PY:+--setenv=DEALERS_PY=$DEALERS_PY} ${CAR_STOREFRONTS_PY:+--setenv=CAR_STOREFRONTS_PY=$CAR_STOREFRONTS_PY} ${ORDERS_PY:+--setenv=ORDERS_PY=$ORDERS_PY} \\
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_storefront.py || rc=1
""")
    t = t.replace("DEALER_FEED_PY=... DOCUMENTS_PY=... ./run_all.sh", "DEALER_FEED_PY=... CAR_STOREFRONTS_PY=... DOCUMENTS_PY=... ./run_all.sh")
    open(p, "w", encoding="utf-8").write(t)
PY
bash -n scripts/2026-09-30_karta_produktu_testy/run_all.sh || rollback "syntaxe run_all.sh"
for t in test_storefront.py test_dealeri.py test_provize.py test_vyuctovani.py test_objednavky.py test_feed.py; do
  timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY $T/$t > /tmp/claude-0/pm_$t.out 2>&1 || { grep -E "^FAIL|Traceback" /tmp/claude-0/pm_$t.out | head -6 | cut -c1-300; rollback "$t nad zivymi soubory"; }
  echo "$t (zive soubory): $(tail -1 /tmp/claude-0/pm_$t.out)"
done
timeout 900 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator $PY scripts/2026-10-01_zastupce_montaz_testy/test_cena_varianty_zastupce.py > /tmp/claude-0/pm_zastupce.out 2>&1 || { grep -E "^FAIL|Traceback" /tmp/claude-0/pm_zastupce.out | head -6 | cut -c1-300; rollback "test_cena_varianty_zastupce.py"; }
echo "test_cena_varianty_zastupce.py (zive soubory): $(tail -1 /tmp/claude-0/pm_zastupce.out | cut -c1-110)"
OUT=$(timeout 120 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator/api $PY -c "import app; print('import app OK')" 2>&1); RC=$?
echo "$OUT" | tail -1
[ $RC -eq 0 ] || rollback "import app"
git add $T/test_storefront.py $D
BOT_ID=bot5 git commit -q -F - -- $G_EXIST $TESTY <<'MSG' || rollback "git commit"
feat(dealeri): puvod objednavky (order_host, order_lang), aliasy hostu mini-shopu a prirazeni mini-shopu dealerovi, dealer_source (bot5)

Navrh A-D schvalil bot3 (2026-10-02), upresneni Roberta: mini-shopy na nasich domenach (jedna na jazyk), jazyk urcuje DOMENA, jeden storefront muze mit vic hostu (alias, napr. vlastni domena
dealera), objednavka bez dealera je nase, zpetna provize jen na Robertuv pokyn. Migrace uz je v DB (a1f8c3a6, 321a434b).
- car_storefronts.py: resolve_storefront rozpozna i alias (storefront_hosts), record_order_origin (nemenny snimek order_host + order_lang podle jazyka storefrontu, nikdy nevyhodi vyjimku),
  add_storefront_host/remove_storefront_host/storefront_hosts_of, jazyk (lang) v admin API storefrontu (dedi se po nadrazene domene), aliasy v kontrole duplicit, mazani s historii = 409 misto 500.
- dealers.py: atribuce podle prirazeni mini-shopu (storefront_dealers, platne V TU CHVILI) ma prednost pred cookie z prokliku, vlastni nakup/testovaci/neaktivni dealer = nase BEZ navratu ke kliku,
  dealer_source (click/storefront), knihovna assign_storefront/end_assignment (nikdy zpetne, jedno prirazeni bez konce, planovany zacatek, zruseni planovaneho znovu otevre puvodniho dealera).
- orders.py: hook puvodu v orders_create a v objednavce z prijate online nabidky, admin serializace nese storefront_id/order_host/order_lang/dealer_source.
Test test_storefront.py 62/62 (skutecne POST /api/orders z ruznych hostu, aliasy, cas, mutace), regrese dealerskych testu beze zmeny. Na ostro pri nasazeni serveru.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Fb64CoYDZYH6vkfu892Gq
MSG
scripts/lock.sh release bot5
git log -2 --format='%h %s' | cut -c1-140
