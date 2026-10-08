#!/usr/bin/env python3
"""Automat, ktery si sam z prehledu vyroby sestav bere praci - Robertovo
zadani ("dela nekdo na watchdogovi pro hlidani botu aby si sami z tabulky
vybrali praci... protoze ty [bot3] to taky nezvladas ridit"), navrh bot10,
postaveno bot9 2026-09-11. Zabrani resi scripts/production_work_claims.py
(viz tam i sql/2026-09-11j_production_work_claims.sql pro schema a princip -
NENI TO DEPLOY_LOCK).

Spousti se periodicky (systemd timer, viz deploy/konfigurator-watchdog-
prace.{service,timer}) jako www-data, NE uvnitr gunicornu - zmena kodu
uvnitr bezici sluzby by vyzadovala restart, ktery se dnes (2026-09-11)
nesmi delat driv, nez dobehne ingest davky 334.

KROKY, KTERE AUTOMAT SMI - a JEN TY (Robert/bot3 2026-09-11):
  * bom_backfill    - doplneni kusovniku/ceny u sestav bez BOM
                       (scripts/2026-09-06_backfill_bom_price.js).
                       AKTUALIZACE (bot8 2026-09-13): integrovana
                       detectRealJointCount() (profil-profil only, viz
                       zaznam joint_count_backfill nize) - tenhle krok
                       tedy uz POCITA I CENU SPOJU spravne. Rucne
                       spusteno na CELY katalog 2026-09-13 (303/303
                       sestav, 0 chyb, primo na Robertuv pokyn "aktualizovat
                       ceny sestav v DB, podle sceny, napric systemem"),
                       zaloha backups/2026-09-06_bom_backfill/pred_zapisem.json.
  * kolizni_sweep   - ZAMITNUTO bot16 (2026-09-11), NEIMPLEMENTOVAT.
                       Kandidat navrhl bot10, ale: (1) prepocet kolizi uz
                       bezi automaticky - scripts/2026-09-11_prepocet_kolize.py
                       na konfigurator-kolize-uhelniky.timer, kazdych 15 min,
                       zapisuje presne kolize_pocet/kolize_detail - druhy
                       nezavisly zapisovac do tehoz pole by byl zavod, ne
                       prinos; (2) kolizni priznak je PRUBEZNE prepocitavany
                       stav (muze se kdykoli vratit), ne jednorazove
                       dokoncitelny ukol - nesedi do modelu zaber->udelej->
                       oznac hotovo; (3) drazsi vrstva (navrh posunu/odsunu,
                       scripts/2026-09-11_sweep_kolizni_uhelniky.cjs +
                       report) je VYSLOVNE podklad pro Robertovo rozhodnuti,
                       ne pro automatickou opravu - propojeni s dalsim
                       automatickym krokem by rizikovalo posun/smazani
                       geometrie bez schvaleni (stejny duvod, proc se
                       razitka nedelaji automaticky).
  * joint_count_backfill - VYRAZENO 2026-09-11 (bot3, po nalezu bot9):
                       scene.html:16397 ma vyslovne Robertovo pravidlo
                       (2026-08-04) "prislusenstvi na profil se do ceny
                       spoje NEMA pocitat" - joint_count_batch.js pocita i
                       uhelniky/zaslepky, coz je s tim v primem rozporu.
                       Dokud Robert nerozhodne, ktere pravidlo plati,
                       automat cislo spoju NESMI rozsevat. Neodstranovat
                       tenhle zaznam, az se rozhodne, sem patri vysledek.

                       VYSLEDEK (bot3 2026-09-13): Robert pravidlo
                       opakovane a vyslovne potvrdil - plati profil-profil
                       (viz PLAN_TVORBY_SESTAV.md, "Vyreseno 2026-09-13").
                       scene.html sjednoceno do classifyJointPair, novy
                       Node.js port detectRealJointCount (profil-profil
                       only) existuje.

                       OPRAVA (bot8 2026-09-13): tenhle konkretni krok
                       (joint_count_backfill / joint_count_batch.js)
                       zustava VYRAZENY TRVALE, ne "ceka na implementaci"
                       - jeho ukol uz plni JINY, uz povoleny krok
                       bom_backfill (viz vyse), do ktereho byl
                       detectRealJointCount() rovnou integrovan a uz
                       SPUSTEN na cely katalog. Samostatny druhy krok nad
                       stejnymi daty (data.price_summary) by byl jen
                       riziko zavodu dvou nezavislych zapisovacu, ne
                       prinos - tenhle zaznam uz nema co dohanet, nechavat
                       vyrazeny navzdy.

                       ZAPNUTO ZPET (bot9, 2026-09-18): app_settings[
                       'watchdog_prace_povoleno']='1' - blokujici otazka
                       byla vyresena uz 2026-09-13 (viz VYSLEDEK/OPRAVA
                       vyse), vypnuti od 2026-09-11 do dnes bylo jen
                       proto, ze rozhodnuti o zapnuti zustalo delegovane
                       na bot3/bot9 a nikdo ho fakticky neprovedl - az
                       nalez u sestavy #552 (schvalena, ale bez BOM/ceny
                       kvuli vypnutemu automatu) na to upozornil. Overeno
                       pred zapnutim primo v kodu (hranice vyse, safety
                       rails beze zmeny).

HRANICE, KTERE SE NESMI PREKROCIT (nemenit bez noveho rozhodnuti bot3):
  * zadny krok, o kterem rozhoduje clovek (schvaleni, publikace, cena,
    mazani, zadani renderu) - automat na ne nesaha, ani nepřímo.
  * renderovaci davku zadava JEDINE bot3 - tenhle skript nikdy nevola
    scripts/2026-09-09_turntable_render.py ani pribuzne.
  * nic destruktivniho - pise JEN data.bom/data.price_summary (u
    bom_backfill). NIKDY data.parts.
  * strop KROKU_MAX kroku na jedno spusteni, pak konec (zadna nekonecna
    smycka - dalsi beh prijde az od timeru).
  * 3 selhani tehoz cile+kroku po sobe = automat chvili nezkousi (odstup 30 min,
    pak 1 h, 2 h ... max 24 h, viz production_work_claims.blokovano; drive
    "navzdy", zmena bot5 2026-10-02) a necha to bublat do
    /api/admin/vyroba-sestav/prehled jako "vyzaduje pohled cloveka"
    (fail_count, viz production_work_claims.fail_count_of).
  * vypinac: app_settings['watchdog_prace_povoleno'] - cte se na ZACATKU
    KAZDEHO behu (skript je oneshot pres timer, ne trvaly proces). Vypnuti
    tedy NEPRERUSI prave bezici beh (ten dojede sve zbyle kandidaty do
    stropu KROKU_MAX nebo do konce seznamu) - zabere az u DALSIHO tiku
    casovace, ktery uz vubec nezacne. Upresneno bot4 pri kontrole pred
    zapnutim (puvodni formulace "zabere hned" byla nepresna).

ZNAME OMEZENI (zaznamenano cestne, ne schovano): tenhle skript pouziva
2026-09-06_backfill_bom_price.js jako subprocess - ten ma HARDCODED sdilene
cesty (/tmp/katalog_pro_backfill.json, /tmp/vsechny_sestavy_pro_backfill.json,
/tmp/backfill_bom_vysledky/). Kazdy beh si tyhle dva vstupni dumpy OBNOVI
SAM (cerstva data), takze soubeh s rucnim spustenim tehoz skriptu NEKYM
JINYM muze teoreticky zachytit castecne prepsany soubor (zadny atomicky
zapis/rename na te strane). U vystupniho souboru pro KONKRETNI zpracovavane
ID kolize nehrozi (kazde ID ma svuj soubor, ten se po pouziti smaze), jen u
sdilenych VSTUPNICH dumpu. Riziko je male (rucni beh je vzacna, deliberatni
akce, ne bezici smycka) - zaznamenano, ne resene zmenou cizich skriptu bez
domluvy s bot8/bot10.

Pouziti:
    api/venv/bin/python3 scripts/2026-09-11_watchdog_prace.py            # beh
    api/venv/bin/python3 scripts/2026-09-11_watchdog_prace.py --dry-run  # jen vypise kandidaty, nic nezabira/nezapisuje
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - driv nez production_work_claims (potrebuje app.get_conn)
import production_work_claims as pwc  # noqa: E402

HELD_BY = "automat:bom_backfill"
STEP_KEY = "bom_backfill"
KROKU_MAX = 20
LEASE_SECONDS = 1200          # 20 minut - viz WORKFLOW.md pozadavek na prodlouzitelnost
MAX_FAIL = 3

KATALOG_DUMP = "/tmp/katalog_pro_backfill.json"
ASM_DUMP = "/tmp/vsechny_sestavy_pro_backfill.json"
OUT_DIR = "/tmp/backfill_bom_vysledky"
REPO = "/opt/konfigurator"


def povoleno(cur):
    v = app.get_setting(cur, "watchdog_prace_povoleno", "0")
    return str(v).strip() == "1"


def kandidati_bom_backfill(cur):
    """Sestavy s prazdnym bom (stejna podminka jako 'Scéna' sloupec v
    api/production_overview.py: bool(bom and price_summary.get('material_czk')
    is not None) - tady jen ta cast 'bom je prazdny', protoze doplnujeme
    prave to)."""
    cur.execute("SELECT id, name, data FROM product_assemblies ORDER BY id")
    ven = []
    for r in cur.fetchall():
        try:
            d = json.loads(r["data"]) if r["data"] else {}
        except (TypeError, ValueError):
            continue
        if not (d.get("bom") or []):
            ven.append((r["id"], r["name"]))
    return ven


def obnov_vstupni_dumpy():
    """Cerstvy katalog + cerstvy seznam sestav - viz ZNAME OMEZENI vyse."""
    subprocess.run(
        [os.path.join(REPO, "api/venv/bin/python3"),
         os.path.join(REPO, "scripts/2026-09-06_dump_katalog_pro_backfill.py")],
        check=True, capture_output=True, text=True, timeout=120,
    )
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, data FROM product_assemblies ORDER BY id")
            rows = cur.fetchall()
    finally:
        conn.close()
    with open(ASM_DUMP, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)


def slouc_price_summary(stary_ps, novy_ps):
    """`2026-09-06_backfill_bom_price.js` vzdy pocita s totalJoints=0 (znama
    mezera - viz jeho hlavicka) a vraci CELE price_summary vcetne
    joint_count=0/joint_czk=0. Kdyby se to prosty prepsalo, sestava, ktera
    uz ma DOPOCITANY joint_count (jinou cestou - napr. rucnim
    joint_count_batch.js behem, az se pravidlo vyjasni), by o nej tichym
    zapisem prisla presne jako pri otevreni ve scene (viz AGENTS_LOG.md,
    2026-09-11, "reload joint_count konflikt pravidel"). Nalezeno bot4 pri
    kontrole pred zapnutim.

    Pravidlo: NEEDITOVAT POLE, KTERE NEDOPOCITAVAME. Kdyz uz sestava ma
    nenulovy joint_count, zachova se (i joint_czk) a `total_czk` se
    prepocita tak, aby ho zahrnoval - jinak by cena spadla presne o tu
    castku, kterou backfill neumi spocitat."""
    stary_jc = (stary_ps or {}).get("joint_count") or 0
    if not stary_jc:
        return novy_ps  # zadny znamy pocet spoju k zachovani - novy vysledek beze zmeny
    stary_jck = (stary_ps or {}).get("joint_czk") or 0
    slouceny = dict(novy_ps)
    slouceny["joint_count"] = stary_jc
    slouceny["joint_czk"] = stary_jck
    slouceny["total_czk"] = round((novy_ps.get("total_czk") or 0) + stary_jck)
    slouceny.pop("joint_price_odhad_chybi_czk", None)
    slouceny.pop("backfill_note", None)
    return slouceny


def zpracuj_bom_backfill(assembly_id):
    """Spocita a rovnou zapise bom/price_summary pro JEDNO ID. Vraci
    (ok: bool, poznamka: str). Nic nezapisuje, kdyz vypocet selze."""
    vysledek_soubor = os.path.join(OUT_DIR, "assembly_%d.json" % assembly_id)
    if os.path.exists(vysledek_soubor):
        os.remove(vysledek_soubor)  # nikdy nepouzit cizi/stary zbytek
    os.makedirs(OUT_DIR, exist_ok=True)

    p = subprocess.run(
        ["node", os.path.join(REPO, "scripts/2026-09-06_backfill_bom_price.js"),
         "--id", str(assembly_id)],
        cwd=REPO, capture_output=True, text=True, timeout=180,
    )
    if p.returncode != 0:
        return False, ("backfill_bom_price.js selhal (exit %d): %s"
                       % (p.returncode, (p.stderr or p.stdout)[-250:]))
    if not os.path.exists(vysledek_soubor):
        return False, "backfill_bom_price.js dobehl, ale vystupni soubor nevznikl (0 vysledku?)"

    try:
        v = json.load(open(vysledek_soubor, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, "nejde precist vystupni soubor: %s" % e
    finally:
        try:
            os.remove(vysledek_soubor)
        except OSError:
            pass

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (assembly_id,))
            row = cur.fetchone()
            if not row:
                return False, "sestava mezitim zmizela z DB"
            d = json.loads(row["data"]) if row["data"] else {}
            if d.get("bom"):
                return False, "sestava uz mezitim dostala bom jinou cestou (souvisejici zapis) - preskoceno, ne prepisuji"
            d["bom"] = v["bom"]
            d["price_summary"] = slouc_price_summary(d.get("price_summary"), v["price_summary"])
            cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                        (json.dumps(d, ensure_ascii=False), assembly_id))
        conn.commit()
    finally:
        conn.close()

    # kontrola cerstvym spojenim - zapis se overuje, ne predpoklada
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (assembly_id,))
            d2 = json.loads(cur.fetchone()["data"])
    finally:
        conn.close()
    if not d2.get("bom"):
        return False, "po zapisu je bom porad prazdny (zapis se neprojevil)"
    return True, "bom radku=%d, total_czk=%s" % (len(d2["bom"]), (d2.get("price_summary") or {}).get("total_czk"))


def main():
    dry = "--dry-run" in sys.argv

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            if not povoleno(cur):
                print("watchdog_prace_povoleno != '1' - automat vypnuty, konci.")
                return 0
            kandidati = kandidati_bom_backfill(cur)
    finally:
        conn.close()

    print("kandidatu na bom_backfill: %d" % len(kandidati))
    if dry:
        for aid, name in kandidati[:KROKU_MAX]:
            print("  [nahled] id=%-5s %s" % (aid, name[:60]))
        print("--dry-run: nic se nezabira ani nezapisuje.")
        return 0

    if not kandidati:
        return 0

    obnov_vstupni_dumpy()

    zpracovano = 0
    for assembly_id, name in kandidati:
        if zpracovano >= KROKU_MAX:
            print("strop %d kroku dosazen, koncim - dalsi beh prijde od casovace." % KROKU_MAX)
            break

        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                # bot5, 2026-10-02 (STAV.md bod 4, TASKS "ZBYVA bot5"): misto pevneho "po 3 selhanich navzdy vzdat" (fail_count_of >= MAX_FAIL) se po MAX_FAIL selhanich
                # pocka (30 min, 1 h, 2 h ... max 24 h) a zkusi se znovu - docasna pricina (vypadek DB, node) uz polozku NEVYRADI napořád. Pocitadlo selhani dal
                # bubli do UI jako "vyzaduje pohled cloveka" (fail_count), jen se ho automat nevzdava.
                if pwc.blokovano(cur, "assembly", assembly_id, STEP_KEY, MAX_FAIL):
                    continue
                zabrano = pwc.claim(cur, "assembly", assembly_id, STEP_KEY, HELD_BY, LEASE_SECONDS)
            conn.commit()
        finally:
            conn.close()
        if not zabrano:
            continue  # drzi to prave ted nekdo/neco jineho

        zpracovano += 1
        t0 = time.time()
        try:
            ok, poznamka = zpracuj_bom_backfill(assembly_id)
        except Exception as e:  # sirokz zachyt ZAMERNE - kazde selhani se ma zapsat jako 'chyba', ne shodit cely beh
            ok, poznamka = False, "vyjimka: %s" % e

        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                pwc.release(cur, "assembly", assembly_id, STEP_KEY, HELD_BY,
                           "hotovo" if ok else "chyba", poznamka)
            conn.commit()
        finally:
            conn.close()
        print("id=%-5s %-45s %-6s (%.1fs) %s"
              % (assembly_id, name[:45], "HOTOVO" if ok else "CHYBA", time.time() - t0, poznamka))

    print("\nzpracovano kroku: %d" % zpracovano)
    return 0


if __name__ == "__main__":
    sys.exit(main())
