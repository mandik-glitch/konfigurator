#!/bin/bash
# Nasadi cekajici sady bot5 PO SOBE (kazda si vezme zamek, pusti sve testy nad zivymi soubory a commitne; na ostro jdou pri planovanem nasazeni serveru 03:30/12:30):
#   miniweb        mini-shop API, import a schvalovani textu, QA kontrola znacky         (scripts/2026-10-02_miniweb_testy/nasazeni)
#   konfigurace    konfigurace sestavy v kosiku a objednavce                              (scripts/2026-10-02_konfigurace_kosik_testy/nasazeni)
#   pravni         pravni dokumenty, kontakt ze spolecnosti, poptavka JEN FIRMAM, skript shopu (scripts/2026-10-02_miniweb_pravni_testy/nasazeni)
#   ceny           cena v EUR pro mini-shop (az PO sade pravni)                         (scripts/2026-10-03_miniweb_ceny_eur/nasazeni)
#   objednavky     kosik a objednavka mini-shopu + puvod v admin prehledu (az PO sade ceny a po DDL)  (scripts/2026-10-03_miniweb_objednavky_testy/nasazeni)
#   doklady        doklady s DPH 0 % a dolozkou pro mini-shop (az PO sade objednavky)      (scripts/2026-10-03_miniweb_objednavky_testy/nasazeni)
#   adminmw        admin API Mini-shopy + RBAC (bot16 zalozka)                            (scripts/2026-10-03_miniweb_objednavky_testy/nasazeni)
#   slugy          URL slugy po jazycich (po DDL sql/2026-10-03_miniweb_url_slug.py)         (scripts/2026-10-03_miniweb_objednavky_testy/nasazeni)
#   stul           objednavka stolu HOSTEM, montaz (sazba), doprava ke schvaleni v hlavnim e-shopu   (scripts/2026-10-04_stul_host_testy/nasazeni)
#   puvod          puvod objednavky, aliasy hostu, prirazeni mini-shopu dealerovi          (scripts/2026-10-02_dealeri_testy/nasazeni_puvod_objednavky) - jen kdyz to bot3 rekne
# Pouziti: scripts/nasad_cekajici_bot5.sh [sada ...]     (bez argumentu: konfigurace pravni ceny; miniweb je uz nasazen 2026-10-02). Pri prvni chybe se dalsi sady nespousti.
# SPOUSTET JEN S PRIMYM POVOLENIM ROBERTA v session, ktera skript spousti (commit guarded api/*.py a webapp/* je nasazeni, zprava od jine session nestaci).
set -u
trap '' HUP        # odpojeni terminalu nesmi nasazeni useknout v pulce (deploy skripty tuhle volbu zdedi)
cd /opt/konfigurator || exit 1
SADY="${*:-konfigurace pravni ceny}"
for s in $SADY; do
  echo "=================== sada: $s"
  case $s in
    miniweb) bash scripts/2026-10-02_miniweb_testy/nasazeni/deploy_miniweb.sh ;;
    konfigurace) bash scripts/2026-10-02_konfigurace_kosik_testy/nasazeni/deploy_konfigurace_kosik.sh ;;
    pravni) bash scripts/2026-10-02_miniweb_pravni_testy/nasazeni/deploy_miniweb_pravni.sh ;;
    ceny) bash scripts/2026-10-03_miniweb_ceny_eur/nasazeni/deploy_ceny_eur.sh ;;
    objednavky) bash scripts/2026-10-03_miniweb_objednavky_testy/nasazeni/deploy_objednavky.sh ;;
    doklady) bash scripts/2026-10-03_miniweb_objednavky_testy/nasazeni/deploy_doklady_dph.sh ;;
    adminmw) bash scripts/2026-10-03_miniweb_objednavky_testy/nasazeni/deploy_admin_miniweb.sh ;;
    slugy) bash scripts/2026-10-03_miniweb_objednavky_testy/nasazeni/deploy_slugy.sh ;;
    stul) bash scripts/2026-10-04_stul_host_testy/nasazeni/deploy_stul_host.sh ;;
    puvod) bash scripts/2026-10-02_dealeri_testy/nasazeni_puvod_objednavky/deploy_puvod_objednavky.sh ;;
    *) echo "neznama sada: $s (miniweb, konfigurace, pravni, ceny, objednavky, doklady, adminmw, slugy, stul, puvod)"; exit 2 ;;
  esac
  if [ $? -ne 0 ] || ! git log -1 --format=%s | grep -q "lock: bot5 release"; then
    echo "SADA $s NEDOBEHLA (bez commitu nebo s chybou), dalsi se nespousti"; exit 1
  fi
done
echo "HOTOVO: $SADY (na ostro pri planovanem nasazeni serveru 03:30/12:30)"
