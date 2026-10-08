#!/bin/bash
# Spusti vsechny testy skladove karty produktu, duplikace, validace a QA kontroly. Nic nezapisuje do ostrych dat
# (UI proti falesnemu serveru, DB testy jen cteni + docasne tabulky). Konci nenulove, kdyz cokoli selze.
# Kandidat pred nasazenim (nic se nezapise do zivych souboru):
#   ADMIN_HTML=... SKLAD_PRODUKTY_JS=... PRODUCTS_PY=... PRODUCT_HTML=... PRODUCT_ASSEMBLIES_PY=... NABIDKA_HTML=... SCENE_HTML=... CATALOG_PANELS_JS=... PATH_TRACED_JS=... CRM_NABIDKY_JS=... SCENE_OFFERS_PY=... DEALERS_PY=... APP_PY=... ORDERS_PY=... CFG_PRICE_PY=... COMMISSIONS_PY=... STATEMENTS_PY=... DEALER_ORDERS_PY=... DEALER_FEED_PY=... DOCUMENTS_PY=... ./run_all.sh
cd "$(dirname "$0")" || exit 1
rc=0
T=../2026-09-30_duplikace_produktu_testy
PY=/opt/konfigurator/api/venv/bin/python3
node test_karta_produktu.js || rc=1
node ../2026-10-01_popisky_dogus_testy/test_popisky_dogus.js || rc=1
$PY ../2026-10-01_popisky_dogus_testy/test_popisky_dogus_fakta.py || rc=1
node ../2026-10-01_nabidka_tabulka_cen_testy/test_nabidka_tabulka_cen.js || rc=1
node ../2026-10-01_nabidka_tabulka_cen_testy/test_balne_nabidka.js || rc=1
node ../2026-10-01_kotovani_testy/test_koty_zvetseni.js || rc=1
node ../2026-10-01_montaz_pct_nabidka_testy/test_montaz_pct_dialog_scena.js || rc=1
node ../2026-10-01_montaz_pct_nabidka_testy/test_montaz_pct_admin_editace.js || rc=1
$PY ../2026-10-01_montaz_pct_nabidka_testy/test_montaz_pct_backend.py || rc=1
node ../2026-10-01_zastupce_montaz_testy/test_produkt_zastupce_kosik.js || rc=1
$PY ../2026-10-01_zastupce_montaz_testy/test_cena_varianty_zastupce.py || rc=1
$PY ../2026-10-02_konfigurator_cena_testy/test_cena_parita.py || rc=1
$PY $T/test_endpoint_duplikace.py || rc=1
$PY $T/test_update_validace.py || rc=1
$PY $T/test_endpoint_normalize_slugs.py || rc=1
# DB testy potrebuji prihlaseni pres systemd (EnvironmentFile), ne cteni api/.env
for t in test_duplikace_db.py test_qa_kontrola.py test_qa_deska_m2.py test_product_slug.py test_qa_slug.py; do
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator $PY scripts/2026-09-30_duplikace_produktu_testy/$t || rc=1
done
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${PRODUCT_ASSEMBLIES_PY:+--setenv=PRODUCT_ASSEMBLIES_PY=$PRODUCT_ASSEMBLIES_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-01_zastupce_montaz_testy/test_kosik_zastupce_db.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DEALERS_PY:+--setenv=DEALERS_PY=$DEALERS_PY} ${APP_PY:+--setenv=APP_PY=$APP_PY} ${ORDERS_PY:+--setenv=ORDERS_PY=$ORDERS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_dealeri.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DEALERS_PY:+--setenv=DEALERS_PY=$DEALERS_PY} ${COMMISSIONS_PY:+--setenv=COMMISSIONS_PY=$COMMISSIONS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_provize.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DEALERS_PY:+--setenv=DEALERS_PY=$DEALERS_PY} ${COMMISSIONS_PY:+--setenv=COMMISSIONS_PY=$COMMISSIONS_PY} ${STATEMENTS_PY:+--setenv=STATEMENTS_PY=$STATEMENTS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_vyuctovani.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DEALER_ORDERS_PY:+--setenv=DEALER_ORDERS_PY=$DEALER_ORDERS_PY} ${ORDERS_PY:+--setenv=ORDERS_PY=$ORDERS_PY} ${APP_PY:+--setenv=APP_PY=$APP_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_objednavky.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DEALER_FEED_PY:+--setenv=DEALER_FEED_PY=$DEALER_FEED_PY} ${DEALERS_PY:+--setenv=DEALERS_PY=$DEALERS_PY} ${APP_PY:+--setenv=APP_PY=$APP_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_feed.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${CFG_PRICE_PY:+--setenv=CFG_PRICE_PY=$CFG_PRICE_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_konfigurator_cena_testy/test_cena_db.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_konfigurator_cena_testy/test_schema_konfigurace.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${CFG_PRICE_PY:+--setenv=CFG_PRICE_PY=$CFG_PRICE_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_konfigurator_cena_testy/test_montaz_sazba.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${SCENE_OFFERS_PY:+--setenv=SCENE_OFFERS_PY=$SCENE_OFFERS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-01_montaz_pct_nabidka_testy/test_montaz_pct_db.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DOCUMENTS_PY:+--setenv=DOCUMENTS_PY=$DOCUMENTS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_pdf_escape_testy/test_pdf_escape.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${DOCUMENTS_PY:+--setenv=DOCUMENTS_PY=$DOCUMENTS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_dealeri_testy/test_dodaci_list_dealer.py || rc=1
node ../2026-10-02_miniweb_testy/test_miniweb_schvaleni.js || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} ${MINIWEB_ADMIN_PY:+--setenv=MINIWEB_ADMIN_PY=$MINIWEB_ADMIN_PY} ${QA_CHECKS_PY:+--setenv=QA_CHECKS_PY=$QA_CHECKS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/test_miniweb.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} ${MINIWEB_ADMIN_PY:+--setenv=MINIWEB_ADMIN_PY=$MINIWEB_ADMIN_PY} ${QA_CHECKS_PY:+--setenv=QA_CHECKS_PY=$QA_CHECKS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/test_miniweb_poptavka.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} ${MINIWEB_ADMIN_PY:+--setenv=MINIWEB_ADMIN_PY=$MINIWEB_ADMIN_PY} ${QA_CHECKS_PY:+--setenv=QA_CHECKS_PY=$QA_CHECKS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/test_miniweb_admin.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} ${MINIWEB_ADMIN_PY:+--setenv=MINIWEB_ADMIN_PY=$MINIWEB_ADMIN_PY} ${QA_CHECKS_PY:+--setenv=QA_CHECKS_PY=$QA_CHECKS_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/test_qa_miniweb.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${CART_PY:+--setenv=CART_PY=$CART_PY} ${ORDERS_PY:+--setenv=ORDERS_PY=$ORDERS_PY} ${KONFIGURACE_KOSIK_PY:+--setenv=KONFIGURACE_KOSIK_PY=$KONFIGURACE_KOSIK_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py || rc=1
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
  ${MINIWEB_PY:+--setenv=MINIWEB_PY=$MINIWEB_PY} \
  --working-directory=/opt/konfigurator $PY scripts/2026-10-02_miniweb_testy/test_miniweb_shop.py || rc=1
[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"
exit $rc
